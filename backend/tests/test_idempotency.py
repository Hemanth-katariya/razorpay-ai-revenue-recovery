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

    # A second *retry attempt* (attempt_no=2) for the same (subscription_id,
    # event_id) is legitimate -- the Executor's one-retry-then-escalate rule
    # (architecture.md §11) writes exactly this -- so it must be accepted,
    # and action_already_executed must still report True without crashing
    # now that two rows exist for this pair.
    db_session.add(
        ActionExecution(
            subscription_id="sub_1", event_id="evt_1", action_id="resend_invoice_reminder",
            attempt_no=2, status="success", executed_at="2026-01-01T00:00:01",
        )
    )
    db_session.commit()
    assert action_already_executed(db_session, "sub_1", "evt_1") is True

    # A duplicate of the *same* attempt_no for the same pair is what the
    # unique constraint actually guards against (e.g. a race re-inserting
    # attempt 1) -- that must still be rejected by the DB.
    db_session.add(
        ActionExecution(
            subscription_id="sub_1", event_id="evt_1", action_id="resend_invoice_reminder",
            attempt_no=1, status="success", executed_at="2026-01-01T00:00:02",
        )
    )
    try:
        db_session.commit()
        raised = False
    except Exception:
        db_session.rollback()
        raised = True
    assert raised, "DB should refuse a duplicate action_executions row for the same (subscription_id, event_id, attempt_no)"
