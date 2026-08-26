"""Writes/updates the actions table (architecture.md §13).

Run after `init_db()` to populate the registry, and re-run after a
manual §4.1 capability-verification spike to flip a row's status to
API_VERIFIED. This script is the only place application code sets
Action.status -- there is no runtime code path that promotes a row.

Usage:
    python -m scripts.seed_actions
"""
from __future__ import annotations

from app.actions.registry import SEED_ACTIONS
from app.db.models import Action
from app.db.session import SessionLocal, init_db


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        for row in SEED_ACTIONS:
            existing = db.get(Action, row["id"])
            if existing is None:
                db.add(Action(**row, verified_at=None, verification_notes=None))
            else:
                # Never overwrite a status a human already promoted/demoted
                # via the verification spike -- only fill in a brand-new row.
                pass
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
    print(f"Seeded {len(SEED_ACTIONS)} actions (existing rows left untouched).")
