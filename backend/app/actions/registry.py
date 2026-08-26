"""Loads/queries the actions table (architecture.md §6).

This table is the single source of truth the Executor and the allow-list
gate both read. It is seeded by scripts/seed_actions.py, not computed at
runtime -- only a human (running that script after a verification spike)
changes a row's status.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Action

# Seed data, product-spec.md §4. Status here is the pre-spike default;
# scripts/seed_actions.py is the only place that flips a row to
# API_VERIFIED, and only after a real Test Mode call succeeds
# (product-spec.md §4.1).
SEED_ACTIONS: list[dict] = [
    {
        "id": "resend_invoice_reminder",
        "display_name": "Resend invoice/payment reminder notification",
        "status": "API_ASSUMED",
    },
    {
        "id": "create_payment_link_and_notify",
        "display_name": "Create a Payment Link for the outstanding amount and send notification",
        "status": "API_ASSUMED",
    },
    {
        "id": "force_retry",
        "display_name": "Force an automatic retry",
        "status": "NOT_SUPPORTED",
    },
    {
        "id": "change_mandate",
        "display_name": "Change payment method / re-authorize mandate",
        "status": "NOT_SUPPORTED",
    },
    {
        "id": "attempt_charge_now",
        "display_name": '"Attempt Charge now" on a halted subscription\'s invoice',
        "status": "HUMAN_REQUIRED",
    },
]


def get_action(db: Session, action_id: str) -> Action | None:
    return db.get(Action, action_id)


def is_verified(db: Session, action_id: str) -> bool:
    action = get_action(db, action_id)
    return action is not None and action.status == "API_VERIFIED"


def list_selectable_for_ai(db: Session) -> list[Action]:
    """Actions the Diagnosis Service may recommend from.

    NOT_SUPPORTED rows are excluded from the menu entirely -- there is no
    escalation reason that models "AI recommended a documented gap", and
    a NOT_SUPPORTED row exists in this table only as an audit record of a
    known limitation, not as a candidate action. Everything else
    (API_VERIFIED, API_ASSUMED, HUMAN_REQUIRED) is selectable: the AI
    picks the best-fit action for the diagnosed category, and the
    deterministic allow-list gate (policy/gates.py) is solely responsible
    for deciding whether that specific action may actually execute right
    now. See docs/implementation-notes.md for why this reading was chosen
    over architecture.md §4's literal "API_VERIFIED subset" phrasing.
    """
    all_actions = db.query(Action).all()
    return [a for a in all_actions if a.status != "NOT_SUPPORTED"]
