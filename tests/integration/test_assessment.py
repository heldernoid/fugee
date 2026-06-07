"""tests/integration/test_assessment.py — real assessment + real tools (T041).

Seeds a real scenario (Ethiopian, political persecution, currently in Sudan) and
runs the full assessment with the real model and real tools (Tavily web_search,
country_lookup). No mocks, no fabricated data. Skips cleanly if the model host or
the Tavily key is unavailable.

Covers SC-025 (real web_search), SC-027 (>=1 recommendation), SC-028 (origin
excluded), SC-029 (session.assessment populated).
"""

from __future__ import annotations

import os
import urllib.request

import pytest

from agent.loop import create_loop
from agent.tools.web_search import search
from app.phases.assessment import stream_assessment
from app.state.session import SessionState, State


def _host_reachable() -> bool:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    try:
        urllib.request.urlopen(host + "/api/tags", timeout=3)
        return True
    except Exception:
        return False


_needs_model = pytest.mark.skipif(not _host_reachable(), reason="Ollama host not reachable")
_needs_tavily = pytest.mark.skipif(not os.getenv("TAVILY_API_KEY"), reason="TAVILY_API_KEY not set")


def _seed_session() -> SessionState:
    s = SessionState()
    s.language = "Amharic"
    # Walk the state machine to REVIEW (forward-only).
    for target in (State.INTAKE, State.SITUATION, State.HISTORY, State.GOALS, State.REVIEW):
        s.transition_to(target)
    s.interview.origin_country = "Ethiopia"
    s.interview.current_country = "Sudan"
    s.interview.persecution_types = ["Political"]
    s.interview.immediate_danger = True
    s.interview.family_situation = "Traveling with 2 children"
    s.interview.languages_spoken = ["Amharic", "Arabic"]
    s.interview.destination_preferences = ["Nearest safe country with open asylum"]
    s.interview.displacement_duration = "about 3 months"
    return s


@_needs_tavily
@pytest.mark.asyncio
async def test_web_search_real():
    """SC-025: a real query returns at least one result with a real URL."""
    out = await search("Kenya asylum Ethiopia 2026", focus="asylum")
    assert out["results"], "expected at least one search result"
    first = out["results"][0]
    assert first["url"].startswith("http")


@_needs_model
@_needs_tavily
@pytest.mark.asyncio
async def test_assessment_seeded_scenario():
    session = _seed_session()
    loop = create_loop()

    updates = 0
    async for _facts, _reason, _progress in stream_assessment(session, loop):
        updates += 1

    # Progressive streaming happened.
    assert updates >= 3

    a = session.assessment
    # SC-029: structured assessment populated.
    assert a.reasoning_trace and len(a.reasoning_trace) > 100
    # SC-027: at least one recommended country.
    assert len(a.recommended_countries) >= 1
    # Each recommendation carries real country_lookup data.
    for rec in a.recommended_countries:
        assert "unhcrPresence" in rec
        assert rec.get("country")
    # SC-028: never recommend the origin country.
    names = {rec["country"].strip().lower() for rec in a.recommended_countries}
    assert "ethiopia" not in names
