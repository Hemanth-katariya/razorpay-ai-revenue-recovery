"""One function per gate (product-spec.md §5, architecture.md §5).

Each gate is a pure function of (subscription, diagnosis, batch_run) --
it reads persisted state and returns a verdict, never mutates anything
and never calls Razorpay or the LLM. engine.py is responsible for
running these in order, stopping at the first failure, and writing
every verdict to gate_results regardless of outcome.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.actions import registry
from app.core import clock
from app.db.models import Action, BatchRun, Diagnosis, Subscription
from sqlalchemy.orm import Session

from app.config import MAX_ATTEMPTS, PER_SUB_EXPOSURE_CAP


@dataclass(frozen=True)
class GateVerdict:
    gate_name: str
    passed: bool
    reason: str


def allow_list_gate(db: Session, subscription: Subscription, diagnosis: Diagnosis) -> GateVerdict:
    if diagnosis.recommended_action_id is None:
        return GateVerdict("allow_list", False, "no_recommended_action")
    action = registry.get_action(db, diagnosis.recommended_action_id)
    if action is None:
        return GateVerdict("allow_list", False, "recommended_action_unknown_id")
    if action.status == "API_VERIFIED":
        return GateVerdict("allow_list", True, "action_verified")
    if action.status == "HUMAN_REQUIRED":
        return GateVerdict("allow_list", False, "human_required")
    if action.status == "API_ASSUMED":
        return GateVerdict("allow_list", False, "unverified_action")
    return GateVerdict("allow_list", False, "not_supported")


def attempt_cap_gate(subscription: Subscription) -> GateVerdict:
    if subscription.attempt_count < MAX_ATTEMPTS:
        return GateVerdict("attempt_cap", True, f"attempt_count={subscription.attempt_count} < {MAX_ATTEMPTS}")
    return GateVerdict("attempt_cap", False, f"attempt_count={subscription.attempt_count} >= {MAX_ATTEMPTS}")


def cooldown_gate(subscription: Subscription, logical_now: str) -> GateVerdict:
    if subscription.cooldown_until is None:
        return GateVerdict("cooldown", True, "no_prior_attempt")
    if clock.is_at_or_after(logical_now, subscription.cooldown_until):
        return GateVerdict("cooldown", True, f"logical_now={logical_now} >= cooldown_until={subscription.cooldown_until}")
    return GateVerdict("cooldown", False, f"logical_now={logical_now} < cooldown_until={subscription.cooldown_until}")


def exposure_cap_gate(subscription: Subscription, batch_run: BatchRun) -> GateVerdict:
    if subscription.outstanding_amount > PER_SUB_EXPOSURE_CAP:
        return GateVerdict(
            "exposure_cap", False,
            f"outstanding_amount={subscription.outstanding_amount} > per_sub_cap={PER_SUB_EXPOSURE_CAP}",
        )
    projected = batch_run.exposure_running_total + subscription.outstanding_amount
    if projected > batch_run.exposure_cap_total:
        return GateVerdict(
            "exposure_cap", False,
            f"projected_total={projected} > batch_cap={batch_run.exposure_cap_total}",
        )
    return GateVerdict("exposure_cap", True, f"projected_total={projected} <= batch_cap={batch_run.exposure_cap_total}")


def idempotency_gate(db: Session, subscription_id: str, event_id: str) -> GateVerdict:
    from app.core.idempotency import action_already_executed

    if action_already_executed(db, subscription_id, event_id):
        return GateVerdict("idempotency", False, "action_execution_already_exists_for_pair")
    return GateVerdict("idempotency", True, "no_prior_execution_for_pair")
