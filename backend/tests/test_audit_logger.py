"""Covers the centralized auto-resolve-open-escalations behavior in
app/audit/logger.py -- any path that drives a subscription to a terminal
state (batch-close sweep, Outcome Observer, a stopping gate) must not
leave a stale "open" escalation behind.
"""
from app.audit import logger as audit_logger
from app.db.models import BatchRun, Escalation, Subscription


def _setup(db, state="ESCALATED"):
    db.add(
        BatchRun(
            id="batch_1", label="t", started_at="2026-01-01T00:00:00",
            exposure_cap_total=10_000_000, exposure_running_total=0, status="open",
        )
    )
    sub = Subscription(
        id="sub_1", batch_run_id="batch_1", customer_ref="c", outstanding_amount=1000,
        current_state=state, attempt_count=0, created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
    )
    db.add(sub)
    db.add(
        Escalation(
            subscription_id="sub_1", event_id="evt_1", reason="unverified_action",
            status="open", opened_at="2026-01-01T00:00:00",
        )
    )
    db.commit()
    return sub


def test_recovered_transition_auto_resolves_with_recovered_resolution(db_session):
    sub = _setup(db_session, state="ESCALATED")
    audit_logger.record_transition(
        db_session, subscription=sub, new_state="RECOVERED", actor="deterministic",
        ts="2026-01-01T01:00:00", event_id="evt_2", detail={},
    )
    db_session.commit()

    esc = db_session.query(Escalation).filter_by(subscription_id="sub_1").one()
    assert esc.status == "resolved"
    assert esc.resolution == "recovered"
    assert "terminal state RECOVERED" in esc.resolver_note


def test_not_recovered_transition_auto_resolves_with_not_recovered_resolution(db_session):
    sub = _setup(db_session, state="ESCALATED")
    audit_logger.record_transition(
        db_session, subscription=sub, new_state="NOT_RECOVERED", actor="deterministic",
        ts="2026-01-01T01:00:00", event_id=None, detail={},
    )
    db_session.commit()

    esc = db_session.query(Escalation).filter_by(subscription_id="sub_1").one()
    assert esc.status == "resolved"
    assert esc.resolution == "not_recovered"


def test_non_terminal_transition_leaves_escalation_open(db_session):
    sub = _setup(db_session, state="ESCALATED")
    audit_logger.record_transition(
        db_session, subscription=sub, new_state="DETECTED", actor="deterministic",
        ts="2026-01-01T01:00:00", event_id="evt_2", detail={},
    )
    db_session.commit()

    esc = db_session.query(Escalation).filter_by(subscription_id="sub_1").one()
    assert esc.status == "open"
