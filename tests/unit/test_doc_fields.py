"""tests/unit/test_doc_fields.py — document drafting field rules.

The personal statement is drafted (LLM at runtime; deterministic fallback here);
pre-filled values trace to real session data; missing specifics become clearly
marked [placeholders]; nothing is fabricated.
"""

from agent.drafting import fallback_statement
from agent.tools.doc_generator import _html_with_placeholders, preview_statement_html
from app.state.session import SessionState, State


def _session(origin="Ethiopia"):
    s = SessionState()
    for t in (State.INTAKE, State.SITUATION, State.HISTORY, State.GOALS, State.REVIEW,
              State.ASSESSMENT, State.RECOMMENDATIONS, State.DOCUMENTS):
        s.transition_to(t)
    s.interview.origin_country = origin
    s.interview.current_country = "Sudan"
    s.interview.free_text_history = "Armed men came to our village."
    return s


def test_fallback_statement_uses_real_data_and_placeholders():
    out = fallback_statement(_session())
    assert "Ethiopia" in out                 # real data
    assert "[your full name]" in out          # placeholder for the person to fill
    assert "Armed men came to our village." in out


def test_placeholders_highlighted_in_html():
    html = _html_with_placeholders("My name is [your full name].")
    assert 'class="fill"' in html and "[your full name]" in html


def test_preview_renders_without_crash_on_empty_session():
    s = SessionState()
    html = preview_statement_html(s)  # no data -> placeholders, no crash
    assert "Personal Statement" in html
    assert "None" not in html
