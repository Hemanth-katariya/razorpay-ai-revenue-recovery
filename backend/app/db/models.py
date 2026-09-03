"""SQLAlchemy models. One-to-one with architecture.md §3.

No migrations tool for the MVP (architecture.md §14) -- Base.metadata.create_all()
at startup is sufficient for a demo database reseeded per run.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return uuid.uuid4().hex


# Legal states, product-spec.md §2. Single source of truth for the enum values.
STATES = (
    "DETECTED",
    "DIAGNOSED",
    "GATED",
    "EXECUTING",
    "ESCALATED",
    "STOPPED",
    "RECOVERED",
    "NOT_RECOVERED",
)
TERMINAL_STATES = ("RECOVERED", "NOT_RECOVERED", "STOPPED")

# Fixed category enum, architecture.md §4.
DIAGNOSIS_CATEGORIES = (
    "insufficient_funds",
    "card_expired",
    "bank_issuer_decline",
    "mandate_issue",
    "unknown",
)

# Action registry status values, product-spec.md §4.
ACTION_STATUSES = ("API_VERIFIED", "API_ASSUMED", "NOT_SUPPORTED", "HUMAN_REQUIRED")

GATE_NAMES = ("allow_list", "attempt_cap", "cooldown", "exposure_cap", "idempotency")

ESCALATION_REASONS = (
    "unverified_action",
    "low_confidence",
    "schema_invalid",
    "executor_failure",
    "human_required",
)


class BatchRun(Base):
    __tablename__ = "batch_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    label: Mapped[str] = mapped_column(String)
    started_at: Mapped[str] = mapped_column(String)  # logical timestamp, ISO 8601
    window_closes_at: Mapped[str | None] = mapped_column(String, nullable=True)
    exposure_cap_total: Mapped[int] = mapped_column(Integer)  # paise
    exposure_running_total: Mapped[int] = mapped_column(Integer, default=0)  # paise
    status: Mapped[str] = mapped_column(String, default="open")  # open | closed

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="batch_run")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # Razorpay subscription_id
    batch_run_id: Mapped[str] = mapped_column(ForeignKey("batch_runs.id"))
    customer_ref: Mapped[str] = mapped_column(String)
    outstanding_amount: Mapped[int] = mapped_column(Integer)  # paise
    current_state: Mapped[str] = mapped_column(String, default="DETECTED")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[str | None] = mapped_column(String, nullable=True)
    cooldown_until: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)

    batch_run: Mapped[BatchRun] = relationship(back_populates="subscriptions")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # Razorpay event_id
    batch_run_id: Mapped[str] = mapped_column(ForeignKey("batch_runs.id"))
    subscription_id: Mapped[str | None] = mapped_column(ForeignKey("subscriptions.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String)
    payload_json: Mapped[str] = mapped_column(Text)
    received_at: Mapped[str] = mapped_column(String)
    signature_valid: Mapped[bool] = mapped_column(Boolean)


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"))
    subscription_id: Mapped[str] = mapped_column(ForeignKey("subscriptions.id"))
    category: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    recommended_action_id: Mapped[str | None] = mapped_column(ForeignKey("actions.id"), nullable=True)
    rationale: Mapped[str] = mapped_column(Text)
    message_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_model_output: Mapped[str] = mapped_column(Text)
    model_name: Mapped[str] = mapped_column(String)
    prompt_version: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "resend_invoice_reminder"
    display_name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    verified_at: Mapped[str | None] = mapped_column(String, nullable=True)
    verification_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class GateResult(Base):
    __tablename__ = "gate_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"))
    subscription_id: Mapped[str] = mapped_column(ForeignKey("subscriptions.id"))
    gate_name: Mapped[str] = mapped_column(String)
    passed: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(Text)
    evaluated_at: Mapped[str] = mapped_column(String)


class ActionExecution(Base):
    __tablename__ = "action_executions"
    # Includes attempt_no: the Executor legitimately writes up to two rows
    # per (subscription_id, event_id) -- one per retry attempt (§11) -- so
    # the race-safety guarantee this constraint provides is "the same
    # attempt can't be double-inserted," not "only one row may ever exist
    # for this pair." See docs/implementation-notes.md for the bug this
    # fixed (the constraint used to omit attempt_no and crash the second
    # attempt with an IntegrityError).
    __table_args__ = (
        UniqueConstraint("subscription_id", "event_id", "attempt_no", name="uq_action_exec_sub_event_attempt"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("subscriptions.id"))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"))
    action_id: Mapped[str] = mapped_column(ForeignKey("actions.id"))
    attempt_no: Mapped[int] = mapped_column(Integer)  # 1 or 2
    status: Mapped[str] = mapped_column(String)  # success | error | timeout
    request_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[str] = mapped_column(String)


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("subscriptions.id"))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"))
    reason: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="open")  # open | resolved
    opened_at: Mapped[str] = mapped_column(String)
    resolved_at: Mapped[str | None] = mapped_column(String, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String, nullable=True)  # recovered | not_recovered
    resolver_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    batch_run_id: Mapped[str] = mapped_column(ForeignKey("batch_runs.id"))
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("subscriptions.id"))
    ts: Mapped[str] = mapped_column(String)  # logical timestamp
    prior_state: Mapped[str | None] = mapped_column(String, nullable=True)
    new_state: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)  # deterministic | ai
    detail_json: Mapped[str] = mapped_column(Text)
