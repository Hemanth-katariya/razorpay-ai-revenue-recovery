from app.db.models import Action, BatchRun, Diagnosis, Event, Subscription
from app.policy import engine as policy_engine
from app.policy import gates


def _setup(db, *, action_status="API_VERIFIED", outstanding_amount=1000, attempt_count=0,
           cooldown_until=None, batch_exposure_running=0, batch_exposure_cap=10_000_000,
           per_sub_amount=None):
    db.add(Action(id="resend_invoice_reminder", display_name="Resend", status=action_status))
    batch = BatchRun(
        id="batch_1", label="t", started_at="2026-01-01T00:00:00",
        exposure_cap_total=batch_exposure_cap, exposure_running_total=batch_exposure_running, status="open",
    )
    db.add(batch)
    sub = Subscription(
        id="sub_1", batch_run_id="batch_1", customer_ref="c",
        outstanding_amount=per_sub_amount if per_sub_amount is not None else outstanding_amount,
        current_state="GATED", attempt_count=attempt_count, cooldown_until=cooldown_until,
        created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
    )
    db.add(sub)
    event = Event(
        id="evt_1", batch_run_id="batch_1", subscription_id="sub_1", event_type="payment.failed",
        payload_json="{}", received_at="2026-01-01T00:00:00", signature_valid=True,
    )
    db.add(event)
    diagnosis = Diagnosis(
        event_id="evt_1", subscription_id="sub_1", category="insufficient_funds", confidence=0.9,
        recommended_action_id="resend_invoice_reminder", rationale="r", raw_model_output="{}",
        model_name="claude", prompt_version="v1", created_at="2026-01-01T00:00:00",
    )
    db.add(diagnosis)
    db.commit()
    return sub, event, diagnosis, batch


def test_all_gates_pass_routes_to_executing(db_session):
    sub, event, diagnosis, batch = _setup(db_session)
    outcome = policy_engine.run(
        db_session, subscription=sub, diagnosis=diagnosis, batch_run=batch,
        event_id=event.id, logical_now="2026-01-01T00:00:00",
    )
    assert outcome.next_state == "EXECUTING"
    assert len(outcome.verdicts) == 5


def test_unverified_action_escalates_before_any_other_gate_runs(db_session):
    sub, event, diagnosis, batch = _setup(db_session, action_status="API_ASSUMED")
    outcome = policy_engine.run(
        db_session, subscription=sub, diagnosis=diagnosis, batch_run=batch,
        event_id=event.id, logical_now="2026-01-01T00:00:00",
    )
    assert outcome.next_state == "ESCALATED"
    assert outcome.escalation_reason == "unverified_action"
    assert len(outcome.verdicts) == 1  # stopped at gate 1, no others evaluated


def test_human_required_escalates_with_human_required_reason(db_session):
    sub, event, diagnosis, batch = _setup(db_session, action_status="HUMAN_REQUIRED")
    outcome = policy_engine.run(
        db_session, subscription=sub, diagnosis=diagnosis, batch_run=batch,
        event_id=event.id, logical_now="2026-01-01T00:00:00",
    )
    assert outcome.next_state == "ESCALATED"
    assert outcome.escalation_reason == "human_required"


def test_attempt_cap_exceeded_stops(db_session):
    sub, event, diagnosis, batch = _setup(db_session, attempt_count=3)
    outcome = policy_engine.run(
        db_session, subscription=sub, diagnosis=diagnosis, batch_run=batch,
        event_id=event.id, logical_now="2026-01-01T00:00:00",
    )
    assert outcome.next_state == "STOPPED"
    assert len(outcome.verdicts) == 2  # allow_list passed, attempt_cap failed


def test_cooldown_not_elapsed_stops(db_session):
    sub, event, diagnosis, batch = _setup(db_session, cooldown_until="2026-01-02T00:00:00")
    outcome = policy_engine.run(
        db_session, subscription=sub, diagnosis=diagnosis, batch_run=batch,
        event_id=event.id, logical_now="2026-01-01T12:00:00",
    )
    assert outcome.next_state == "STOPPED"


def test_cooldown_elapsed_passes(db_session):
    sub, event, diagnosis, batch = _setup(db_session, cooldown_until="2026-01-01T00:00:00")
    outcome = policy_engine.run(
        db_session, subscription=sub, diagnosis=diagnosis, batch_run=batch,
        event_id=event.id, logical_now="2026-01-02T00:00:00",
    )
    assert outcome.next_state == "EXECUTING"


def test_per_subscription_exposure_cap_stops(db_session):
    sub, event, diagnosis, batch = _setup(db_session, per_sub_amount=99_999_999)
    outcome = policy_engine.run(
        db_session, subscription=sub, diagnosis=diagnosis, batch_run=batch,
        event_id=event.id, logical_now="2026-01-01T00:00:00",
    )
    assert outcome.next_state == "STOPPED"


def test_batch_exposure_cap_stops(db_session):
    sub, event, diagnosis, batch = _setup(
        db_session, outstanding_amount=6_000_000, batch_exposure_running=6_000_000, batch_exposure_cap=10_000_000,
    )
    outcome = policy_engine.run(
        db_session, subscription=sub, diagnosis=diagnosis, batch_run=batch,
        event_id=event.id, logical_now="2026-01-01T00:00:00",
    )
    assert outcome.next_state == "STOPPED"


def test_idempotency_gate_escalates_on_duplicate_execution(db_session):
    from app.db.models import ActionExecution

    sub, event, diagnosis, batch = _setup(db_session)
    db_session.add(
        ActionExecution(
            subscription_id="sub_1", event_id="evt_1", action_id="resend_invoice_reminder",
            attempt_no=1, status="success", executed_at="2026-01-01T00:00:00",
        )
    )
    db_session.commit()
    outcome = policy_engine.run(
        db_session, subscription=sub, diagnosis=diagnosis, batch_run=batch,
        event_id=event.id, logical_now="2026-01-01T00:00:00",
    )
    assert outcome.next_state == "ESCALATED"
    assert outcome.escalation_reason == "action_execution_already_exists_for_pair"


def test_no_recommended_action_escalates(db_session):
    sub, event, diagnosis, batch = _setup(db_session)
    diagnosis.recommended_action_id = None
    db_session.commit()
    outcome = policy_engine.run(
        db_session, subscription=sub, diagnosis=diagnosis, batch_run=batch,
        event_id=event.id, logical_now="2026-01-01T00:00:00",
    )
    assert outcome.next_state == "ESCALATED"
    assert outcome.escalation_reason == "no_recommended_action"
