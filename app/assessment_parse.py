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
# Small models sometimes emit the metadata as a prose "Summary of my assessment"
# list instead of the @@ASSESSMENT block (and trail a stray @@END). Strip that too.
_SUMMARY_RE = re.compile(
    r"(?ims)^[ \t>#*_~-]*\**\s*summary of (?:my |the |your )?assessment\b.*?(?:@@END\b|\Z)"
)
# A run of bare metadata field lines (case_type:/grounds:/risk:/countries:).
_FIELD_LINE = re.compile(r"(?im)^[ \t>#*_~\-••]*\**\s*(case_type|grounds|risk|countries)\b\s*:")
# Any stray block marker left behind.
_STRAY_MARKER = re.compile(r"(?im)^[ \t>*_]*@@(?:ASSESSMENT|END)\b.*$")
_VALID_RISK = {"high", "moderate", "low"}


@dataclass
class AssessmentResult:
    grounds: list[str] = field(default_factory=list)
    risk: str | None = None
    countries: list[str] = field(default_factory=list)
    case_type: str | None = None


def _split_list(value: str) -> list[str]:
    # Drop any trailing parenthetical gloss, then split on | or ,.
    value = re.sub(r"\([^)]*\)", "", value)
    parts = re.split(r"[|,]", value)
    return [p.strip(" .*_") for p in parts if p.strip(" .*_")]


def _parse_fields(body: str) -> AssessmentResult:
    result = AssessmentResult()
    for raw in body.splitlines():
        line = raw.strip().lstrip("-*••>#_ ").strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower().strip("*_ ")
        value = value.strip()
        if key == "grounds":
            g = _split_list(value)
            # "none" / "n/a" means no grounds, not a literal ground.
            result.grounds = [] if g and g[0].lower() in {"none", "n/a", "na", "-"} else g
        elif key == "risk":
            m = re.match(r"[a-z]+", value.strip().lower())  # "low (…)" -> "low"
            result.risk = m.group(0) if m and m.group(0) in _VALID_RISK else None
        elif key == "countries":
            result.countries = _split_list(value)
        elif key == "case_type":
            ct = value.lower().strip("*_ .").replace(" ", "_")
            result.case_type = ct or None
    return result


def parse_assessment(text: str) -> tuple[str, AssessmentResult]:
    """Return (visible_reasoning, AssessmentResult).

    Robust to small-model drift. The structured metadata is recognised in three
    forms — the canonical ``@@ASSESSMENT … @@END`` block, a prose "Summary of my
    assessment" section, or a bare run of ``field: value`` lines — and is always
    removed from the visible reasoning (along with any stray ``@@ASSESSMENT`` /
    ``@@END`` markers) so it never leaks onto the screen.
    """
    if not text:
        return "", AssessmentResult()

    spans: list[tuple[int, int]] = []
    body = ""

    block_matches = list(_BLOCK_RE.finditer(text))
    if block_matches:
        spans = [(m.start(), m.end()) for m in block_matches]
        body = block_matches[-1].group(1)
    else:
        sm = _SUMMARY_RE.search(text)
        if sm:
            spans = [(sm.start(), sm.end())]
            body = sm.group(0)
        else:
            fields = list(_FIELD_LINE.finditer(text))
            if fields:
                start = fields[0].start()
                end_m = re.search(r"@@END\b", text[start:], re.IGNORECASE)
                end = start + end_m.end() if end_m else len(text)
                spans = [(start, end)]
                body = text[start:end]

    # Visible reasoning = text minus every metadata span, minus stray markers.
    visible = text
    for s, e in sorted(spans, key=lambda x: -x[0]):
        visible = visible[:s] + visible[e:]
    visible = _STRAY_MARKER.sub("", visible).strip()

    return visible, _parse_fields(body)


__all__ = ["AssessmentResult", "parse_assessment"]
