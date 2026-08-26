"""Single write path for audit_log (architecture.md §1, §9).

Every other component calls into `record_transition` -- nothing else in
the codebase constructs an AuditLog row. audit_log is append-only: there
is deliberately no update/delete function here.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core import state_machine
from app.db.models import AuditLog, Escalation, Subscription

# A subscription can reach a terminal state through more than one path
# (batch-close force-sweep, the Outcome Observer, or a fresh failure event
# re-entering the pipeline and hitting a stopping gate) while it still has
# an escalation opened by an earlier cycle. Whichever path gets there
# first, any of its still-open escalations must be reconciled here, in the
# single place current_state actually changes -- not duplicated in every
# caller that might produce a terminal transition.
_TERMINAL_STATE_RESOLUTION = {
    "RECOVERED": "recovered",
    "NOT_RECOVERED": "not_recovered",
    "STOPPED": "not_recovered",
}


def record_transition(
    db: Session,
    *,
    subscription: Subscription,
    new_state: str,
    actor: str,
    ts: str,
    event_id: str | None,
    detail: dict,
) -> AuditLog:
    """Advance subscription.current_state and append the matching audit
    row in one caller-managed transaction. Raises state_machine.IllegalTransition
    rather than silently accepting an inconsistent state.
    """
    prior_state = subscription.current_state
    state_machine.assert_legal(prior_state, new_state)

    subscription.current_state = new_state
    subscription.updated_at = ts

    row = AuditLog(
        batch_run_id=subscription.batch_run_id,
        event_id=event_id,
        subscription_id=subscription.id,
        ts=ts,
        prior_state=prior_state,
        new_state=new_state,
        actor=actor,
        detail_json=json.dumps(detail),
    )
    db.add(row)
    db.add(subscription)

    if new_state in _TERMINAL_STATE_RESOLUTION:
        _auto_resolve_open_escalations(db, subscription, ts, resolution=_TERMINAL_STATE_RESOLUTION[new_state])

    return row


def _auto_resolve_open_escalations(db: Session, subscription: Subscription, ts: str, *, resolution: str) -> None:
    open_escalations = (
        db.query(Escalation)
        .filter(Escalation.subscription_id == subscription.id, Escalation.status == "open")
        .all()
    )
    for esc in open_escalations:
        esc.status = "resolved"
        esc.resolved_at = ts
        esc.resolution = resolution
        esc.resolver_note = f"auto-resolved: subscription reached terminal state {subscription.current_state}"
        db.add(esc)


def record_creation(
    db: Session,
    *,
    subscription: Subscription,
    ts: str,
    event_id: str | None,
    detail: dict,
) -> AuditLog:
    """A brand-new subscription's first row: there is no prior state to
    transition from (it's an insert, not a transition), so this bypasses
    state_machine.assert_legal rather than faking a prior_state.
    subscription.current_state must already be set to "DETECTED" by the
    caller before this is invoked.
    """
    row = AuditLog(
        batch_run_id=subscription.batch_run_id,
        event_id=event_id,
        subscription_id=subscription.id,
        ts=ts,
        prior_state=None,
        new_state=subscription.current_state,
        actor="deterministic",
        detail_json=json.dumps(detail),
    )
    db.add(row)
    return row
