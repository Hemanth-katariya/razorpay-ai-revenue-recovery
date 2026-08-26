"""Runs gates in order, writes gate_results (product-spec.md §5,
architecture.md §5).

The engine is pure aside from the gate_results audit write: it never
calls Razorpay or the LLM, and derives the next state purely from which
gate (if any) failed. It stops at the first failure -- gates after that
point are not evaluated and get no gate_results row.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.clock import now_iso
from app.db.models import BatchRun, Diagnosis, GateResult, Subscription
from app.policy import gates


@dataclass
class PolicyOutcome:
    next_state: str  # EXECUTING | ESCALATED | STOPPED
    escalation_reason: str | None
    verdicts: list[gates.GateVerdict] = field(default_factory=list)


# Gates 1 (allow_list) and 5 (idempotency) failing routes to ESCALATED
# (unverified action / duplicate is not a stopping condition -- it's
# routed to a human, or silently dropped for the idempotency case).
# Gates 2-4 (attempt_cap, cooldown, exposure_cap) failing routes to STOPPED.
# See the early-return in each branch below.


def run(
    db: Session,
    *,
    subscription: Subscription,
    diagnosis: Diagnosis,
    batch_run: BatchRun,
    event_id: str,
    logical_now: str,
) -> PolicyOutcome:
    verdicts: list[gates.GateVerdict] = []

    def record(v: gates.GateVerdict) -> gates.GateVerdict:
        verdicts.append(v)
        db.add(
            GateResult(
                event_id=event_id,
                subscription_id=subscription.id,
                gate_name=v.gate_name,
                passed=v.passed,
                reason=v.reason,
                evaluated_at=now_iso(),
            )
        )
        return v

    v1 = record(gates.allow_list_gate(db, subscription, diagnosis))
    if not v1.passed:
        return PolicyOutcome("ESCALATED", v1.reason, verdicts)

    v2 = record(gates.attempt_cap_gate(subscription))
    if not v2.passed:
        return PolicyOutcome("STOPPED", v2.reason, verdicts)

    v3 = record(gates.cooldown_gate(subscription, logical_now))
    if not v3.passed:
        return PolicyOutcome("STOPPED", v3.reason, verdicts)

    v4 = record(gates.exposure_cap_gate(subscription, batch_run))
    if not v4.passed:
        return PolicyOutcome("STOPPED", v4.reason, verdicts)

    v5 = record(gates.idempotency_gate(db, subscription.id, event_id))
    if not v5.passed:
        return PolicyOutcome("ESCALATED", v5.reason, verdicts)

    return PolicyOutcome("EXECUTING", None, verdicts)
