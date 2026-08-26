"""§10 queries -- plain read-only SQL aggregates, computed on demand.

Not a streaming pipeline (architecture.md §10). This is the single query
path used by both GET /batches/{id}/metrics and the batch-runner's
end-of-run printout, so the demo can never show a different number than
what the data actually contains (acceptance criterion #7).
"""
from __future__ import annotations

import json
from collections import Counter

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.clock import parse
from app.db.models import AuditLog, Diagnosis, Escalation, Subscription


def compute_metrics(db: Session, *, batch_run_id: str) -> dict:
    subs = db.query(Subscription).filter(Subscription.batch_run_id == batch_run_id).all()
    total_count = len(subs)
    total_amount = sum(s.outstanding_amount for s in subs)

    recovered = [s for s in subs if s.current_state == "RECOVERED"]
    recovered_count = len(recovered)
    recovered_amount = sum(s.outstanding_amount for s in recovered)

    executed_sub_ids = {
        row.subscription_id
        for row in db.query(AuditLog.subscription_id)
        .filter(AuditLog.batch_run_id == batch_run_id, AuditLog.new_state == "EXECUTING")
        .distinct()
    }
    attempted_count = len(executed_sub_ids)

    # A single subscription can be escalated more than once across the batch
    # (repeat failure events re-enter the pipeline, see
    # docs/implementation-notes.md §3). "Escalation rate" is a share of the
    # batch, so this counts distinct subscriptions ever escalated, keyed by
    # each subscription's most recent escalation reason -- consistent with
    # batch_size_reconciliation, which is also per-subscription.
    escalations = (
        db.query(Escalation)
        .join(Subscription, Escalation.subscription_id == Subscription.id)
        .filter(Subscription.batch_run_id == batch_run_id)
        .order_by(Escalation.opened_at.asc())
        .all()
    )
    latest_reason_by_sub = {e.subscription_id: e.reason for e in escalations}
    escalated_sub_count = len(latest_reason_by_sub)
    escalation_by_reason = Counter(latest_reason_by_sub.values())

    stop_rows = db.query(AuditLog).filter(
        AuditLog.batch_run_id == batch_run_id, AuditLog.new_state == "STOPPED"
    ).all()
    stop_by_reason: Counter = Counter()
    for row in stop_rows:
        detail = json.loads(row.detail_json)
        stop_by_reason[detail.get("reason", "unknown")] += 1

    stopped_count = sum(1 for s in subs if s.current_state == "STOPPED")
    not_recovered_count = sum(1 for s in subs if s.current_state == "NOT_RECOVERED")

    # Time-to-recovery: first DETECTED audit ts -> RECOVERED audit ts, per subscription.
    times_to_recovery = []
    for s in recovered:
        first_detected = (
            db.query(AuditLog)
            .filter(AuditLog.subscription_id == s.id, AuditLog.new_state == "DETECTED")
            .order_by(AuditLog.ts.asc())
            .first()
        )
        recovered_row = (
            db.query(AuditLog)
            .filter(AuditLog.subscription_id == s.id, AuditLog.new_state == "RECOVERED")
            .order_by(AuditLog.ts.desc())
            .first()
        )
        if first_detected and recovered_row:
            delta = (parse(recovered_row.ts) - parse(first_detected.ts)).total_seconds()
            times_to_recovery.append(delta)

    avg_time_to_recovery_seconds = sum(times_to_recovery) / len(times_to_recovery) if times_to_recovery else None

    confidences = [
        c
        for (c,) in db.query(Diagnosis.confidence)
        .join(Subscription, Diagnosis.subscription_id == Subscription.id)
        .filter(Subscription.batch_run_id == batch_run_id)
        .all()
    ]
    confidence_buckets = Counter()
    for c in confidences:
        bucket = f"{int(c * 10) * 10}-{int(c * 10) * 10 + 10}%"
        confidence_buckets[bucket] += 1

    return {
        "batch_run_id": batch_run_id,
        "revenue_at_risk_detected": {"count": total_count, "amount_paise": total_amount},
        "revenue_recovered": {"count": recovered_count, "amount_paise": recovered_amount},
        "recovery_rate": {
            "recovered_over_detected": (recovered_count / total_count) if total_count else 0.0,
            "recovered_over_attempted": (recovered_count / attempted_count) if attempted_count else 0.0,
        },
        "escalation_rate": {
            "count": escalated_sub_count,
            "share_of_batch": (escalated_sub_count / total_count) if total_count else 0.0,
            "by_reason": dict(escalation_by_reason),
        },
        "stop_rate": {
            "count": stopped_count,
            "share_of_batch": (stopped_count / total_count) if total_count else 0.0,
            "by_reason": dict(stop_by_reason),
        },
        "not_recovered_count": not_recovered_count,
        "time_to_recovery_seconds_avg": avg_time_to_recovery_seconds,
        "diagnosis_confidence_distribution": dict(confidence_buckets),
        "batch_size_reconciliation": {
            "total": total_count,
            "recovered": recovered_count,
            "stopped": stopped_count,
            "not_recovered": not_recovered_count,
            "still_open": total_count - recovered_count - stopped_count - not_recovered_count,
        },
    }
