"""tests/integration/test_interview_flow.py — deterministic interview flow.

The interview is now app-driven (slot-filling): the app owns the questions,
controls, and progression; the LLM only phrases. These tests verify the
deterministic contract (offline) plus a real-model phrasing smoke check.
"""

from __future__ import annotations

import os
import urllib.request

import gradio as gr
import pytest

from app.phases.interview import (
    SLOTS,
    advance_to,
    build,
    control_updates,
    store_answer,
)
from app.state.session import SessionState, State


def _host_reachable() -> bool:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    try:
        urllib.request.urlopen(host + "/api/tags", timeout=3)
        return True
    except Exception:
        return False


def test_slots_cover_fields_and_phases_in_order():
    keys = [s.key for s in SLOTS]
    for required in ("origin_country", "current_country", "persecution_types", "immediate_danger"):
        assert required in keys
    # phases are non-decreasing through the plan
    phases = [s.phase for s in SLOTS]
    assert phases == sorted(phases)


def test_controls_are_deterministic_per_slot():
    def vis(u):
        return [x.get("visible") for x in u]

    by_key = {s.key: s for s in SLOTS}
    assert vis(control_updates(by_key["current_country"])) == [False, False, True, False]  # country only
    assert vis(control_updates(by_key["persecution_types"])) == [False, True, False, False]  # multi only
    assert vis(control_updates(by_key["immediate_danger"])) == [True, False, False, False]  # radio only


def test_store_answer_types():
    s = SessionState()
    by_key = {sl.key: sl for sl in SLOTS}
    store_answer(s, by_key["current_country"], None, None, "🇨🇴 Colombia", None)
    assert s.interview.current_country == "Colombia"
    store_answer(s, by_key["persecution_types"], None, ["Political", "Ethnic"], None, None)
    assert s.interview.persecution_types == ["Political", "Ethnic"]
    store_answer(s, by_key["immediate_danger"], "Yes", None, None, None)
    assert s.interview.immediate_danger is True


def test_advance_to_is_forward_only():
    s = SessionState()
    s.transition_to(State.INTAKE)
    advance_to(s, State.GOALS)
    assert s.state is State.GOALS
    advance_to(s, State.SITUATION)  # backward ignored
    assert s.state is State.GOALS


@pytest.mark.skipif(not _host_reachable(), reason="Ollama host not reachable")
@pytest.mark.asyncio
async def test_real_model_phrases_first_question():
    """start_fn streams an LLM-phrased opening question and shows the country control."""
    with gr.Blocks():
        iv = build()
    lengths, last = [], None
    async for out in iv.start_fn(None, None):
        if isinstance(out[0], str):
            lengths.append(len(out[0]))
        last = out
    # streamed progressively, ended on SITUATION with the country picker visible
    assert len(lengths) >= 2
    session = last[6]
    assert session.state == State.SITUATION
    country_update = last[4]  # (chat, rail, radio, multi, country, text, ...)
    assert country_update.get("visible") is True
