"""app/countries.py — lightweight country list for UI selectors.

Reads names + flags from specs/data/countries.json (the committed fallback) for
the interview's country selector. The richer per-country asylum data is loaded by
the country_lookup tool in Phase 3; this is only for the dropdown labels.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COUNTRIES_JSON = REPO_ROOT / "specs" / "data" / "countries.json"


@lru_cache(maxsize=1)
def country_choices() -> list[str]:
    """Sorted ``"<flag> <name>"`` labels for every documented country."""
    data = json.loads(COUNTRIES_JSON.read_text(encoding="utf-8"))
    labels: list[str] = []
    for group in ("signatories", "non_signatories"):
        for entry in data.get(group, {}).values():
            name = entry.get("name")
            if not name:
                continue
            flag = entry.get("flag", "").strip()
            labels.append(f"{flag} {name}".strip())
    return sorted(set(labels), key=lambda s: s.split(" ", 1)[-1])


def country_name(label: str) -> str:
    """Strip the leading flag emoji from a selector label."""
    if not label:
        return ""
    parts = label.split(" ", 1)
    # If the first token is non-ASCII (a flag), drop it.
    if len(parts) == 2 and not parts[0].isascii():
        return parts[1].strip()
    return label.strip()


__all__ = ["country_choices", "country_name", "COUNTRIES_JSON"]
