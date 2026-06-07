"""tests/unit/test_doc_fields.py — pre-fill field rules (T055).

Pre-filled values trace to real session keys and are amber-highlighted; missing
fields render as a blank line (never a crash, never an invented value).
"""

from agent.tools.doc_generator import build_html, fill
from app.state.session import SessionState, State


def test_fill_present_value_is_highlighted():
    out = fill("Ethiopia", "interview.origin_country")
    assert "Ethiopia" in out
    assert 'class="fill"' in out


def test_fill_missing_value_is_blank_not_placeholder():
    out = fill(None, "interview.origin_country")
    assert 'class="blank"' in out
    assert "Ethiopia" not in out
    assert "None" not in out  # never leak the literal None
    assert "PLACEHOLDER" not in out and "[NAME]" not in out


def test_fill_list_is_joined_and_escaped():
    out = fill(["Political", "Ethnic"], "interview.persecution_types")
    assert "Political, Ethnic" in out
    safe = fill("<script>x</script>", "interview.free_text_history")
    assert "<script>" not in safe  # HTML-escaped


def _min_session() -> SessionState:
    s = SessionState()
    for t in (State.INTAKE, State.SITUATION, State.HISTORY, State.GOALS, State.REVIEW,
              State.ASSESSMENT, State.RECOMMENDATIONS, State.DOCUMENTS):
        s.transition_to(t)
    return s


def test_build_html_with_no_data_does_not_crash():
    # origin_country is None and nothing is filled — must render blanks, not crash.
    s = _min_session()
    htmls = build_html(s)
    assert set(htmls) == {
        "personal_statement", "action_plan", "emergency_contacts", "rights_summary_card"
    }
    statement = htmls["personal_statement"]
    assert 'class="blank"' in statement  # origin rendered as a blank line
    assert "None" not in statement
