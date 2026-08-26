"""Diagnosis output schema (architecture.md §4).

Malformed or off-schema model output is a first-class failure path
(product-spec.md §7): anything that doesn't validate here routes straight
to ESCALATED with reason=schema_invalid, never retried with a looser
prompt.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.models import DIAGNOSIS_CATEGORIES

NO_ACTION_SENTINEL = "none"


class DiagnosisOutput(BaseModel):
    category: str = Field(description="Fixed failure category")
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_action_id: str = Field(
        description=f"An allow-listed action id, or the literal '{NO_ACTION_SENTINEL}' if none fits"
    )
    rationale: str = Field(min_length=1, max_length=500)
    message_draft: str | None = None

    def model_post_init(self, __context) -> None:
        if self.category not in DIAGNOSIS_CATEGORIES:
            raise ValueError(f"category '{self.category}' not in fixed enum {DIAGNOSIS_CATEGORIES}")


def tool_input_schema(allowed_action_ids: list[str]) -> dict:
    """JSON schema for the Anthropic tool call, built fresh per request so
    the allow-listed action set (architecture.md §4 point 2) is injected
    at call time rather than baked into a static schema.
    """
    return {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": list(DIAGNOSIS_CATEGORIES)},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "recommended_action_id": {
                "type": "string",
                "enum": [*allowed_action_ids, NO_ACTION_SENTINEL],
            },
            "rationale": {"type": "string", "maxLength": 500},
            "message_draft": {"type": ["string", "null"]},
        },
        "required": ["category", "confidence", "recommended_action_id", "rationale"],
    }
