"""Reads later webhooks and matches them back to an open subscription to
mark RECOVERED (architecture.md §1, §2).

Not listed as its own file in architecture.md §13's folder sketch, but
§1's component table names "Outcome Observer" as a distinct
responsibility from the Ingestion API, so it gets its own module rather
than being inlined into api/webhooks.py. See docs/implementation-notes.md.

Deterministic only: this module never calls the LLM. It only reads a
webhook's own payload plus current DB state, and applies the RECOVERED
transition when (and only when) it is legal from the subscription's
current state -- product-spec.md §2, "RECOVERED ... observed, not
claimed."
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.audit import logger as audit_logger
from app.core import state_machine
from app.db.models import Subscription

OUTCOME_CONFIRMING_EVENT_TYPES = {"payment.captured", "invoice.paid", "subscription.charged"}


def observe(
    db: Session,
    *,
    subscription: Subscription,
    event_id: str,
    event_type: str,
    logical_now: str,
) -> bool:
    """Returns True if this event caused a RECOVERED transition."""
    if event_type not in OUTCOME_CONFIRMING_EVENT_TYPES:
        return False

    if "RECOVERED" not in state_machine.TRANSITIONS.get(subscription.current_state, set()):
        # Not an error: e.g. already STOPPED/RECOVERED/NOT_RECOVERED, or a
        # confirming event arrived before our pipeline ever executed
        # anything for this subscription. The raw event is still
        # persisted in `events` regardless of this no-op.
        return False

    audit_logger.record_transition(
        db,
        subscription=subscription,
        new_state="RECOVERED",
        actor="deterministic",
        ts=logical_now,
        event_id=event_id,
        detail={"reason": "outcome_confirmed", "confirming_event_type": event_type},
    )
    return True
