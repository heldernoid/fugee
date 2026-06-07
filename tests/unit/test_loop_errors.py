"""tests/unit/test_loop_errors.py — loop error handling (SC-015).

If the LLM client fails, the loop must yield an ``ErrorEvent`` and finish
gracefully — never raise through the async generator (which in the UI would be a
silent hang). No real network is used: the client is replaced with a fake.
"""

import pytest

from agent.events import AgentStartEvent, ErrorEvent
from agent.loop import AgentLoop


class _RaisingClient:
    async def chat(self, *args, **kwargs):
        raise RuntimeError("connection refused")


class _RaisingMidStreamClient:
    async def chat(self, *args, **kwargs):
        async def _gen():
            raise RuntimeError("stream died")
            yield  # pragma: no cover - makes this an async generator
        return _gen()


@pytest.mark.asyncio
async def test_error_before_stream_becomes_error_event():
    loop = AgentLoop()
    loop._client = _RaisingClient()  # bypass lazy real client
    events = [ev async for ev in loop.run("hi", session=None, system_prompt="x")]
    assert isinstance(events[0], AgentStartEvent)
    assert isinstance(events[-1], ErrorEvent)
    assert "connection refused" in events[-1].message


@pytest.mark.asyncio
async def test_error_mid_stream_becomes_error_event():
    loop = AgentLoop()
    loop._client = _RaisingMidStreamClient()
    events = [ev async for ev in loop.run("hi", session=None, system_prompt="x")]
    types = [e.type for e in events]
    assert types[0] == "agent_start"
    assert types[-1] == "error"
    assert "stream died" in events[-1].message
