"""tests/unit/test_intake_state.py — intake language selection logic (T034).

Single-select language with click-to-deselect; beginning the interview without a
language is a ValueError surfaced before any model call.
"""

import pytest

from app.phases.intake import (
    begin_interview,
    begin_label,
    select_language,
    toggle_selection,
)
from app.state.session import SessionState, State


def test_select_language_sets_english_name():
    s = SessionState()
    select_language(s, "Français")
    assert s.language == "French"


def test_selecting_new_language_replaces_old():
    s = SessionState()
    select_language(s, "Français")
    select_language(s, "العربية")
    assert s.language == "Arabic"  # not a list, not appended — replaced


def test_deselect_clears_language():
    s = SessionState()
    select_language(s, "English")
    select_language(s, None)
    assert s.language is None


def test_begin_without_language_raises():
    s = SessionState()
    with pytest.raises(ValueError):
        begin_interview(s)


def test_begin_with_language_transitions_to_intake():
    s = SessionState()
    select_language(s, "Español")
    assert begin_interview(s) is State.INTAKE
    assert s.state is State.INTAKE
    assert s.language == "Spanish"


def test_toggle_selection_single_and_deselect():
    # selecting from nothing
    assert toggle_selection("Français", None) == "Français"
    # selecting a different pill replaces
    assert toggle_selection("العربية", "Français") == "العربية"
    # clicking the active pill deselects
    assert toggle_selection("Français", "Français") is None


def test_begin_label_reflects_selection():
    assert begin_label(None) == ("Begin", False)
    assert begin_label("Français") == ("Begin in Français", True)
