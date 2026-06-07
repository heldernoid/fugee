"""agent/tools/base.py — the AgentTool contract.

A tool is a name + description + JSON-Schema parameter spec + an async
``execute`` callable. Tools are registered with :class:`AgentLoop` and exposed
to the model in the Ollama tool-calling format.

See specs/ARCHITECTURE.md §2 Agent Tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable


@dataclass
class AgentTool:
    name: str
    description: str
    parameters: dict  # JSON Schema object
    execute: Callable[[dict], Awaitable[dict]]  # async (args) -> result dict

    def to_ollama_schema(self) -> dict:
        """Render this tool in the Ollama / OpenAI function-calling shape."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


__all__ = ["AgentTool"]
