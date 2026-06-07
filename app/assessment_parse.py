"""app/assessment_parse.py — parse the agent's ``@@ASSESSMENT`` summary block.

The assessment agent narrates its reasoning, then ends with a structured block
(see app/prompts/assessment.md). This module splits that block off the visible
reasoning trace and parses it into convention grounds, a risk level, and ranked
country names. Parsing is lenient so a small model that drifts slightly still
yields usable structure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_BLOCK_RE = re.compile(r"@@ASSESSMENT\b(.*?)(?:@@END|\Z)", re.IGNORECASE | re.DOTALL)
_VALID_RISK = {"high", "moderate", "low"}


@dataclass
class AssessmentResult:
    grounds: list[str] = field(default_factory=list)
    risk: str | None = None
    countries: list[str] = field(default_factory=list)


def _split_list(value: str) -> list[str]:
    parts = re.split(r"[|,]", value)
    return [p.strip() for p in parts if p.strip()]


def parse_assessment(text: str) -> tuple[str, AssessmentResult]:
    """Return (visible_reasoning, AssessmentResult)."""
    if not text:
        return "", AssessmentResult()

    match = _BLOCK_RE.search(text)
    if not match:
        return text.strip(), AssessmentResult()

    visible = text[: match.start()].rstrip()
    body = match.group(1)

    result = AssessmentResult()
    for line in body.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "grounds":
            result.grounds = _split_list(value)
        elif key == "risk":
            risk = value.lower()
            result.risk = risk if risk in _VALID_RISK else None
        elif key == "countries":
            result.countries = _split_list(value)

    return visible, result


__all__ = ["AssessmentResult", "parse_assessment"]
