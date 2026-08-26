"""Legal transitions, single writer of subscriptions.current_state
(architecture.md §8, §13).

Every transition is applied together with its audit_log row in one DB
transaction (see app.audit.logger.record_transition) so the audit trail
can never drift from the actual state. This module only knows the legal
edges and raises loudly on an illegal one -- it does not decide *why* a
transition happens, that's the caller's job.
"""
from __future__ import annotations

from app.db.models import TERMINAL_STATES

# product-spec.md §2 workflow diagram, plus two edges back to DETECTED
# (EXECUTING/ESCALATED -> DETECTED) for a *new* failure event arriving on
# a subscription whose previous cycle didn't reach a terminal state yet --
# the synthetic batch deliberately sends several failures per subscription
# to exercise the attempt cap (product-spec.md acceptance criterion #5).
# STOPPED/RECOVERED/NOT_RECOVERED stay strictly terminal: a repeat failure
# event on an already-terminal subscription is dropped, not reopened (see
# docs/implementation-notes.md).
TRANSITIONS: dict[str, set[str]] = {
    "DETECTED": {"DIAGNOSED", "ESCALATED", "NOT_RECOVERED"},
    "DIAGNOSED": {"GATED", "NOT_RECOVERED"},
    "GATED": {"EXECUTING", "ESCALATED", "STOPPED", "NOT_RECOVERED"},
    "EXECUTING": {"RECOVERED", "ESCALATED", "NOT_RECOVERED", "DETECTED"},
    "ESCALATED": {"RECOVERED", "NOT_RECOVERED", "DETECTED"},
    "STOPPED": set(),
    "RECOVERED": set(),
    "NOT_RECOVERED": set(),
}


class IllegalTransition(Exception):
    pass


def is_terminal(state: str) -> bool:
    return state in TERMINAL_STATES


def assert_legal(prior_state: str, new_state: str) -> None:
    if new_state not in TRANSITIONS.get(prior_state, set()):
        raise IllegalTransition(f"{prior_state} -> {new_state} is not a legal transition")
