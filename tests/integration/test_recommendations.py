"""tests/integration/test_recommendations.py — country cards + roadmap (T047).

Offline: seeds a completed assessment with real country_lookup records (the same
data the assessment attaches at runtime) and verifies the cards, selection, and
roadmap behave. No model needed — the assessment output is the real-data input.
"""

import gradio as gr

from agent.tools.country_lookup import lookup_country, work_route_countries
from app.phases.recommendations import (
    build,
    card_body_html,
    is_economic_case,
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
    # render_outputs = [intro] + [slot,card,btn]*3 + [roadmap, proceed]
    assert len(updates) == len(ui.render_outputs)
    assert s.selected_country == "Kenya"  # top recommendation auto-selected


# --- economic (non-protection) case: must NOT present asylum -----------------

def _seed_economic_case() -> SessionState:
    s = _seed_completed_assessment()
    s.interview.origin_country = "Bangladesh"
    s.assessment.case_type = "economic_or_other"
    s.assessment.recommended_countries = work_route_countries()[:3]
    s.selected_country = None
    return s


def test_economic_shortlist_is_work_visa_countries_not_asylum():
    recs = work_route_countries()
    assert recs, "expected a curated work-visa shortlist"
    names = {r["country"] for r in recs}
    assert "United Arab Emirates" in names  # Gulf labour market
    for r in recs:
        assert r["workVisa"].get("exists") is True
        assert r["isSignatory"] is False  # not asylum destinations


def test_economic_cards_use_work_route_framing():
    s = _seed_economic_case()
    assert is_economic_case(s) is True
    for rec in s.assessment.recommended_countries:
        html = card_body_html(rec, economic=True)
        assert "Work route" in html            # not "Strong match"
        assert "Recognition rate" not in html  # no asylum recognition rate
        assert "Work visa" in html


def test_economic_roadmap_is_labour_not_asylum():
    rec = work_route_countries()[0]
    rm = roadmap_html(rec, economic=True)
    assert "work-route roadmap" in rm.lower()
    assert "Register with UNHCR" not in rm  # not the asylum RSD roadmap
    assert "asylum" not in rm.lower()


def test_economic_case_hides_document_proceed():
    s = _seed_economic_case()
    with gr.Blocks():
        ui = build(visible=False, session_st=gr.State(None))
    updates = ui.populate(s)
    # last update is the "Prepare my documents" button — hidden for economic cases
    proceed_update = updates[-1]
    assert proceed_update.get("visible") is False
