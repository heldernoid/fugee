"""agent/tools/asylum_stats.py — origin→destination asylum statistics tool.

Exposes the UNHCR historical decision data (downloaded by
``data/scripts/unhcr_downloader.py`` into ``data/processed/``) to the agent via
``data/scripts/query_data.py``. This lets the agent ground its suggestions in the
real recognition rate for a *specific* origin→destination pair (e.g. Ethiopians
applying in Kenya vs Egypt), not just per-country averages.

Returns real data or a structured ``{"error": ...}`` — never fabricated figures
(CLAUDE.md Critical Rule 1). If the data has not been downloaded yet, it says so.
"""

from __future__ import annotations

import sys
from pathlib import Path

from agent.tools.base import AgentTool
from agent.tools.country_lookup import resolve_iso3

# query_data.py lives in data/scripts (not a package); make it importable.
_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "data" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _query():
    import query_data  # imported lazily so the tool loads without the data present
    return query_data


def get_acceptance(origin: str, asylum: str) -> dict:
    """Latest + historical recognition rate for an origin→destination pair."""
    qd = _query()
    o_iso = resolve_iso3(origin) or (origin or "").upper()
    a_iso = resolve_iso3(asylum) or (asylum or "").upper()
    try:
        rates = qd.get_acceptance_rates(o_iso, a_iso, year_from=2010)
    except qd.DataNotAvailableError as exc:
        return {"error": "data_not_downloaded", "detail": str(exc)}
    if not rates:
        return {
            "error": "no_records",
            "origin": origin,
            "asylum": asylum,
            "note": "No UNHCR decision records for this origin/destination pair.",
        }
    latest = rates[-1]
    return {
        "origin": origin,
        "asylum": asylum,
        "originIso": o_iso,
        "asylumIso": a_iso,
        "latestYear": latest.year,
        "recognitionRate": latest.recognition_rate,
        "totalProtectionRate": latest.total_protection_rate,
        "totalDecisions": latest.total_decisions,
        "history": [
            {"year": r.year, "recognitionRate": r.recognition_rate, "totalDecisions": r.total_decisions}
            for r in rates
        ],
    }


async def _execute(args: dict) -> dict:
    args = args or {}
    origin = args.get("origin", "")
    asylum = args.get("asylum", "")
    if not origin or not asylum:
        return {"error": "missing_args", "detail": "origin and asylum are required"}
    try:
        return get_acceptance(origin, asylum)
    except Exception as exc:  # noqa: BLE001
        return {"error": "stats_failed", "detail": f"{type(exc).__name__}: {exc}"}


asylum_stats_tool = AgentTool(
    name="asylum_stats",
    description=(
        "Get the real UNHCR recognition (acceptance) rate for a specific origin "
        "country applying in a specific destination country, with recent history. "
        "Use this to compare how a person's nationality fares across destinations."
    ),
    parameters={
        "type": "object",
        "properties": {
            "origin": {"type": "string", "description": "Country of origin (name or ISO3)"},
            "asylum": {"type": "string", "description": "Destination country (name or ISO3)"},
        },
        "required": ["origin", "asylum"],
    },
    execute=_execute,
)


__all__ = ["asylum_stats_tool", "get_acceptance"]
