from app.core.idempotency import action_already_executed, event_already_seen
from app.db.models import ActionExecution, BatchRun, Event, Subscription


def _make_batch(db):
    batch = BatchRun(
        id="batch_1", label="t", started_at="2026-01-01T00:00:00",
        exposure_cap_total=10_000_000, exposure_running_total=0, status="open",
    )
    db.add(batch)
    db.commit()
    return batch


def test_event_already_seen(db_session):
    _make_batch(db_session)
    assert event_already_seen(db_session, "evt_1") is False
    db_session.add(
        Event(
            id="evt_1", batch_run_id="batch_1", subscription_id=None, event_type="payment.failed",
            payload_json="{}", received_at="2026-01-01T00:00:00", signature_valid=True,
        )
    )
    db_session.commit()
    assert event_already_seen(db_session, "evt_1") is True


def test_action_execution_unique_constraint_enforced_at_db_level(db_session):
    _make_batch(db_session)
    db_session.add(
        Subscription(
            id="sub_1", batch_run_id="batch_1", customer_ref="c", outstanding_amount=100,
            current_state="EXECUTING", attempt_count=1, created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        )
    )
    db_session.add(
        Event(
            id="evt_1", batch_run_id="batch_1", subscription_id="sub_1", event_type="payment.failed",
            payload_json="{}", received_at="2026-01-01T00:00:00", signature_valid=True,
        )
    )
    db_session.commit()

    assert action_already_executed(db_session, "sub_1", "evt_1") is False

    db_session.add(
        ActionExecution(
            subscription_id="sub_1", event_id="evt_1", action_id="resend_invoice_reminder",
            attempt_no=1, status="success", executed_at="2026-01-01T00:00:00",
        )
    )
    db_session.commit()
    assert action_already_executed(db_session, "sub_1", "evt_1") is True

    # A second attempt at the same (subscription_id, event_id) pair must be
    # rejected by the DB unique constraint, not just application logic.
    db_session.add(
        ActionExecution(
            subscription_id="sub_1", event_id="evt_1", action_id="resend_invoice_reminder",
            attempt_no=2, status="success", executed_at="2026-01-01T00:00:01",
        )
    )
    try:
        db_session.commit()
        raised = False
    except Exception:
        db_session.rollback()
        raised = True
    assert raised, "DB should refuse a second action_executions row for the same (subscription_id, event_id)"
