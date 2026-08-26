"""POST /webhooks/razorpay (architecture.md §1, §2, §12).

Receives one event (real or Test Mode replay), verifies its signature,
enforces idempotency, and -- for the events this MVP acts on -- drives
the full DETECTED -> DIAGNOSED -> GATED -> {EXECUTING|ESCALATED|STOPPED}
flow synchronously in one request, per the architecture.md §2 diagram.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.actions import executor as action_executor
from app.actions.executor import ActionNotVerified
from app.ai import diagnosis as diagnosis_service
from app.audit import logger as audit_logger
from app.config import RAZORPAY_WEBHOOK_SECRET
from app.core import outcome_observer
from app.core.idempotency import event_already_seen
from app.db.models import BatchRun, Diagnosis, Event, Subscription
from app.db.session import get_db
from app.policy import engine as policy_engine
from app.razorpay_client.client import RazorpayNotConfigured

router = APIRouter()
log = logging.getLogger("recoverflow.webhooks")

FAILURE_EVENT_TYPES = {"payment.failed", "subscription.pending", "subscription.halted"}


def verify_signature(raw_body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    expected = hmac.new(RAZORPAY_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhooks/razorpay")
async def receive_webhook(
    request: Request,
    batch_run_id: str = Query(...),
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")

    if not verify_signature(raw_body, signature):
        log.warning("rejected webhook: invalid signature")
        raise HTTPException(status_code=400, detail="invalid signature")

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid JSON body")

    event_id = body.get("id")
    event_type = body.get("event")
    simulated_at = body.get("created_at")
    if not event_id or not event_type or not simulated_at:
        raise HTTPException(status_code=400, detail="missing id/event/created_at")

    if event_already_seen(db, event_id):
        log.info("dropped duplicate event_id=%s", event_id)
        return {"status": "duplicate_dropped", "event_id": event_id}

    batch_run = db.get(BatchRun, batch_run_id)
    if batch_run is None:
        raise HTTPException(status_code=404, detail=f"unknown batch_run_id={batch_run_id!r}")

    payload = body.get("payload", {})
    sub_payload = payload.get("subscription", {})
    subscription_id = sub_payload.get("id")
    if not subscription_id:
        raise HTTPException(status_code=400, detail="payload.subscription.id is required")

    event_row = Event(
        id=event_id,
        batch_run_id=batch_run_id,
        subscription_id=subscription_id,
        event_type=event_type,
        payload_json=json.dumps(payload),
        received_at=simulated_at,
        signature_valid=True,
    )
    db.add(event_row)

    subscription = db.get(Subscription, subscription_id)
    is_new = subscription is None
    if is_new:
        subscription = Subscription(
            id=subscription_id,
            batch_run_id=batch_run_id,
            customer_ref=sub_payload.get("customer_ref", subscription_id),
            outstanding_amount=sub_payload.get("outstanding_amount", 0),
            current_state="DETECTED",
            attempt_count=0,
            created_at=simulated_at,
            updated_at=simulated_at,
        )
        db.add(subscription)
    else:
        subscription.customer_ref = sub_payload.get("customer_ref", subscription.customer_ref)
        if "outstanding_amount" in sub_payload:
            subscription.outstanding_amount = sub_payload["outstanding_amount"]

    result_state = _route_event(
        db,
        subscription=subscription,
        is_new=is_new,
        event_row=event_row,
        event_type=event_type,
        payload=payload,
        batch_run=batch_run,
        logical_now=simulated_at,
    )

    db.commit()
    return {"status": "processed", "event_id": event_id, "subscription_id": subscription_id, "resulting_state": result_state}


def _route_event(
    db: Session,
    *,
    subscription: Subscription,
    is_new: bool,
    event_row: Event,
    event_type: str,
    payload: dict,
    batch_run: BatchRun,
    logical_now: str,
) -> str:
    if event_type in FAILURE_EVENT_TYPES:
        return _run_recovery_pipeline(
            db, subscription=subscription, is_new=is_new, event_row=event_row, payload=payload,
            batch_run=batch_run, logical_now=logical_now,
        )

    matched = outcome_observer.observe(
        db, subscription=subscription, event_id=event_row.id, event_type=event_type, logical_now=logical_now,
    )
    if not matched:
        log.info("event_type=%s for subscription=%s did not change state (state=%s)", event_type, subscription.id, subscription.current_state)
    return subscription.current_state


def _run_recovery_pipeline(
    db: Session,
    *,
    subscription: Subscription,
    is_new: bool,
    event_row: Event,
    payload: dict,
    batch_run: BatchRun,
    logical_now: str,
) -> str:
    from app.core import state_machine

    if is_new:
        audit_logger.record_creation(
            db, subscription=subscription, ts=logical_now, event_id=event_row.id,
            detail={"reason": "first_failure_event", "event_type": event_row.event_type},
        )
    elif "DETECTED" in state_machine.TRANSITIONS.get(subscription.current_state, set()):
        audit_logger.record_transition(
            db, subscription=subscription, new_state="DETECTED", actor="deterministic",
            ts=logical_now, event_id=event_row.id,
            detail={"reason": "new_failure_event", "event_type": event_row.event_type},
        )
    else:
        # Already terminal (STOPPED/RECOVERED/NOT_RECOVERED): this batch's
        # case for this subscription is closed, a repeat failure is
        # dropped rather than reopened. See docs/implementation-notes.md.
        log.info("ignored repeat failure for terminal subscription=%s state=%s", subscription.id, subscription.current_state)
        return subscription.current_state

    diagnosis_result = diagnosis_service.diagnose(
        db,
        event_payload=payload,
        subscription_context={
            "subscription_id": subscription.id,
            "outstanding_amount": subscription.outstanding_amount,
            "attempt_count": subscription.attempt_count,
        },
    )

    if not diagnosis_result.success:
        # Only persist a diagnoses row when the model actually returned a
        # valid, schema-conformant confidence (the low_confidence case) --
        # architecture.md §4 step 4 ties diagnoses.raw_model_output to a
        # successful/validated response. A schema_invalid failure has no
        # real diagnosis to record; its raw_model_output already lives in
        # this audit row's detail_json, which is enough to reconstruct
        # "why" (acceptance criterion #2). This also keeps the confidence
        # distribution metric honest -- it must not count "the model call
        # failed" as if it were "the model reported 0% confidence".
        if diagnosis_result.escalation_reason == "low_confidence":
            db.add(
                Diagnosis(
                    event_id=event_row.id,
                    subscription_id=subscription.id,
                    category=diagnosis_result.category,
                    confidence=diagnosis_result.confidence,
                    recommended_action_id=diagnosis_result.recommended_action_id,
                    rationale=diagnosis_result.rationale or "",
                    message_draft=diagnosis_result.message_draft,
                    raw_model_output=diagnosis_result.raw_model_output,
                    model_name="claude",
                    prompt_version=diagnosis_service.PROMPT_VERSION,
                    created_at=logical_now,
                )
            )
        audit_logger.record_transition(
            db, subscription=subscription, new_state="ESCALATED", actor="ai",
            ts=logical_now, event_id=event_row.id,
            detail={"reason": diagnosis_result.escalation_reason, "raw_model_output": diagnosis_result.raw_model_output},
        )
        _open_escalation(db, subscription, event_row, diagnosis_result.escalation_reason, logical_now)
        return "ESCALATED"

    diagnosis_row = Diagnosis(
        event_id=event_row.id,
        subscription_id=subscription.id,
        category=diagnosis_result.category,
        confidence=diagnosis_result.confidence,
        recommended_action_id=diagnosis_result.recommended_action_id,
        rationale=diagnosis_result.rationale,
        message_draft=diagnosis_result.message_draft,
        raw_model_output=diagnosis_result.raw_model_output,
        model_name="claude",
        prompt_version=diagnosis_service.PROMPT_VERSION,
        created_at=logical_now,
    )
    db.add(diagnosis_row)
    audit_logger.record_transition(
        db, subscription=subscription, new_state="DIAGNOSED", actor="ai",
        ts=logical_now, event_id=event_row.id,
        detail={
            "category": diagnosis_result.category,
            "confidence": diagnosis_result.confidence,
            "recommended_action_id": diagnosis_result.recommended_action_id,
            "rationale": diagnosis_result.rationale,
        },
    )

    audit_logger.record_transition(
        db, subscription=subscription, new_state="GATED", actor="deterministic",
        ts=logical_now, event_id=event_row.id, detail={"note": "policy engine about to run"},
    )
    policy_outcome = policy_engine.run(
        db, subscription=subscription, diagnosis=diagnosis_row, batch_run=batch_run,
        event_id=event_row.id, logical_now=logical_now,
    )

    detail = {"gate_verdicts": [{"gate": v.gate_name, "passed": v.passed, "reason": v.reason} for v in policy_outcome.verdicts]}

    if policy_outcome.next_state == "STOPPED":
        audit_logger.record_transition(
            db, subscription=subscription, new_state="STOPPED", actor="deterministic",
            ts=logical_now, event_id=event_row.id, detail={**detail, "reason": policy_outcome.escalation_reason},
        )
        return "STOPPED"

    if policy_outcome.next_state == "ESCALATED":
        audit_logger.record_transition(
            db, subscription=subscription, new_state="ESCALATED", actor="deterministic",
            ts=logical_now, event_id=event_row.id, detail={**detail, "reason": policy_outcome.escalation_reason},
        )
        _open_escalation(db, subscription, event_row, policy_outcome.escalation_reason, logical_now)
        return "ESCALATED"

    # EXECUTING
    audit_logger.record_transition(
        db, subscription=subscription, new_state="EXECUTING", actor="deterministic",
        ts=logical_now, event_id=event_row.id, detail=detail,
    )
    subscription.attempt_count += 1
    subscription.last_attempt_at = logical_now
    from app.core.clock import add_hours
    from app.config import COOLDOWN_HOURS

    subscription.cooldown_until = add_hours(logical_now, COOLDOWN_HOURS)
    batch_run.exposure_running_total += subscription.outstanding_amount

    try:
        outcome = action_executor.execute(
            db, subscription=subscription, event=event_row, action_id=diagnosis_row.recommended_action_id,
        )
    except (ActionNotVerified, RazorpayNotConfigured) as exc:
        log.error("executor refused to run action: %s", exc)
        audit_logger.record_transition(
            db, subscription=subscription, new_state="ESCALATED", actor="deterministic",
            ts=logical_now, event_id=event_row.id, detail={"reason": "executor_failure", "error": str(exc)},
        )
        _open_escalation(db, subscription, event_row, "executor_failure", logical_now)
        return "ESCALATED"

    if outcome.success:
        return "EXECUTING"

    audit_logger.record_transition(
        db, subscription=subscription, new_state="ESCALATED", actor="deterministic",
        ts=logical_now, event_id=event_row.id, detail={"reason": outcome.escalation_reason},
    )
    _open_escalation(db, subscription, event_row, outcome.escalation_reason, logical_now)
    return "ESCALATED"


def _open_escalation(db: Session, subscription: Subscription, event_row: Event, reason: str | None, ts: str) -> None:
    from app.db.models import Escalation

    db.add(
        Escalation(
            subscription_id=subscription.id,
            event_id=event_row.id,
            reason=reason or "unknown",
            status="open",
            opened_at=ts,
        )
    )
