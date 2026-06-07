"""tests/unit/test_responder.py — @@RESPONDER directive parsing.

The directive must be split cleanly off the visible message, parsed correctly,
and degrade safely to free text when missing or malformed.
"""

from app.responder import ResponderSpec, parse, strip_directive


def test_choice_multi_with_options():
    text = (
        "What is the primary reason you had to leave?\n"
        "@@RESPONDER mode=choice; phase=SITUATION; multi=true; "
        "options=Political | Ethnic | Religious | Other"
    )
    visible, spec = parse(text)
    assert visible == "What is the primary reason you had to leave?"
    assert "@@RESPONDER" not in visible
    assert spec.mode == "choice"
    assert spec.multi is True
    assert spec.phase == "SITUATION"
    assert spec.options == ["Political", "Ethnic", "Religious", "Other"]


def test_yes_no_choice_single():
    visible, spec = parse(
        "Are you in immediate danger?\n@@RESPONDER mode=choice; phase=SITUATION; "
        "multi=false; options=Yes | No"
    )
    assert spec.mode == "choice"
    assert spec.multi is False
    assert spec.options == ["Yes", "No"]


def test_country_mode():
    visible, spec = parse("Which country are you from?\n@@RESPONDER mode=country; phase=SITUATION")
    assert spec.mode == "country"
    assert spec.phase == "SITUATION"
    assert spec.options == []


def test_text_mode_with_placeholder():
    _, spec = parse(
        "What languages do you speak?\n@@RESPONDER mode=text; phase=GOALS; "
        "placeholder=e.g. Amharic"
    )
    assert spec.mode == "text"
    assert spec.placeholder == "e.g. Amharic"
    assert spec.phase == "GOALS"


def test_missing_directive_defaults_to_text():
    visible, spec = parse("Just a plain question with no directive.")
    assert visible == "Just a plain question with no directive."
    assert spec.mode == "text"
    assert spec.phase is None


def test_choice_without_options_degrades_to_text():
    _, spec = parse("Hmm?\n@@RESPONDER mode=choice; phase=SITUATION")
    assert spec.mode == "text"


def test_invalid_phase_becomes_none():
    _, spec = parse("Q?\n@@RESPONDER mode=country; phase=NONSENSE")
    assert spec.phase is None


def test_strip_directive_helper():
    assert strip_directive("Hello\n@@RESPONDER mode=text; phase=GOALS") == "Hello"
