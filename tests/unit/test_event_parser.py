"""tests/unit/test_event_parser.py — agent event contracts (T028).

Every AgentEvent dataclass instantiates with the correct ``type`` string and
carries its payload fields. These are the typed contracts the Gradio phases
dispatch on, so a drift here breaks streaming.
"""

from agent.events import (
    AgentEndEvent,
    AgentStartEvent,
    ErrorEvent,
    TextDeltaEvent,
    ToolEndEvent,
    ToolStartEvent,
    TurnEndEvent,
    TurnStartEvent,
)


def test_marker_events_have_correct_type():
    assert AgentStartEvent().type == "agent_start"
    assert TurnStartEvent().type == "turn_start"


def test_text_delta_carries_delta():
    ev = TextDeltaEvent(delta="hello")
    assert ev.type == "text_delta"
    assert ev.delta == "hello"


def test_tool_start_carries_name_and_args():
    ev = ToolStartEvent(name="country_lookup", args={"country": "Kenya"})
    assert ev.type == "tool_start"
    assert ev.name == "country_lookup"
    assert ev.args == {"country": "Kenya"}


def test_tool_end_carries_result():
    ev = ToolEndEvent(name="country_lookup", result={"unhcrPresence": True})
    assert ev.type == "tool_end"
    assert ev.result["unhcrPresence"] is True


def test_turn_end_carries_message():
    ev = TurnEndEvent(message={"role": "assistant", "content": "hi"})
    assert ev.type == "turn_end"
    assert ev.message["role"] == "assistant"


def test_agent_end_carries_messages():
    msgs = [{"role": "user", "content": "x"}]
    ev = AgentEndEvent(messages=msgs)
    assert ev.type == "agent_end"
    assert ev.messages == msgs


def test_error_carries_message():
    ev = ErrorEvent(message="boom")
    assert ev.type == "error"
    assert ev.message == "boom"


def test_default_factories_are_independent():
    # Mutable defaults must not be shared between instances.
    a, b = ToolStartEvent(), ToolStartEvent()
    a.args["k"] = 1
    assert b.args == {}
