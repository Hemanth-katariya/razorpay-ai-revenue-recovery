"""GET /subscriptions, /subscriptions/{id}/audit (architecture.md §12).

Read-only. No endpoint here allows a client to set current_state --
that's only ever mutated by the State Machine (via audit.logger).
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import AuditLog, Subscription
from app.db.session import get_db

router = APIRouter()


@router.get("/subscriptions")
def list_subscriptions(batch_run_id: str = Query(...), db: Session = Depends(get_db)):
    subs = db.query(Subscription).filter(Subscription.batch_run_id == batch_run_id).all()
    return [
        {
            "id": s.id,
            "customer_ref": s.customer_ref,
            "outstanding_amount": s.outstanding_amount,
            "current_state": s.current_state,
            "attempt_count": s.attempt_count,
            "cooldown_until": s.cooldown_until,
        }
        for s in subs
    ]


@router.get("/subscriptions/{subscription_id}/audit")
def get_audit_trail(subscription_id: str, db: Session = Depends(get_db)):
    sub = db.get(Subscription, subscription_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="subscription not found")

    rows = (
        db.query(AuditLog)
        .filter(AuditLog.subscription_id == subscription_id)
        .order_by(AuditLog.ts.asc())
        .all()
    )
    return {
        "subscription_id": subscription_id,
        "current_state": sub.current_state,
        "trail": [
            {
                "ts": r.ts,
                "prior_state": r.prior_state,
                "new_state": r.new_state,
                "actor": r.actor,
                "event_id": r.event_id,
                "detail": json.loads(r.detail_json),
            }
            for r in rows
        ],
    }
