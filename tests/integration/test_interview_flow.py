"""tests/integration/test_interview_flow.py — real multi-turn interview (T026).

Uses the real AgentLoop and a real model (whatever MODEL_ID/.env points at —
gemma4:12b by default) against the configured Ollama host. No mocks, no
fabricated tool results. Skips cleanly if the model host is unreachable so the
unit suite can still run offline.

Covers: SC-008 (3 distinct agent questions), SC-014 (state advances within
SITUATION..REVIEW), and the streaming event ordering contract.
"""

from __future__ import annotations

import asyncio

import pytest

from agent.events import (
    AgentEndEvent,
    AgentStartEvent,
    ErrorEvent,
    TextDeltaEvent,
    TurnStartEvent,
)
from agent.loop import create_loop
from app.phases.interview import BOOTSTRAP, advance_to
from app.prompt_loader import interview_system_prompt
from app.responder import parse
from app.state.session import SessionState, State


def _host_reachable() -> bool:
    import os
    import urllib.request

    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    try:
        urllib.request.urlopen(host + "/api/tags", timeout=3)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _host_reachable(), reason="Ollama host not reachable; integration test needs a real model"
)


async def _run_turn(loop, session, prompt):
    """Drive one real turn; return (event_types, agent_text, spec)."""
    types: list[str] = []
    acc = ""
    final = list(session.messages)
    async for ev in loop.run(prompt, session, system_prompt=interview_system_prompt()):
        types.append(ev.type)
        if isinstance(ev, TextDeltaEvent):
            acc += ev.delta
        elif isinstance(ev, AgentEndEvent):
            final = ev.messages
        elif isinstance(ev, ErrorEvent):
            raise AssertionError(f"loop raised ErrorEvent: {ev.message}")
    session.messages = final
    _, spec = parse(acc)
    advance_to(session, spec.phase)
    return types, acc.strip(), spec


def _assert_stream_order(types: list[str]):
    assert types, "no events were produced"
    assert types[0] == "agent_start", f"first event must be agent_start, got {types[0]}"
    assert types[-1] == "agent_end", f"last event must be agent_end, got {types[-1]}"
    assert "turn_start" in types
    assert types.index("agent_start") < types.index("turn_start")
    assert "text_delta" in types, "expected streamed text deltas"


@pytest.mark.asyncio
async def test_real_interview_multiturn():
    session = SessionState()
    session.transition_to(State.INTAKE)
    loop = create_loop()

    # Turn 1 — the agent's opening question.
    t1_types, t1_text, _ = await _run_turn(loop, session, BOOTSTRAP)
    _assert_stream_order(t1_types)
    assert len(t1_text) > 0
    # The bootstrap drove us into the interview proper.
    assert State.SITUATION <= session.state <= State.REVIEW

    # Turn 2 — the seeded real scenario.
    t2_types, t2_text, _ = await _run_turn(
        loop, session, "I am from Ethiopia, and I am currently in Sudan."
    )
    _assert_stream_order(t2_types)
    assert len(t2_text) > 0, "agent must ask a follow-up, not go silent"
    assert State.SITUATION <= session.state <= State.REVIEW

    # Turn 3 — another answer; agent should keep the interview moving.
    t3_types, t3_text, _ = await _run_turn(loop, session, "I left for political reasons.")
    _assert_stream_order(t3_types)
    assert len(t3_text) > 0
    assert State.SITUATION <= session.state <= State.REVIEW

    # SC-008: three distinct agent questions.
    assert t1_text != t2_text != t3_text
    assert t1_text != t3_text


@pytest.mark.asyncio
async def test_first_event_is_agent_start_quickly():
    """The loop yields AgentStartEvent before any network call (SC-004 echo)."""
    loop = create_loop()
    gen = loop.run(BOOTSTRAP, SessionState(), system_prompt=interview_system_prompt())
    try:
        first = await asyncio.wait_for(gen.__anext__(), timeout=3.0)
    finally:
        await gen.aclose()
    assert isinstance(first, AgentStartEvent)
