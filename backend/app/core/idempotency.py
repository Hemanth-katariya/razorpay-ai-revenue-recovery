"""Event / action-execution dedupe helpers (architecture.md §8).

Two independent layers, both enforced at the DB level so a race can
never double-process:
  1. events.id (Razorpay event_id) is the primary key.
  2. action_executions(subscription_id, event_id) has a unique constraint.
This module only offers read-side existence checks; the actual
guarantee is the DB constraint, not this code.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ActionExecution, Event


def event_already_seen(db: Session, event_id: str) -> bool:
    return db.get(Event, event_id) is not None


def action_already_executed(db: Session, subscription_id: str, event_id: str) -> bool:
    # Existence check, not scalar_one_or_none(): the Executor can legitimately
    # write two rows for this pair (one per retry attempt, see
    # ActionExecution's UniqueConstraint), so more than one match is
    # expected, not an error.
    stmt = select(ActionExecution.id).where(
        ActionExecution.subscription_id == subscription_id,
        ActionExecution.event_id == event_id,
    ).limit(1)
    return db.execute(stmt).first() is not None
