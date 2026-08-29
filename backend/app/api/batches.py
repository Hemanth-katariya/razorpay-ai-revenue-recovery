"""POST /batches, /batches/{id}/close, GET .../metrics (architecture.md §12).

The close step is the Batch Runner's terminal sweep (architecture.md §11):
any subscription still non-terminal when the batch closes is forced to
NOT_RECOVERED, audited -- never left permanently stuck (acceptance
criterion #1).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import logger as audit_logger
from app.core.clock import now_iso
from app.core.state_machine import is_terminal
from app.db.models import BatchRun, Subscription
from app.db.session import get_db
from app.metrics.aggregator import compute_metrics

router = APIRouter()


class CreateBatchRequest(BaseModel):
    label: str
    exposure_cap_total: int  # paise
    window_closes_at: str | None = None
    started_at: str | None = None


class CloseBatchRequest(BaseModel):
    simulated_at: str | None = None


@router.get("/batches")
def list_batches(db: Session = Depends(get_db)):
    batches = db.query(BatchRun).order_by(BatchRun.started_at.asc()).all()
    return [
        {"id": b.id, "label": b.label, "status": b.status, "started_at": b.started_at}
        for b in batches
    ]


@router.post("/batches")
def create_batch(req: CreateBatchRequest, db: Session = Depends(get_db)):
    batch_run = BatchRun(
        label=req.label,
        started_at=req.started_at or now_iso(),
        window_closes_at=req.window_closes_at,
        exposure_cap_total=req.exposure_cap_total,
        exposure_running_total=0,
        status="open",
    )
    db.add(batch_run)
    db.commit()
    db.refresh(batch_run)
    return {"id": batch_run.id, "label": batch_run.label, "status": batch_run.status}


@router.post("/batches/{batch_id}/close")
def close_batch(batch_id: str, req: CloseBatchRequest, db: Session = Depends(get_db)):
    batch_run = db.get(BatchRun, batch_id)
    if batch_run is None:
        raise HTTPException(status_code=404, detail="batch not found")

    ts = req.simulated_at or now_iso()
    swept = 0
    subs = db.query(Subscription).filter(Subscription.batch_run_id == batch_id).all()
    for sub in subs:
        if is_terminal(sub.current_state):
            continue
        # Also auto-resolves any of this subscription's still-open
        # escalations (app/audit/logger.py) -- an "open" escalation on an
        # already-terminal subscription would otherwise be stale data that
        # 409s if someone tried to resolve it later.
        audit_logger.record_transition(
            db, subscription=sub, new_state="NOT_RECOVERED", actor="deterministic",
            ts=ts, event_id=None, detail={"reason": "batch_window_closed_no_outcome_observed"},
        )
        swept += 1

    batch_run.status = "closed"
    db.add(batch_run)
    db.commit()
    return {"id": batch_run.id, "status": "closed", "subscriptions_force_closed": swept}


@router.get("/batches/{batch_id}/metrics")
def get_metrics(batch_id: str, db: Session = Depends(get_db)):
    batch_run = db.get(BatchRun, batch_id)
    if batch_run is None:
        raise HTTPException(status_code=404, detail="batch not found")
    return compute_metrics(db, batch_run_id=batch_id)
