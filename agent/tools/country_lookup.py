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


def _clean(value):
    """Treat the data layer's "PENDING" sentinel as missing (not fabricated)."""
    if isinstance(value, str) and value.strip().upper() == "PENDING":
        return None
    return value


def _load_curated_with_stats() -> dict:
    """Authoritative data = the curated specs/data/countries.json.

    All structural content — organisations, signatory/convention status, asylum
    systems, profiles — ALWAYS comes from the manually curated file. If the
    enriched file exists, it overlays ONLY the numeric ``stats.*`` values that
    the curator left as "PENDING"; it can never replace curated fields.
    """
    curated = json.loads(FALLBACK.read_text(encoding="utf-8"))
    if not ENRICHED.exists():
        return curated
    try:
        enriched = json.loads(ENRICHED.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return curated
    for group in ("signatories", "non_signatories"):
        for iso3, entry in curated.get(group, {}).items():
            en = enriched.get(group, {}).get(iso3)
            if not en or not isinstance(en.get("stats"), dict):
                continue
            stats = dict(entry.get("stats", {}) or {})
            for key, value in en["stats"].items():
                # Only fill from enrichment when it has a real (non-PENDING) value.
                if not (isinstance(value, str) and value.strip().upper() == "PENDING"):
                    stats[key] = value
            entry["stats"] = stats
    return curated


@lru_cache(maxsize=1)
def _index() -> dict[str, dict]:
    """Build a name/iso3 -> entry index once, across both country groups."""
    data = _load_curated_with_stats()
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


def resolve_iso3(country: str) -> str | None:
    """Map a country name or code to its ISO3 (from the curated data)."""
    entry = _lookup(country)
    return entry.get("iso3") if entry else None


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
        "region": entry.get("region"),
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
    pathways = entry.get("alternative_pathways", {}) or {}
    work_visa = pathways.get("work_visa", {}) or {}
    return {
        "country": entry.get("name"),
        "flag": entry.get("flag"),
        "tier": entry.get("tier"),
        "region": entry.get("region"),
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
        "alternativePathways": pathways,
        "workVisa": work_visa,                              # {exists, requirement}
        "economicOpportunity": entry.get("economic_opportunity"),
        "strategicGuidance": entry.get("strategic_guidance"),  # honest caveats
        "kafala": entry.get("kafala"),
        "safety": entry.get("safety"),
        "warning": (
            "Not a party to the 1951 Refugee Convention — no formal asylum system. "
            "May offer temporary or alternative pathways; not a durable solution."
        ),
    }


# Curated labour-migration shortlist for economic (non-protection) cases. These
# are the non-signatory countries whose curated data records a real work-visa
# pathway — historically the most accessible labour markets for foreign workers
# (Gulf states with employer sponsorship), unlike Western countries that
# prioritise their own/EU nationals with strict visa criteria. Ordered by a
# blend of labour-market size and safety; each carries its own honest
# ``strategicGuidance`` caveat so the recommendation is never blind.
_WORK_ROUTE_ORDER = ["UAE", "QAT", "SAU", "OMN", "BHR"]


def work_route_countries() -> list[dict]:
    """Ranked work-visa destinations for an economic-migration case (not asylum)."""
    data = _load_curated_with_stats()
    ns = data.get("non_signatories", {})
    picks: list[dict] = []
    for iso3 in _WORK_ROUTE_ORDER:
        entry = ns.get(iso3)
        if not entry:
            continue
        work_visa = (entry.get("alternative_pathways", {}) or {}).get("work_visa", {}) or {}
        if work_visa.get("exists"):
            picks.append(_record_for_non_signatory(entry))
    return picks


# Curated strong-asylum destinations — tier-1 signatories with full procedures
# and UNHCR presence. Used only as a last-resort fallback for a protection case
# when the model named no resolvable country, so the recommendations screen is
# never empty. Real records, never fabricated.
_STRONG_ASYLUM_ORDER = ["CAN", "DEU", "FRA", "SWE", "NLD", "GBR", "ESP"]


def strong_asylum_destinations() -> list[dict]:
    """Fallback shortlist of robust asylum systems (real signatory records)."""
    data = _load_curated_with_stats()
    sig = data.get("signatories", {})
    picks: list[dict] = []
    for iso3 in _STRONG_ASYLUM_ORDER:
        entry = sig.get(iso3)
        if entry:
            picks.append(_record_for_signatory(entry))
    return picks


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


__all__ = ["country_lookup_tool", "lookup_country", "resolve_iso3",
           "work_route_countries", "strong_asylum_destinations"]
