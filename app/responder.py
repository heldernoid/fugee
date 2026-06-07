"""app/responder.py — parse the agent's ``@@RESPONDER`` answer-control directive.

The interview agent ends each message with one machine directive line telling the
UI which answer control to show (see app/prompts/interview.md). This module
splits that directive off the visible message and parses it into a
:class:`ResponderSpec`, so the chat bubble shows only natural language and the
structured responder switches mode deterministically (SC-011).

Parsing is lenient: a missing or malformed directive falls back to free text,
so a small model that forgets the directive never breaks the UI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

DIRECTIVE_RE = re.compile(r"^[ \t]*@@RESPONDER\b(.*)$", re.IGNORECASE | re.MULTILINE)

VALID_MODES = {"choice", "country", "text"}
VALID_PHASES = {"SITUATION", "HISTORY", "GOALS", "REVIEW"}


@dataclass
class ResponderSpec:
    mode: str = "text"
    options: list[str] = field(default_factory=list)
    multi: bool = False
    placeholder: str = ""
    phase: Optional[str] = None


def _parse_fields(body: str) -> dict[str, str]:
    """Parse ``key=value; key=value`` pairs from a directive body."""
    fields: dict[str, str] = {}
    for part in body.split(";"):
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        key = key.strip().lower()
        value = value.strip()
        if key:
            fields[key] = value
    return fields


def parse(text: str) -> tuple[str, ResponderSpec]:
    """Split ``text`` into (visible_message, ResponderSpec).

    The visible message is everything before the directive line, trimmed. If no
    directive is present, the whole text is returned with a free-text spec.
    """
    if not text:
        return "", ResponderSpec(mode="text")

    match = DIRECTIVE_RE.search(text)
    if not match:
        return text.strip(), ResponderSpec(mode="text")

    visible = text[: match.start()].rstrip()
    fields = _parse_fields(match.group(1))

    mode = fields.get("mode", "text").lower()
    if mode not in VALID_MODES:
        mode = "text"

    options = [o.strip() for o in fields.get("options", "").split("|") if o.strip()]
    multi = fields.get("multi", "false").lower() == "true"

    phase = fields.get("phase", "").upper() or None
    if phase not in VALID_PHASES:
        phase = None

    # A choice with no options is meaningless — degrade to free text.
    if mode == "choice" and not options:
        mode = "text"

    return visible, ResponderSpec(
        mode=mode,
        options=options,
        multi=multi,
        placeholder=fields.get("placeholder", ""),
        phase=phase,
    )


def strip_directive(text: str) -> str:
    """Return just the visible message (drops the directive)."""
    return parse(text)[0]


__all__ = ["ResponderSpec", "parse", "strip_directive", "VALID_PHASES", "VALID_MODES"]
