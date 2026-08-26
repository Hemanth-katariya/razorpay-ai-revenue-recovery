from app.audit import logger as audit_logger
from app.db.models import BatchRun, Diagnosis, Subscription
from app.metrics.aggregator import compute_metrics


def _sub(id_, state, amount=1000):
    return Subscription(
        id=id_, batch_run_id="batch_1", customer_ref="c", outstanding_amount=amount,
        current_state=state, attempt_count=0, created_at="2026-01-01T00:00:00",
        updated_at="2026-01-01T00:00:00",
    )


def test_batch_size_reconciliation_sums_to_total(db_session):
    db_session.add(
        BatchRun(
            id="batch_1", label="t", started_at="2026-01-01T00:00:00",
            exposure_cap_total=10_000_000, exposure_running_total=0, status="open",
        )
    )
    subs = {
        "sub_recovered": _sub("sub_recovered", "DETECTED", amount=1000),
        "sub_stopped": _sub("sub_stopped", "DETECTED", amount=2000),
        "sub_not_recovered": _sub("sub_not_recovered", "DETECTED", amount=3000),
        "sub_open": _sub("sub_open", "DETECTED", amount=4000),
    }
    for s in subs.values():
        db_session.add(s)
    db_session.commit()

    for s in subs.values():
        audit_logger.record_creation(db_session, subscription=s, ts="2026-01-01T00:00:00", event_id=None, detail={})
    db_session.commit()

    audit_logger.record_transition(db_session, subscription=subs["sub_recovered"], new_state="DIAGNOSED", actor="ai", ts="2026-01-01T00:01:00", event_id=None, detail={})
    audit_logger.record_transition(db_session, subscription=subs["sub_recovered"], new_state="GATED", actor="deterministic", ts="2026-01-01T00:02:00", event_id=None, detail={})
    audit_logger.record_transition(db_session, subscription=subs["sub_recovered"], new_state="EXECUTING", actor="deterministic", ts="2026-01-01T00:03:00", event_id=None, detail={})
    audit_logger.record_transition(db_session, subscription=subs["sub_recovered"], new_state="RECOVERED", actor="deterministic", ts="2026-01-01T00:04:00", event_id=None, detail={})

    audit_logger.record_transition(db_session, subscription=subs["sub_stopped"], new_state="DIAGNOSED", actor="ai", ts="2026-01-01T00:01:00", event_id=None, detail={})
    audit_logger.record_transition(db_session, subscription=subs["sub_stopped"], new_state="GATED", actor="deterministic", ts="2026-01-01T00:02:00", event_id=None, detail={})
    audit_logger.record_transition(db_session, subscription=subs["sub_stopped"], new_state="STOPPED", actor="deterministic", ts="2026-01-01T00:03:00", event_id=None, detail={"reason": "attempt_cap"})

    audit_logger.record_transition(db_session, subscription=subs["sub_not_recovered"], new_state="ESCALATED", actor="ai", ts="2026-01-01T00:01:00", event_id=None, detail={})
    audit_logger.record_transition(db_session, subscription=subs["sub_not_recovered"], new_state="NOT_RECOVERED", actor="deterministic", ts="2026-01-01T00:02:00", event_id=None, detail={})

    db_session.commit()

    db_session.add(
        Diagnosis(
            event_id="evt_x", subscription_id="sub_recovered", category="insufficient_funds", confidence=0.75,
            recommended_action_id=None, rationale="r", raw_model_output="{}", model_name="claude",
            prompt_version="v1", created_at="2026-01-01T00:01:00",
        )
    )
    db_session.commit()

    metrics = compute_metrics(db_session, batch_run_id="batch_1")

    recon = metrics["batch_size_reconciliation"]
    assert recon["total"] == 4
    assert recon["recovered"] == 1
    assert recon["stopped"] == 1
    assert recon["not_recovered"] == 1
    assert recon["still_open"] == 1
    assert recon["total"] == recon["recovered"] + recon["stopped"] + recon["not_recovered"] + recon["still_open"]

    assert metrics["revenue_at_risk_detected"]["count"] == 4
    assert metrics["revenue_at_risk_detected"]["amount_paise"] == 10000
    assert metrics["revenue_recovered"]["count"] == 1
    assert metrics["revenue_recovered"]["amount_paise"] == 1000
    assert metrics["stop_rate"]["by_reason"] == {"attempt_cap": 1}
    assert metrics["diagnosis_confidence_distribution"] == {"70-80%": 1}
