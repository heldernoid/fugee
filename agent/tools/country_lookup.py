"""agent/tools/country_lookup.py — country asylum-data lookup tool (T036).

Looks a country up in the curated reference data and returns a flat record the
agent (and the recommendations UI) can use: UNHCR presence, processing time,
acceptance/protection rates, primary language, required documents, legal-aid
orgs, UNHCR office, tier, and a warning when relevant.

Data source (priority order, loaded once at import — never re-read per call):
  1. specs/data/countries_enriched.json  (post enrich_downloader.py, if present)
  2. specs/data/countries.json           (curated fallback, always committed)

Both share the same schema (see specs/data/README.md). If a country is not
found the tool returns ``{"error": "not_found"}`` — it never fabricates data
(CLAUDE.md Critical Rule 1).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from agent.tools.base import AgentTool

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "specs" / "data"
ENRICHED = DATA_DIR / "countries_enriched.json"
FALLBACK = DATA_DIR / "countries.json"


def _data_file() -> Path:
    return ENRICHED if ENRICHED.exists() else FALLBACK


def _clean(value):
    """Treat the data layer's "PENDING" sentinel as missing (not fabricated)."""
    if isinstance(value, str) and value.strip().upper() == "PENDING":
        return None
    return value


@lru_cache(maxsize=1)
def _index() -> dict[str, dict]:
    """Build a name/iso3 -> entry index once, across both country groups."""
    data = json.loads(_data_file().read_text(encoding="utf-8"))
    index: dict[str, dict] = {}
    for group in ("signatories", "non_signatories"):
        for iso3, entry in data.get(group, {}).items():
            index[iso3.upper()] = entry
            name = entry.get("name")
            if name:
                index[name.strip().lower()] = entry
    return index


def _lookup(country: str) -> dict | None:
    if not country:
        return None
    idx = _index()
    return idx.get(country.strip().upper()) or idx.get(country.strip().lower())


def _record_for_signatory(entry: dict) -> dict:
    asylum = entry.get("asylum_system", {})
    profile = entry.get("profile", {})
    stats = entry.get("stats", {})
    proc = asylum.get("processing_months", {}) or {}
    languages = profile.get("languages", []) or []
    return {
        "country": entry.get("name"),
        "flag": entry.get("flag"),
        "tier": entry.get("tier"),
        "isSignatory": True,
        "unhcrPresence": bool(asylum.get("unhcr_present")),
        "unhcrOffice": asylum.get("unhcr_office"),
        "processingTimeMonths": proc.get("typical") or proc.get("max"),
        "acceptanceRate": _clean(stats.get("acceptance_rate_recent")),
        "totalProtectionRate": _clean(stats.get("total_protection_rate_recent")),
        "primaryLanguage": languages[0] if languages else None,
        "languages": languages,
        "requiredDocuments": asylum.get("docs_required", []),
        "legalAidOrgs": asylum.get("orgs", []),
        "steps": asylum.get("steps", []),
        "safety": profile.get("safety"),
    }


def _record_for_non_signatory(entry: dict) -> dict:
    languages = entry.get("languages", []) or []
    return {
        "country": entry.get("name"),
        "flag": entry.get("flag"),
        "tier": entry.get("tier"),
        "isSignatory": False,
        "unhcrPresence": False,
        "unhcrOffice": None,
        "processingTimeMonths": None,
        "acceptanceRate": None,
        "totalProtectionRate": None,
        "primaryLanguage": languages[0] if languages else None,
        "languages": languages,
        "requiredDocuments": [],
        "legalAidOrgs": [],
        "alternativePathways": entry.get("alternative_pathways", {}),
        "safety": entry.get("safety"),
        "warning": (
            "Not a party to the 1951 Refugee Convention — no formal asylum system. "
            "May offer temporary or alternative pathways; not a durable solution."
        ),
    }


def lookup_country(country: str) -> dict:
    """Synchronous core (also handy for unit tests)."""
    entry = _lookup(country)
    if entry is None:
        return {"error": "not_found", "country": country}
    if entry.get("convention", {}).get("1951") or "asylum_system" in entry:
        return _record_for_signatory(entry)
    return _record_for_non_signatory(entry)


async def _execute(args: dict) -> dict:
    return lookup_country((args or {}).get("country", ""))


country_lookup_tool = AgentTool(
    name="country_lookup",
    description=(
        "Look up a country's asylum programme: UNHCR presence, processing time, "
        "acceptance rate, primary language, required documents, legal-aid orgs."
    ),
    parameters={
        "type": "object",
        "properties": {
            "country": {"type": "string", "description": "Country name or ISO3 code"},
            "profile": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string"},
                    "persecutionType": {"type": "string"},
                },
            },
        },
        "required": ["country"],
    },
    execute=_execute,
)


__all__ = ["country_lookup_tool", "lookup_country"]
