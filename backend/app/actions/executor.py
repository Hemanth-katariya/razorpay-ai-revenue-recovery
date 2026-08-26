"""Calls razorpay_client, owns the one-retry-then-escalate rule
(architecture.md §1, §11).

The Executor refuses to run any action whose current registry status is
not API_VERIFIED, independent of what the allow-list gate already
checked (defense-in-depth, product-spec.md acceptance criterion #8) --
even if the Policy Engine were ever wrong, this module is a second,
independent gate.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from app.actions import registry
from app.config import EXECUTOR_RETRY_BACKOFF_SECONDS
from app.core.clock import now_iso
from app.db.models import ActionExecution, Event, Subscription
from app.razorpay_client import client as razorpay_client


class ActionNotVerified(Exception):
    pass


@dataclass
class ExecutionOutcome:
    success: bool
    escalation_reason: str | None = None  # "executor_failure" when both attempts fail


def _dispatch(action_id: str, subscription: Subscription, event_payload: dict) -> razorpay_client.RazorpayCallResult:
    if action_id == "resend_invoice_reminder":
        invoice_id = event_payload.get("invoice_id")
        return razorpay_client.resend_invoice_notification(invoice_id)

    if action_id == "create_payment_link_and_notify":
        result = razorpay_client.create_payment_link(
            amount=subscription.outstanding_amount,
            currency="INR",
            description=f"Outstanding payment for subscription {subscription.id}",
            customer={
                "name": event_payload.get("customer_ref", subscription.customer_ref),
                "email": event_payload.get("customer_email"),
                "contact": event_payload.get("customer_contact"),
            },
        )
        if not result.ok:
            return result
        link_id = (result.response or {}).get("id")
        notify_result = razorpay_client.send_payment_link_notification(link_id) if link_id else razorpay_client.RazorpayCallResult(
            ok=False, error_message="payment link created but no id returned; cannot notify"
        )
        combined_response = {"create": result.response, "notify": notify_result.response}
        if not notify_result.ok:
            return razorpay_client.RazorpayCallResult(ok=False, response=combined_response, error_message=notify_result.error_message)
        return razorpay_client.RazorpayCallResult(ok=True, response=combined_response)

    raise ActionNotVerified(f"no dispatcher wired for action_id={action_id!r}")


def execute(
    db: Session,
    *,
    subscription: Subscription,
    event: Event,
    action_id: str,
    dispatch: Callable[[str, Subscription, dict], razorpay_client.RazorpayCallResult] = _dispatch,
) -> ExecutionOutcome:
    if not registry.is_verified(db, action_id):
        raise ActionNotVerified(
            f"action_id={action_id!r} is not API_VERIFIED; the Executor refuses to run it "
            "even though it reached this point (defense-in-depth)."
        )

    event_payload = json.loads(event.payload_json)
    last_error: str | None = None

    for attempt_no in (1, 2):
        try:
            result = dispatch(action_id, subscription, event_payload)
        except Exception as exc:  # razorpay_client raised instead of returning a result
            result = razorpay_client.RazorpayCallResult(ok=False, error_message=str(exc))

        status = "success" if result.ok else "error"
        db.add(
            ActionExecution(
                subscription_id=subscription.id,
                event_id=event.id,
                action_id=action_id,
                attempt_no=attempt_no,
                status=status,
                request_payload=json.dumps({"action_id": action_id, "event_payload": event_payload}, default=str),
                response_payload=json.dumps(result.response, default=str) if result.response is not None else None,
                error_message=result.error_message,
                executed_at=now_iso(),
            )
        )

        if result.ok:
            return ExecutionOutcome(success=True)

        last_error = result.error_message
        if attempt_no == 1:
            time.sleep(EXECUTOR_RETRY_BACKOFF_SECONDS)

    return ExecutionOutcome(success=False, escalation_reason="executor_failure")
