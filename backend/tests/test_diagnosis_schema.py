from types import SimpleNamespace

from app.ai import diagnosis
from app.db.models import Action


class FakeModels:
    def __init__(self, input_dict=None, no_tool_use=False, raise_error=False):
        self._input = input_dict
        self._no_tool_use = no_tool_use
        self._raise_error = raise_error

    def generate_content(self, **kwargs):
        if self._raise_error:
            raise RuntimeError("simulated API failure")
        if self._no_tool_use:
            return SimpleNamespace(function_calls=[], text="not a tool call")
        return SimpleNamespace(
            function_calls=[SimpleNamespace(name="emit_diagnosis", args=self._input)], text=None
        )


class FakeClient:
    def __init__(self, **kwargs):
        self.models = FakeModels(**kwargs)


def _seed_actions(db):
    db.add(Action(id="resend_invoice_reminder", display_name="Resend", status="API_ASSUMED"))
    db.add(Action(id="attempt_charge_now", display_name="Charge now", status="HUMAN_REQUIRED"))
    db.add(Action(id="force_retry", display_name="Force retry", status="NOT_SUPPORTED"))
    db.commit()


def test_valid_diagnosis_succeeds(db_session):
    _seed_actions(db_session)
    client = FakeClient(input_dict={
        "category": "insufficient_funds",
        "confidence": 0.85,
        "recommended_action_id": "resend_invoice_reminder",
        "rationale": "Card had insufficient funds.",
        "message_draft": "Please retry your payment.",
    })
    result = diagnosis.diagnose(db_session, event_payload={}, subscription_context={}, client=client)
    assert result.success
    assert result.category == "insufficient_funds"
    assert result.recommended_action_id == "resend_invoice_reminder"


def test_not_supported_action_is_never_offered_to_ai(db_session):
    _seed_actions(db_session)
    client = FakeClient(input_dict={
        "category": "bank_issuer_decline",
        "confidence": 0.9,
        "recommended_action_id": "force_retry",  # NOT_SUPPORTED, must not be in allow-list
        "rationale": "r",
    })
    result = diagnosis.diagnose(db_session, event_payload={}, subscription_context={}, client=client)
    assert not result.success
    assert result.escalation_reason == "schema_invalid"


def test_low_confidence_escalates(db_session):
    _seed_actions(db_session)
    client = FakeClient(input_dict={
        "category": "unknown",
        "confidence": 0.2,
        "recommended_action_id": "none",
        "rationale": "Ambiguous error.",
    })
    result = diagnosis.diagnose(db_session, event_payload={}, subscription_context={}, client=client)
    assert not result.success
    assert result.escalation_reason == "low_confidence"


def test_invalid_category_is_schema_invalid(db_session):
    _seed_actions(db_session)
    client = FakeClient(input_dict={
        "category": "not_a_real_category",
        "confidence": 0.9,
        "recommended_action_id": "none",
        "rationale": "r",
    })
    result = diagnosis.diagnose(db_session, event_payload={}, subscription_context={}, client=client)
    assert not result.success
    assert result.escalation_reason == "schema_invalid"


def test_missing_tool_call_is_schema_invalid(db_session):
    _seed_actions(db_session)
    client = FakeClient(no_tool_use=True)
    result = diagnosis.diagnose(db_session, event_payload={}, subscription_context={}, client=client)
    assert not result.success
    assert result.escalation_reason == "schema_invalid"


def test_api_error_is_schema_invalid_not_a_crash(db_session):
    _seed_actions(db_session)
    client = FakeClient(raise_error=True)
    result = diagnosis.diagnose(db_session, event_payload={}, subscription_context={}, client=client)
    assert not result.success
    assert result.escalation_reason == "schema_invalid"


def test_human_required_action_is_selectable_by_ai(db_session):
    _seed_actions(db_session)
    client = FakeClient(input_dict={
        "category": "mandate_issue",
        "confidence": 0.9,
        "recommended_action_id": "attempt_charge_now",
        "rationale": "Mandate invalid, needs manual charge.",
    })
    result = diagnosis.diagnose(db_session, event_payload={}, subscription_context={}, client=client)
    assert result.success
    assert result.recommended_action_id == "attempt_charge_now"
