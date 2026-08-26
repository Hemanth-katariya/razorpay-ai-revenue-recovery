"""Prompt build, model call, schema validation (architecture.md §4).

This is the only module in the codebase that calls the LLM. It never
calls Razorpay and never writes to action_executions -- it only produces
a recommendation that the Policy Engine and Executor independently gate
and act on (product-spec.md §3).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import anthropic
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.actions import registry
from app.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, DIAGNOSIS_CONFIDENCE_THRESHOLD
from app.ai.schemas import NO_ACTION_SENTINEL, DiagnosisOutput, tool_input_schema
from app.db.models import DIAGNOSIS_CATEGORIES

PROMPT_VERSION = "v1"
TOOL_NAME = "emit_diagnosis"

_SYSTEM_PROMPT = f"""You are a payment-failure diagnosis assistant for a subscription
billing system. Given one failed-charge event, classify the failure reason and, if
one applies, recommend a single recovery action.

Rules you must follow:
- category must be exactly one of: {", ".join(DIAGNOSIS_CATEGORIES)}.
- recommended_action_id must be exactly one of the allow-listed action ids given to you
  in this request, or the literal string "{NO_ACTION_SENTINEL}" if none of them fit the
  diagnosed cause. Never invent an action id.
- confidence is your genuine calibrated confidence in the category, from 0.0 to 1.0.
  Do not default to a high confidence; use low values when the payload is ambiguous.
- rationale is one sentence explaining the category and action choice, for a human
  audit log.
- message_draft is a short customer-facing reminder only if the recommended action is
  a customer notification; otherwise omit it.
Call the {TOOL_NAME} tool exactly once with your answer. Do not respond in prose.
"""


@dataclass
class DiagnosisCallResult:
    success: bool
    escalation_reason: str | None = None  # "schema_invalid" | "low_confidence"
    category: str | None = None
    confidence: float | None = None
    recommended_action_id: str | None = None  # None means "no action recommended"
    rationale: str | None = None
    message_draft: str | None = None
    raw_model_output: str = ""


def build_user_prompt(event_payload: dict, subscription_context: dict) -> str:
    return json.dumps(
        {
            "event": event_payload,
            "subscription": subscription_context,
        },
        indent=2,
        default=str,
    )


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def diagnose(
    db: Session,
    *,
    event_payload: dict,
    subscription_context: dict,
    client: anthropic.Anthropic | None = None,
) -> DiagnosisCallResult:
    selectable = registry.list_selectable_for_ai(db)
    allowed_action_ids = [a.id for a in selectable]
    schema = tool_input_schema(allowed_action_ids)
    user_prompt = build_user_prompt(event_payload, subscription_context)

    active_client = client or _get_client()
    try:
        response = active_client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[{"name": TOOL_NAME, "description": "Emit the structured diagnosis.", "input_schema": schema}],
            tool_choice={"type": "tool", "name": TOOL_NAME},
        )
    except Exception as exc:  # network/API error: treat as schema_invalid, never crash the pipeline
        return DiagnosisCallResult(
            success=False,
            escalation_reason="schema_invalid",
            raw_model_output=f"<model call failed: {exc!r}>",
        )

    tool_use = next((b for b in response.content if b.type == "tool_use"), None)
    raw_output = json.dumps(tool_use.input) if tool_use is not None else json.dumps([b.model_dump() for b in response.content])

    if tool_use is None:
        return DiagnosisCallResult(success=False, escalation_reason="schema_invalid", raw_model_output=raw_output)

    try:
        parsed = DiagnosisOutput.model_validate(tool_use.input)
    except ValidationError as exc:
        return DiagnosisCallResult(
            success=False,
            escalation_reason="schema_invalid",
            raw_model_output=raw_output + f"\n<validation error: {exc}>",
        )

    if parsed.recommended_action_id != NO_ACTION_SENTINEL and parsed.recommended_action_id not in allowed_action_ids:
        return DiagnosisCallResult(
            success=False,
            escalation_reason="schema_invalid",
            raw_model_output=raw_output + "\n<recommended_action_id outside injected allow-list>",
        )

    if parsed.confidence < DIAGNOSIS_CONFIDENCE_THRESHOLD:
        return DiagnosisCallResult(
            success=False,
            escalation_reason="low_confidence",
            category=parsed.category,
            confidence=parsed.confidence,
            recommended_action_id=None if parsed.recommended_action_id == NO_ACTION_SENTINEL else parsed.recommended_action_id,
            rationale=parsed.rationale,
            message_draft=parsed.message_draft,
            raw_model_output=raw_output,
        )

    return DiagnosisCallResult(
        success=True,
        category=parsed.category,
        confidence=parsed.confidence,
        recommended_action_id=None if parsed.recommended_action_id == NO_ACTION_SENTINEL else parsed.recommended_action_id,
        rationale=parsed.rationale,
        message_draft=parsed.message_draft,
        raw_model_output=raw_output,
    )
