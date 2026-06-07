"""
UNHCR Targeted Enrichment Downloader
=====================================
Downloads ONLY the data needed to fill PENDING fields in countries.json.
Instead of coa_all=true (hundreds of pages), fetches per country-of-asylum.

Endpoints fetched per country:
  /asylum-decisions/      → acceptance_rate, total_protection_rate
  /asylum-applications/   → applications_last_year
  /population/            → refugee_population_total

Strategy
--------
1. Fetch /countries/ to build ISO3 → UNHCR-code mapping
2. For each country in countries.json, fire 3 targeted requests
3. Aggregate, compute rates, write enriched file

Time estimate: ~152 countries × 3 endpoints × ~0.5s = ~4 min
vs old approach: 400+ pages × 4s = 30+ min

Usage
-----
  python3 enrich_downloader.py
  python3 enrich_downloader.py --output ../../specs/data/countries_enriched.json
  python3 enrich_downloader.py --dry-run   # print plan, no requests

Co-authored-by: Codex <noreply@openai.com>
"""

import argparse
import json
import logging
import time
from pathlib import Path

import httpx

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL        = "https://api.unhcr.org/population/v1"
RATE_DELAY      = 0.4       # seconds between requests
TIMEOUT         = 30.0
YEAR_FROM       = 2019      # only recent years needed for enrichment
DATA_DIR        = Path(__file__).parent.parent
COUNTRIES_JSON  = DATA_DIR.parent / "specs" / "data" / "countries.json"
ENRICHED_JSON   = DATA_DIR.parent / "specs" / "data" / "countries_enriched.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("enrich")

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Refuge/1.0 (HuggingFace hackathon; humanitarian AI tool)",
}

# ── Step 1: Build ISO3 → UNHCR code mapping ───────────────────────────────────

def fetch_unhcr_code_map(client: httpx.Client) -> dict[str, str]:
    """
    Returns {iso3: unhcr_code} by fetching /countries/.
    UNHCR uses its own 3-letter codes which often differ from ISO3
    (e.g. DEU→GFR, GMB→GAM, CIV→ICO, ZMB→ZAM).
    """
    log.info("Fetching UNHCR country code mapping...")
    mapping = {}
    page = 1
    while True:
        r = client.get(
            f"{BASE_URL}/countries/",
            params={"limit": 1000, "page": page},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        items = data.get("items") or data.get("data") or []
        for item in items:
            # The /countries/ endpoint exposes ISO3 as "iso" (and "code");
            # older API shapes used iso3/coo_iso/coa_iso.
            iso3 = (
                item.get("iso3") or item.get("iso")
                or item.get("coo_iso") or item.get("coa_iso")
            )
            code = item.get("code") or item.get("coo") or item.get("coa")
            if iso3 and code:
                mapping[iso3.upper()] = code.upper()
        total = data.get("total", 0)
        if isinstance(total, dict):
            total = total.get("value", 0)
        max_pages = max(1, -(-int(total) // 1000)) if total else 1
        if page >= max_pages or not items:
            break
        page += 1
        time.sleep(RATE_DELAY)

    log.info("  Got %d country code mappings", len(mapping))
    return mapping


# ── Step 2: Fetch data per country ────────────────────────────────────────────

def _items(data: dict) -> list:
    for key in ("items", "data", "results"):
        val = data.get(key)
        if isinstance(val, list):
            return val
    return []


def fetch_coa(client: httpx.Client, endpoint: str, unhcr_code: str) -> list:
    """Fetch all pages for a given country-of-asylum code."""
    all_items = []
    page = 1
    total_pages = None

    while True:
        params = {
            "coa": unhcr_code,
            "yearFrom": YEAR_FROM,
            "limit": 1000,
            "page": page,
        }
        try:
            r = client.get(f"{BASE_URL}/{endpoint}/", params=params, timeout=TIMEOUT)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            log.warning("  HTTP %d for %s/%s: %s", e.response.status_code, endpoint, unhcr_code, e)
            return all_items
        except httpx.RequestError as e:
            log.warning("  Request error for %s/%s: %s", endpoint, unhcr_code, e)
            return all_items

        data = r.json()
        page_items = _items(data)
        all_items.extend(page_items)

        if total_pages is None:
            total = data.get("total", 0)
            if isinstance(total, dict):
                total = total.get("value", 0)
            total_pages = max(1, -(-int(total) // 1000)) if total else 1

        if page >= total_pages or not page_items:
            break
        page += 1
        time.sleep(RATE_DELAY)

    return all_items


# ── Step 3: Compute stats from raw data ──────────────────────────────────────

def compute_stats(
    decisions: list,
    applications: list,
    population: list,
    iso3: str,
) -> dict:
    """
    Compute enrichment stats for one country-of-asylum.
    Returns dict matching the stats schema in countries.json.
    """

    # ── Asylum decisions: find most recent year with enough data ──────────────
    # Group by year, sum across all origins
    by_year: dict[int, dict] = {}
    for row in decisions:
        year = row.get("year")
        if not isinstance(year, int):
            continue
        y = by_year.setdefault(year, {
            "recognized": 0, "complementary": 0,
            "otherwise_closed": 0, "rejected": 0, "total": 0
        })
        def _int(v):
            try: return int(v) if v not in (None, "", "-") else 0
            except: return 0
        y["recognized"]        += _int(row.get("dec_recognized") or row.get("decisions_recognized"))
        # Complementary protection is exposed as "dec_other" in the API.
        y["complementary"]     += _int(row.get("dec_other") or row.get("dec_complementary") or row.get("decisions_complementary"))
        y["otherwise_closed"]  += _int(row.get("dec_closed") or row.get("decisions_closed"))
        y["rejected"]          += _int(row.get("dec_rejected") or row.get("decisions_rejected"))
        y["total"]             += _int(row.get("dec_total") or row.get("decisions_total"))

    # Pick most recent year with at least 10 total decisions (avoid noise)
    acceptance_rate = "PENDING"
    total_protection_rate = "PENDING"
    data_year = "PENDING"

    for year in sorted(by_year.keys(), reverse=True):
        y = by_year[year]
        if y["total"] >= 10:
            rec  = y["recognized"]
            prot = y["recognized"] + y["complementary"]
            tot  = y["total"]
            acceptance_rate       = round(rec  / tot, 4) if tot else 0.0
            total_protection_rate = round(prot / tot, 4) if tot else 0.0
            data_year             = year
            break

    # ── Applications: most recent year total ─────────────────────────────────
    app_by_year: dict[int, int] = {}
    for row in applications:
        year = row.get("year")
        if not isinstance(year, int):
            continue
        def _int(v):
            try: return int(v) if v not in (None, "", "-") else 0
            except: return 0
        app_by_year[year] = app_by_year.get(year, 0) + _int(
            row.get("applied") or row.get("applications_new") or row.get("apps_new") or 0
        )

    applications_last_year = "PENDING"
    if app_by_year:
        latest_app_year = max(app_by_year.keys())
        applications_last_year = app_by_year[latest_app_year]
        # Use this year as data_year if we didn't get one from decisions
        if data_year == "PENDING":
            data_year = latest_app_year

    # ── Population: total refugee stock (most recent year) ───────────────────
    pop_by_year: dict[int, int] = {}
    for row in population:
        year = row.get("year")
        if not isinstance(year, int):
            continue
        def _int(v):
            try: return int(v) if v not in (None, "", "-") else 0
            except: return 0
        pop_by_year[year] = pop_by_year.get(year, 0) + _int(
            row.get("refugees") or 0
        )

    refugee_population_total = "PENDING"
    if pop_by_year:
        refugee_population_total = pop_by_year[max(pop_by_year.keys())]

    return {
        "acceptance_rate_recent":       acceptance_rate,
        "total_protection_rate_recent": total_protection_rate,
        "applications_last_year":       applications_last_year,
        "refugee_population_total":     refugee_population_total,
        "data_year":                    data_year,
    }


# ── Step 4: Main enrichment loop ─────────────────────────────────────────────

def load_countries() -> tuple[dict, list]:
    """Load countries.json, return (data, list_of_iso3_to_enrich)."""
    data = json.loads(COUNTRIES_JSON.read_text(encoding="utf-8"))
    targets = list(data.get("signatories", {}).keys())
    # Also enrich non-signatories that have UNHCR resettlement pipelines
    for iso3, entry in data.get("non_signatories", {}).items():
        if entry.get("tier") in ("non_signatory_resettlement_pipeline", "non_signatory_viable_temporary"):
            targets.append(iso3)
    return data, targets


def enrich(dry_run: bool = False, output_path: Path = ENRICHED_JSON):
    data, targets = load_countries()
    log.info("Countries to enrich: %d", len(targets))

    if dry_run:
        log.info("DRY RUN — no requests will be made")
        log.info("Would fire: %d countries × 3 endpoints = %d requests",
                 len(targets), len(targets) * 3)
        log.info("Estimated time: ~%.0f seconds (~%.1f min)",
                 len(targets) * 3 * RATE_DELAY, len(targets) * 3 * RATE_DELAY / 60)
        return

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:

        # Step 1: get code mapping
        code_map = fetch_unhcr_code_map(client)
        time.sleep(RATE_DELAY)

        # Step 2: enrich each country
        enriched = 0
        skipped  = 0

        for i, iso3 in enumerate(targets, 1):
            unhcr_code = code_map.get(iso3)
            if not unhcr_code:
                log.warning("[%d/%d] %s — no UNHCR code found, skipping",
                            i, len(targets), iso3)
                skipped += 1
                continue

            log.info("[%d/%d] %s (UNHCR: %s)", i, len(targets), iso3, unhcr_code)

            decisions    = fetch_coa(client, "asylum-decisions",    unhcr_code)
            time.sleep(RATE_DELAY)
            applications = fetch_coa(client, "asylum-applications", unhcr_code)
            time.sleep(RATE_DELAY)
            population   = fetch_coa(client, "population",          unhcr_code)
            time.sleep(RATE_DELAY)

            stats = compute_stats(decisions, applications, population, iso3)

            # Write into the right section
            if iso3 in data["signatories"]:
                data["signatories"][iso3]["stats"] = stats
            elif iso3 in data["non_signatories"]:
                data["non_signatories"][iso3]["stats"] = stats

            enriched += 1

            # Log what we got
            log.info(
                "  → prot_rate=%.0f%% apps=%s refugees=%s year=%s",
                (stats["total_protection_rate_recent"] * 100
                 if isinstance(stats["total_protection_rate_recent"], float) else 0),
                stats["applications_last_year"],
                stats["refugee_population_total"],
                stats["data_year"],
            )

    # Step 3: write enriched file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    log.info(
        "Done. %d enriched, %d skipped. Written to %s",
        enriched, skipped, output_path
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fetch UNHCR stats for each country and enrich countries.json."
    )
    parser.add_argument(
        "--output", type=Path, default=ENRICHED_JSON,
        help=f"Output path (default: {ENRICHED_JSON})"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print plan and exit without making requests"
    )
    args = parser.parse_args()
    enrich(dry_run=args.dry_run, output_path=args.output)


if __name__ == "__main__":
    main()
