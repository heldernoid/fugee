"""app/prompt_loader.py — load and compose the agent's markdown prompts.

Prompts live in app/prompts/*.md. ``system.md`` is always the base persona;
phase prompts (``interview.md``, ``assessment.md``) are appended for the phase
the agent is currently driving (T021).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Read a prompt markdown file by stem (e.g. ``"system"``)."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8").strip()


def compose(*names: str) -> str:
    """Join several prompts with blank-line separators, in order."""
    return "\n\n".join(load_prompt(n) for n in names)


def interview_system_prompt() -> str:
    """Base persona + interview protocol + responder directive spec (T021)."""
    return compose("system", "interview")


__all__ = ["load_prompt", "compose", "interview_system_prompt", "PROMPTS_DIR"]
