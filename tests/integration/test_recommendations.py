"""tests/integration/test_recommendations.py — country cards + roadmap (T047).

Offline: seeds a completed assessment with real country_lookup records (the same
data the assessment attaches at runtime) and verifies the cards, selection, and
roadmap behave. No model needed — the assessment output is the real-data input.
"""

import gradio as gr

from agent.tools.country_lookup import lookup_country
from app.phases.recommendations import (
    build,
    card_body_html,
    match_strength,
    roadmap_html,
    select_country,
)
from app.state.session import SessionState, State


def _seed_completed_assessment() -> SessionState:
    s = SessionState()
    for target in (State.INTAKE, State.SITUATION, State.HISTORY, State.GOALS,
                   State.REVIEW, State.ASSESSMENT, State.RECOMMENDATIONS):
        s.transition_to(target)
    s.interview.origin_country = "Ethiopia"
    s.assessment.risk_level = "high"
    s.assessment.recommended_countries = [
        lookup_country("Kenya"),
        lookup_country("Uganda"),
        lookup_country("Egypt"),
    ]
    return s


def test_two_or_three_cards_with_real_names():
    s = _seed_completed_assessment()
    recs = s.assessment.recommended_countries
    assert 2 <= len(recs) <= 3
    for rec in recs:
        html = card_body_html(rec)
        assert rec["country"] in html  # real country name, not a placeholder
        assert "match" in html.lower()  # has a match badge


def test_match_badge_from_real_fields():
    kenya = lookup_country("Kenya")
    assert match_strength(kenya) == "strong"  # signatory + UNHCR + tier 1


def test_selecting_card_sets_selected_country():
    s = _seed_completed_assessment()
    select_country(s, 1)  # Uganda
    assert s.selected_country == "Uganda"
    select_country(s, 0)  # Kenya
    assert s.selected_country == "Kenya"


def test_roadmap_header_names_selected_country():
    kenya = lookup_country("Kenya")
    rm = roadmap_html(kenya)
    assert "Kenya" in rm
    assert rm.count('class="step"') >= 4  # SC-035: >= 4 steps
    uganda = lookup_country("Uganda")
    assert "Uganda" in roadmap_html(uganda)  # SC-036: header changes


def test_populate_shows_cards_and_autoselects_first():
    s = _seed_completed_assessment()
    with gr.Blocks():
        ui = build(visible=False, session_st=gr.State(None))
    updates = ui.populate(s)
    # render_outputs = [slot,card,btn]*3 + [roadmap] = 10 updates
    assert len(updates) == len(ui.render_outputs)
    assert s.selected_country == "Kenya"  # top recommendation auto-selected
