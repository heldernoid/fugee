"""tests/unit/test_loop_ping.py — agent loop ping (T015 / SC-004).

SC-004: ``AgentLoop.run()`` yields an ``AgentStartEvent`` within 3 seconds of the
first call. The loop yields ``AgentStartEvent`` before any network call, so this
exercises the real loop (not a mock) and does not depend on a running model.
"""

import asyncio

import pytest

from agent.events import AgentStartEvent
from agent.loop import AgentLoop


@pytest.mark.asyncio
async def test_run_yields_agent_start_first_within_3s():
    loop = AgentLoop()
    gen = loop.run("ping", session=None, system_prompt="")
    try:
        first = await asyncio.wait_for(gen.__anext__(), timeout=3.0)
    finally:
        await gen.aclose()
    assert isinstance(first, AgentStartEvent)
    assert first.type == "agent_start"
