"""
UNHCR Data Query Helper
========================
Used internally by Refuge's country_lookup tool.
Queries the local processed JSON files — no network required at runtime.

This is the query layer between the agent tools and the downloaded data.
All functions return real data or raise DataNotAvailableError — never fake data.

Co-authored-by: Codex <noreply@openai.com>
"""

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

PROC_DIR = Path(__file__).parent.parent / "processed"


class DataNotAvailableError(Exception):
    """Raised when data for a query cannot be found in local cache."""
    pass


# ── Data loading (cached) ─────────────────────────────────────────────────────

@lru_cache(maxsize=16)
def _load(endpoint: str) -> list[dict]:
    p = PROC_DIR / f"{endpoint}.json"
    if not p.exists():
        raise DataNotAvailableError(
            f"Data for '{endpoint}' not found. "
            f"Run: python3 data/scripts/unhcr_downloader.py --endpoint {endpoint}"
        )
    data = json.loads(p.read_text())
    return data.get("items", [])


# ── Country lookup ────────────────────────────────────────────────────────────

@dataclass
class CountryInfo:
    unhcr_code: str
    iso3: str
    name: str
    unhcr_region: str
    unsd_region: str


def get_country(code: str) -> CountryInfo:
    """Look up a country by UNHCR code or ISO3 code."""
    countries = _load("countries")
    code = code.upper()
    for c in countries:
        if c.get("code") == code or c.get("iso3") == code or c.get("name", "").lower() == code.lower():
            return CountryInfo(
                unhcr_code=c.get("code", ""),
                iso3=c.get("iso3", ""),
                name=c.get("name", ""),
                unhcr_region=c.get("unhcr_region", {}).get("name", "") if isinstance(c.get("unhcr_region"), dict) else c.get("unhcr_region", ""),
                unsd_region=c.get("region", ""),
            )
    raise DataNotAvailableError(f"Country not found: {code}")


def list_african_asylum_countries() -> list[CountryInfo]:
    """Return all countries in UNHCR's African regions."""
    african_regions = {
        "East and Horn of Africa",
        "West and Central Africa",
        "Southern Africa",
        "North Africa",
        "Great Lakes and Central Africa",
    }
    countries = _load("countries")
    results = []
    for c in countries:
        region = c.get("unhcr_region", {})
        region_name = region.get("name", "") if isinstance(region, dict) else str(region)
        if any(ar in region_name for ar in african_regions):
            results.append(CountryInfo(
                unhcr_code=c.get("code", ""),
                iso3=c.get("iso3", ""),
                name=c.get("name", ""),
                unhcr_region=region_name,
                unsd_region=c.get("region", ""),
            ))
    return results


# ── Acceptance rates ──────────────────────────────────────────────────────────

@dataclass
class AcceptanceRate:
    coo: str               # country of origin code
    coa: str               # country of asylum code
    year: int
    recognised: int        # granted Convention status
    complementary: int     # granted complementary protection
    rejected: int
    otherwise_closed: int
    total_decisions: int
    recognition_rate: Optional[float]    # recognised / total (UNHCR definition)
    total_protection_rate: Optional[float]  # (recognised + complementary) / total


def get_acceptance_rates(
    origin_code: str,
    asylum_code: str,
    year_from: int = 2018,
    year_to: int = 2025,
) -> list[AcceptanceRate]:
    """
    Get historical acceptance rates for a specific origin × asylum pair.
    Returns list sorted by year ascending.
    """
    decisions = _load("asylum-decisions")
    origin_code = origin_code.upper()
    asylum_code = asylum_code.upper()

    rates = []
    for row in decisions:
        # Real API rows expose ISO3 as coo_iso/coa_iso (and UNHCR codes as
        # coo/coa); the older coo_code/coa_code keys do not exist.
        row_coo = (row.get("coo_iso") or row.get("coo") or row.get("coo_code") or "").upper()
        row_coa = (row.get("coa_iso") or row.get("coa") or row.get("coa_code") or "").upper()
        if row_coo != origin_code or row_coa != asylum_code:
            continue
        year = int(row.get("year", 0))
        if not (year_from <= year <= year_to):
            continue

        recognised     = int(row.get("dec_recognized", 0) or 0)
        complementary  = int(row.get("dec_other", 0) or 0)  # complementary protection
        rejected       = int(row.get("dec_rejected", 0) or 0)
        closed         = int(row.get("dec_closed", 0) or 0)
        total          = int(row.get("dec_total", 0) or 0)

        rec_rate  = round(recognised / total, 4)         if total > 0 else None
        tpr       = round((recognised + complementary) / total, 4) if total > 0 else None

        rates.append(AcceptanceRate(
            coo=origin_code,
            coa=asylum_code,
            year=year,
            recognised=recognised,
            complementary=complementary,
            rejected=rejected,
            otherwise_closed=closed,
            total_decisions=total,
            recognition_rate=rec_rate,
            total_protection_rate=tpr,
        ))

    return sorted(rates, key=lambda r: r.year)


def latest_acceptance_rate(origin_code: str, asylum_code: str) -> Optional[AcceptanceRate]:
    """Return the most recent available acceptance rate for an origin × asylum pair."""
    rates = get_acceptance_rates(origin_code, asylum_code)
    if not rates:
        return None
    return rates[-1]


# ── Population figures ────────────────────────────────────────────────────────

@dataclass
class PopulationFigure:
    coo: str
    coa: str
    year: int
    refugees: int
    asylum_seekers: int
    idps: int
    stateless: int
    total: int


def get_population(
    origin_code: str,
    asylum_code: str,
    year: Optional[int] = None,
) -> list[PopulationFigure]:
    """Get population stock figures for an origin × asylum pair."""
    pop = _load("population")
    origin_code = origin_code.upper()
    asylum_code = asylum_code.upper()
    results = []

    for row in pop:
        if (
            row.get("coo_code", "").upper() != origin_code
            or row.get("coa_code", "").upper() != asylum_code
        ):
            continue
        row_year = int(row.get("year", 0))
        if year and row_year != year:
            continue

        refugees       = int(row.get("refugees", 0) or 0)
        asylum_seekers = int(row.get("asylum_seekers", 0) or 0)
        idps           = int(row.get("idps", 0) or 0)
        stateless      = int(row.get("stateless", 0) or 0)

        results.append(PopulationFigure(
            coo=origin_code,
            coa=asylum_code,
            year=row_year,
            refugees=refugees,
            asylum_seekers=asylum_seekers,
            idps=idps,
            stateless=stateless,
            total=refugees + asylum_seekers,
        ))

    return sorted(results, key=lambda r: r.year)


# ── Applications ──────────────────────────────────────────────────────────────

def get_application_volume(
    origin_code: str,
    asylum_code: str,
    year_from: int = 2018,
) -> list[dict]:
    """How many people from origin X applied in asylum country Y per year."""
    apps = _load("asylum-applications")
    origin_code = origin_code.upper()
    asylum_code = asylum_code.upper()
    results = []

    for row in apps:
        if (
            row.get("coo_code", "").upper() != origin_code
            or row.get("coa_code", "").upper() != asylum_code
        ):
            continue
        year = int(row.get("year", 0))
        if year < year_from:
            continue
        results.append({
            "year": year,
            "new_applications": int(row.get("applied", 0) or 0),
            "pending_start": int(row.get("asylum_seekers", 0) or 0),
        })

    return sorted(results, key=lambda r: r["year"])


# ── IDP context ───────────────────────────────────────────────────────────────

def get_idp_context(country_code: str, year: Optional[int] = None) -> list[dict]:
    """Internal displacement figures for an origin country."""
    idmc = _load("idmc")
    country_code = country_code.upper()
    results = []

    for row in idmc:
        if row.get("coo_code", "").upper() != country_code:
            continue
        row_year = int(row.get("year", 0))
        if year and row_year != year:
            continue
        results.append({
            "year": row_year,
            "idps_conflict": int(row.get("idps_conflict", 0) or 0),
            "idps_disasters": int(row.get("idps_disasters", 0) or 0),
            "total_idps": int(row.get("idps_conflict", 0) or 0) + int(row.get("idps_disasters", 0) or 0),
        })

    return sorted(results, key=lambda r: r["year"])


# ── Resettlement ──────────────────────────────────────────────────────────────

def get_resettlement(origin_code: str, year_from: int = 2018) -> list[dict]:
    """How many people from origin X were resettled globally."""
    solutions = _load("solutions")
    origin_code = origin_code.upper()
    results = []

    for row in solutions:
        if row.get("coo_code", "").upper() != origin_code:
            continue
        year = int(row.get("year", 0))
        if year < year_from:
            continue
        resettled = int(row.get("resettlement", 0) or 0)
        if resettled > 0:
            results.append({
                "year": year,
                "coa": row.get("coa_code", ""),
                "resettled": resettled,
            })

    return sorted(results, key=lambda r: r["year"])


# ── Footnotes / data quality ──────────────────────────────────────────────────

def get_footnotes(country_code: str) -> list[str]:
    """Return any data quality notes for a country."""
    try:
        notes = _load("footnotes")
    except DataNotAvailableError:
        return []
    country_code = country_code.upper()
    return [
        row.get("note", "")
        for row in notes
        if row.get("coa_code", "").upper() == country_code
        or row.get("coo_code", "").upper() == country_code
        if row.get("note")
    ]


# ── Composite: full country profile for Refuge ───────────────────────────────

@dataclass
class CountryProfile:
    """Everything Refuge needs about a potential asylum country for a given origin."""
    country: CountryInfo
    latest_acceptance_rate: Optional[AcceptanceRate]
    application_trend: list[dict]          # last 5 years of applications
    current_population: Optional[PopulationFigure]
    origin_idp_context: list[dict]         # IDP figures for origin country
    resettlement_available: bool
    data_footnotes: list[str]


def build_country_profile(
    origin_code: str,
    asylum_code: str,
) -> CountryProfile:
    """
    Build a full profile for asylum_code as a destination for someone from origin_code.
    Used by the country_lookup agent tool.
    Raises DataNotAvailableError if essential data is missing.
    """
    country = get_country(asylum_code)
    acceptance = latest_acceptance_rate(origin_code, asylum_code)
    apps = get_application_volume(origin_code, asylum_code)[-5:]  # last 5 years
    pop_series = get_population(origin_code, asylum_code)
    current_pop = pop_series[-1] if pop_series else None
    idp = get_idp_context(origin_code)[-3:]  # last 3 years
    resettlement = get_resettlement(origin_code)
    footnotes = get_footnotes(asylum_code)

    return CountryProfile(
        country=country,
        latest_acceptance_rate=acceptance,
        application_trend=apps,
        current_population=current_pop,
        origin_idp_context=idp,
        resettlement_available=len(resettlement) > 0,
        data_footnotes=footnotes,
    )
