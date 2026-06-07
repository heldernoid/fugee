"""agent/events.py — AgentEvent dataclasses.

Typed event contracts for the pure-Python agent loop, ported from the
pi-agent-core event-stream design (see specs/ARCHITECTURE.md §1 Agent Loop).

Each event carries a ``type`` string matching its event name so consumers
(Gradio phases) can dispatch on either ``isinstance`` or ``event.type``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union


@dataclass
class AgentStartEvent:
    """Emitted once, before any LLM call, when ``AgentLoop.run`` begins."""

    type: str = "agent_start"


@dataclass
class TurnStartEvent:
    """Emitted at the start of each model turn (one LLM request)."""

    type: str = "turn_start"


@dataclass
class TextDeltaEvent:
    """A streamed chunk of assistant text. Never buffered."""

    delta: str = ""
    type: str = "text_delta"


@dataclass
class ToolStartEvent:
    """A tool call has been requested by the model and is about to run."""

    name: str = ""
    args: dict = field(default_factory=dict)
    type: str = "tool_start"


@dataclass
class ToolEndEvent:
    """A tool call has completed; ``result`` is the tool's return dict."""

    name: str = ""
    result: dict = field(default_factory=dict)
    type: str = "tool_end"


@dataclass
class TurnEndEvent:
    """A model turn finished; ``message`` is the final assistant message."""

    message: dict = field(default_factory=dict)
    type: str = "turn_end"


@dataclass
class AgentEndEvent:
    """The loop finished; ``messages`` is the full conversation history."""

    messages: list = field(default_factory=list)
    type: str = "agent_end"


@dataclass
class ErrorEvent:
    """Any failure inside the loop. Surfaced to the UI — never raised through."""

    message: str = ""
    type: str = "error"


AgentEvent = Union[
    AgentStartEvent,
    TurnStartEvent,
    TextDeltaEvent,
    ToolStartEvent,
    ToolEndEvent,
    TurnEndEvent,
    AgentEndEvent,
    ErrorEvent,
]

__all__ = [
    "AgentStartEvent",
    "TurnStartEvent",
    "TextDeltaEvent",
    "ToolStartEvent",
    "ToolEndEvent",
    "TurnEndEvent",
    "AgentEndEvent",
    "ErrorEvent",
    "AgentEvent",
]
