"""GET/POST /escalations (architecture.md §12).

POST /escalations/{id}/resolve is a human closing the loop -- it writes
the corresponding terminal-state transition through the State Machine,
never by editing current_state directly.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import logger as audit_logger
from app.core.clock import now_iso
from app.core.state_machine import IllegalTransition
from app.db.models import Escalation, Subscription
from app.db.session import get_db

router = APIRouter()


class ResolveEscalationRequest(BaseModel):
    resolution: str  # "recovered" | "not_recovered"
    note: str | None = None
    simulated_at: str | None = None


@router.get("/escalations")
def list_escalations(status: str = Query("open"), db: Session = Depends(get_db)):
    rows = db.query(Escalation).filter(Escalation.status == status).all()
    return [
        {
            "id": e.id,
            "subscription_id": e.subscription_id,
            "event_id": e.event_id,
            "reason": e.reason,
            "status": e.status,
            "opened_at": e.opened_at,
            "resolved_at": e.resolved_at,
            "resolution": e.resolution,
            "resolver_note": e.resolver_note,
        }
        for e in rows
    ]


@router.post("/escalations/{escalation_id}/resolve")
def resolve_escalation(escalation_id: str, req: ResolveEscalationRequest, db: Session = Depends(get_db)):
    if req.resolution not in ("recovered", "not_recovered"):
        raise HTTPException(status_code=400, detail="resolution must be 'recovered' or 'not_recovered'")

    escalation = db.get(Escalation, escalation_id)
    if escalation is None:
        raise HTTPException(status_code=404, detail="escalation not found")
    if escalation.status == "resolved":
        raise HTTPException(status_code=409, detail="escalation already resolved")

    subscription = db.get(Subscription, escalation.subscription_id)
    ts = req.simulated_at or now_iso()
    new_state = "RECOVERED" if req.resolution == "recovered" else "NOT_RECOVERED"

    try:
        audit_logger.record_transition(
            db, subscription=subscription, new_state=new_state, actor="deterministic",
            ts=ts, event_id=escalation.event_id,
            detail={"reason": "human_resolved_escalation", "note": req.note},
        )
    except IllegalTransition:
        # The subscription reached a terminal state some other way since
        # this escalation was opened (most commonly: the batch closed and
        # force-swept it to NOT_RECOVERED before a human got to it -- see
        # app/api/batches.py close_batch, which auto-resolves escalations
        # it sweeps for exactly this reason). Surface a clear conflict
        # rather than a raw 500.
        raise HTTPException(
            status_code=409,
            detail=f"subscription {subscription.id} is already terminal ({subscription.current_state}); cannot resolve this escalation",
        )

    escalation.status = "resolved"
    escalation.resolved_at = ts
    escalation.resolution = req.resolution
    escalation.resolver_note = req.note
    db.add(escalation)
    db.commit()

    return {"id": escalation.id, "status": "resolved", "resolution": req.resolution, "subscription_state": new_state}
