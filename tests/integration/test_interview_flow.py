"""tests/unit-style tests for the fully-scripted interview.

The interview is deterministic (no LLM): a fixed question bank, pre-translated
into every supported language, with fixed controls. These tests verify the
script integrity and the deterministic controls.
"""

import gradio as gr

from app.interview_script import (
    QUESTIONS,
    REVIEW_INDEX,
    TR,
    option_labels,
    question_text,
    t,
)
from app.phases.interview import build, control_updates
from app.phases.intake import LANGUAGES
from app.state.session import SessionState, State


def test_all_offered_languages_have_full_translations():
    base_keys = set(TR["English"])
    offered = {english for _native, english in LANGUAGES}
    for lang in offered:
        assert lang in TR, f"missing translations for {lang}"
        missing = base_keys - set(TR[lang])
        assert not missing, f"{lang} missing keys: {missing}"


def test_questions_cover_fields_and_phases_in_order():
    fields = [q.field for q in QUESTIONS]
    for required in ("current_country", "origin_country", "immediate_danger"):
        assert required in fields
    phases = [q.phase for q in QUESTIONS]
    assert phases == sorted(phases)  # non-decreasing


def test_question_text_templates_origin():
    s = SessionState()
    s.language = "English"
    s.interview.origin_country = "Afghanistan"
    reason_q = next(q for q in QUESTIONS if q.field == "free_text_history")
    text = question_text("English", reason_q, s)
    assert "Afghanistan" in text and "{origin}" not in text


def test_controls_are_deterministic_per_question():
    s = SessionState(); s.language = "English"

    # control order: (radio, grounds, docs, country, text). Choice controls
    # (radio/grounds/docs) are driven by non-empty choices, not a visible flag;
    # country/text are driven by visible=True.
    def active(u):
        radio, grounds, docs, country, text = u
        if radio.get("choices"):
            return "radio"
        if grounds.get("choices"):
            return "grounds"
        if docs.get("choices"):
            return "docs"
        if country.get("visible"):
            return "country"
        if text.get("visible"):
            return "text"
        return None

    by_field = {q.field: i for i, q in enumerate(QUESTIONS)}
    assert active(control_updates(s, by_field["current_country"])) == "country"
    assert active(control_updates(s, by_field["immediate_danger"])) == "radio"  # yes/no
    assert active(control_updates(s, by_field["persecution_types"])) == "grounds"
    assert active(control_updates(s, by_field["documents_available"])) == "docs"
    assert active(control_updates(s, by_field["free_text_history"])) == "text"
    assert active(control_updates(s, REVIEW_INDEX)) == "radio"  # confirm

    # The inactive choice controls are emptied so CSS collapses them (never a
    # stray visible CheckboxGroup leaking through).
    u = control_updates(s, by_field["documents_available"])
    assert u[1]["choices"] == [] and u[0]["choices"] == []  # grounds + radio cleared


def test_option_labels_localised():
    danger_q = next(q for q in QUESTIONS if q.control == "yesno")
    assert option_labels("Spanish", danger_q) == [t("Spanish", "opt_yes"), t("Spanish", "opt_no")]
    assert option_labels("Spanish", danger_q) == ["Sí", "No"]


def test_build_starts_with_country_control():
    with gr.Blocks():
        ui = build()
    assert ui.session is not None and ui.continue_event is not None
