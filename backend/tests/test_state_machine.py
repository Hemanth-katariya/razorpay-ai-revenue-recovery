import pytest

from app.core import state_machine


def test_legal_transition_passes():
    state_machine.assert_legal("DETECTED", "DIAGNOSED")
    state_machine.assert_legal("GATED", "EXECUTING")
    state_machine.assert_legal("EXECUTING", "RECOVERED")


def test_illegal_transition_raises():
    with pytest.raises(state_machine.IllegalTransition):
        state_machine.assert_legal("DETECTED", "EXECUTING")


def test_terminal_states_have_no_outgoing_edges():
    for terminal in ("RECOVERED", "NOT_RECOVERED", "STOPPED"):
        assert state_machine.TRANSITIONS[terminal] == set()
        assert state_machine.is_terminal(terminal)


def test_non_terminal_states_are_not_terminal():
    for s in ("DETECTED", "DIAGNOSED", "GATED", "EXECUTING", "ESCALATED"):
        assert not state_machine.is_terminal(s)


def test_repeat_failure_can_reopen_executing_and_escalated():
    state_machine.assert_legal("EXECUTING", "DETECTED")
    state_machine.assert_legal("ESCALATED", "DETECTED")


def test_stopped_cannot_be_reopened():
    with pytest.raises(state_machine.IllegalTransition):
        state_machine.assert_legal("STOPPED", "DETECTED")
