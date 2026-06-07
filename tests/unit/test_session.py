"""tests/unit/test_session.py — interview state machine (T012 / SC-005).

Forward transitions are allowed; backward or skipped transitions raise
ValueError. The interview is append-only and forward-only (CLAUDE.md Rule 3).
"""

import pytest

from app.state.session import SessionState, State

FORWARD_CHAIN = [
    State.LANGUAGE_SELECT,
    State.INTAKE,
    State.SITUATION,
    State.HISTORY,
    State.GOALS,
    State.REVIEW,
    State.ASSESSMENT,
    State.RECOMMENDATIONS,
    State.DOCUMENTS,
    State.COMPLETE,
]


def test_starts_in_language_select():
    assert SessionState().state is State.LANGUAGE_SELECT


def test_valid_forward_chain_via_advance():
    s = SessionState()
    for expected_next in FORWARD_CHAIN[1:]:
        assert s.advance() is expected_next
    assert s.state is State.COMPLETE


def test_explicit_single_step_forward_is_allowed():
    s = SessionState()
    assert s.transition_to(State.INTAKE) is State.INTAKE
    assert s.transition_to(State.SITUATION) is State.SITUATION


def test_same_state_is_idempotent():
    s = SessionState()
    s.transition_to(State.INTAKE)
    # Re-entering the current state (e.g. re-render) must not raise.
    assert s.transition_to(State.INTAKE) is State.INTAKE


def test_backward_transition_raises():
    s = SessionState()
    # Walk forward to REVIEW.
    for _ in range(FORWARD_CHAIN.index(State.REVIEW)):
        s.advance()
    assert s.state is State.REVIEW
    with pytest.raises(ValueError):
        s.transition_to(State.SITUATION)


def test_skipping_a_state_raises():
    s = SessionState()
    s.transition_to(State.INTAKE)
    with pytest.raises(ValueError):
        s.transition_to(State.ASSESSMENT)


def test_updated_at_changes_on_transition():
    s = SessionState()
    before = s.updated_at
    s.transition_to(State.INTAKE)
    assert s.updated_at >= before
