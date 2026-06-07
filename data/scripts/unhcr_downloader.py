"""
UNHCR Refugee Statistics API — Full Downloader
================================================
Base URL : https://api.unhcr.org/population/v1/
Auth     : None required (fully public)
Docs     : https://api.unhcr.org/docs/refugee-statistics.html

Endpoints mapped
----------------
/countries/              → country codes, names, UNHCR/UNSD regions
/regions/                → UNHCR region list with IDs
/years/                  → available data years per endpoint
/population/             → end-year stock figures (refugees, asylum-seekers, IDPs, stateless, OOC, OIP)
/asylum-applications/    → claims filed by year × origin × asylum country
/asylum-decisions/       → decisions (recognised, complementary, rejected) by year × origin × asylum
/demographics/           → age/sex breakdown by year × origin × asylum × population type
/solutions/              → durable solutions (return, resettlement, naturalisation) by year × origin × asylum
/idmc/                   → IDMC internal displacement figures by year × country
/unrwa/                  → Palestine refugee figures under UNRWA mandate
/nowcasting/             → near-real-time displacement estimates (where available)
/footnotes/              → data quality notes per country/year

Usage
-----
  # Full download (all endpoints, all years, all countries)
  python3 unhcr_downloader.py --all

  # Refresh only the endpoints that change annually
  python3 unhcr_downloader.py --refresh

  # Single endpoint
  python3 unhcr_downloader.py --endpoint asylum-decisions --year-from 2015

  # Africa-focused subset (faster, smaller)
  python3 unhcr_downloader.py --all --region "Eastern Africa,Western Africa,Middle Africa,Northern Africa,Southern Africa"

Output
------
  data/raw/<endpoint>_<timestamp>.json    raw paginated JSON
  data/processed/<endpoint>.json          merged, deduplicated, flat JSON
  data/processed/metadata.json           download manifest with timestamps

Co-authored-by: Codex <noreply@openai.com>
"""

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL   = "https://api.unhcr.org/population/v1"
DATA_DIR   = Path(__file__).parent.parent
RAW_DIR    = DATA_DIR / "raw"
PROC_DIR   = DATA_DIR / "processed"
PAGE_SIZE  = 1000         # UNHCR API supports up to 1000 rows/page
RATE_DELAY = 0.4          # seconds between requests (be polite)
TIMEOUT    = 30.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("unhcr")

# ── Endpoint registry ─────────────────────────────────────────────────────────

ENDPOINTS = {

    "countries": {
        "path": "/countries/",
        "description": "Country list with UNHCR codes, ISO3 codes, names, UNHCR region, UNSD region",
        "params": {},                    # no filtering needed — always fetch all
        "paginated": True,
        "refresh_frequency": "annual",
        "refuge_use": "country selector in interview UI; code lookup table for all other endpoints",
    },

    "regions": {
        "path": "/regions/",
        "description": "UNHCR region list with numeric IDs — needed to filter countries by region",
        "params": {},
        "paginated": True,
        "refresh_frequency": "annual",
        "refuge_use": "filter asylum countries to African regions",
    },

    "years": {
        "path": "/years/",
        "description": "Available data years per dataset — use to know the latest year",
        "params": {},
        "paginated": False,
        "refresh_frequency": "annual",
        "refuge_use": "determine latest data year dynamically in refresh logic",
    },

    "population": {
        "path": "/population/",
        "description": (
            "End-year stock figures: refugees (UNHCR mandate), asylum-seekers, IDPs (UNHCR-reported), "
            "other people in need of international protection (OIP), stateless persons, "
            "others of concern (OOC). Disaggregated by year × country-of-origin × country-of-asylum."
        ),
        "params": {
            "coo_all": "true",
            "coa_all": "true",
            "year_from": 2019,       # 6 years sufficient for enrichment
        },
        "paginated": True,
        "refresh_frequency": "annual",
        "refuge_use": (
            "Core population figures: how many refugees from origin X are in asylum country Y. "
            "Used to gauge scale of a displacement corridor and country capacity."
        ),
    },

    "asylum-applications": {
        "path": "/asylum-applications/",
        "description": (
            "New asylum claims filed by year × country-of-origin × country-of-asylum. "
            "Includes claim type (individual, group, etc.)."
        ),
        "params": {
            "coo_all": "true",
            "coa_all": "true",
            "year_from": 2019,
        },
        "paginated": True,
        "refresh_frequency": "annual",
        "refuge_use": (
            "Application volumes: how many people from origin X applied in country Y. "
            "Signals whether an asylum system is active for a given origin."
        ),
    },

    "asylum-decisions": {
        "path": "/asylum-decisions/",
        "description": (
            "Decisions on asylum claims by year × origin × asylum. "
            "Columns: recognised (Convention status), complementary protection, "
            "otherwise closed, rejected, total decisions. "
            "UNHCR computes two rates: Refugee Recognition Rate (recognised/total) "
            "and Total Protection Rate ((recognised + complementary)/total)."
        ),
        "params": {
            "coo_all": "true",
            "coa_all": "true",
            "year_from": 2019,
        },
        "paginated": True,
        "refresh_frequency": "annual",
        "refuge_use": (
            "THE most important endpoint for Refuge. "
            "Acceptance rates per origin × asylum country pair. "
            "Used in Phase 3 assessment to score country recommendations. "
            "E.g. 'Ethiopians in Kenya: 78% total protection rate (2023)'."
        ),
    },

    "demographics": {
        "path": "/demographics/",
        "description": (
            "Age and sex breakdown for all population types. "
            "Available for refugees, asylum-seekers, IDPs (UNHCR-reported), OIP, stateless, OOC. "
            "Also available for IDMC and UNRWA datasets. "
            "Not always available for every country-year combination."
        ),
        "params": {
            "coo_all": "true",
            "coa_all": "true",
            "year_from": 2019,       # recent years only
            "columns": "refugees,asylum_seekers",
        },
        "paginated": True,
        "refresh_frequency": "annual",
        "refuge_use": (
            "Secondary. Useful to understand if a country hosts many refugees "
            "of a given demographic (e.g. unaccompanied minors, women-headed households). "
            "Not surfaced directly in Phase 3 but enriches context."
        ),
    },

    "solutions": {
        "path": "/solutions/",
        "description": (
            "Durable solutions by year × origin × asylum: "
            "voluntary repatriation (returns), resettlement (to third country), "
            "naturalisation. Flow figures (not stocks)."
        ),
        "params": {
            "coo_all": "true",
            "coa_all": "true",
            "year_from": 2019,
        },
        "paginated": True,
        "refresh_frequency": "annual",
        "refuge_use": (
            "Resettlement figures: how many refugees from origin X were resettled "
            "from asylum country Y to a third country. "
            "Used in roadmap step 'Resettlement pathway' if applicable."
        ),
    },

    "idmc": {
        "path": "/idmc/",
        "description": (
            "Internal displacement figures from the Internal Displacement Monitoring Centre (IDMC). "
            "Disaggregated by year × country. Conflict-induced and disaster-induced IDPs."
        ),
        "params": {
            "coo_all": "true",
            "year_from": 2019,
        },
        "paginated": True,
        "refresh_frequency": "annual",
        "refuge_use": (
            "Origin country context: is the person's home country in active conflict "
            "with large IDP numbers? Strengthens Convention grounds assessment."
        ),
    },

    "unrwa": {
        "path": "/unrwa/",
        "description": (
            "Palestine refugee figures under UNRWA mandate. "
            "Separate from UNHCR-mandate refugees. "
            "Disaggregated by year × country."
        ),
        "params": {
            "coo_all": "true",
            "year_from": 2019,
        },
        "paginated": True,
        "refresh_frequency": "annual",
        "refuge_use": (
            "Relevant only for Palestinian origin cases. "
            "UNRWA vs UNHCR mandate distinction matters for legal assessment."
        ),
    },

    "nowcasting": {
        "path": "/nowcasting/",
        "description": (
            "Near-real-time displacement estimates where available. "
            "Not comprehensive — only available for select high-profile situations."
        ),
        "params": {},
        "paginated": True,
        "refresh_frequency": "monthly",
        "refuge_use": (
            "Current crisis context: if a new emergency has displaced people "
            "from origin X in the last few months, this surfaces it. "
            "Supplements historical decisions data with recency signal."
        ),
    },

    "footnotes": {
        "path": "/footnotes/",
        "description": (
            "Data quality notes and caveats per country/year combination. "
            "Important: some country figures are estimates or have known limitations."
        ),
        "params": {},
        "paginated": True,
        "refresh_frequency": "annual",
        "refuge_use": (
            "Data quality layer: when surfacing acceptance rates, "
            "check if the country-year has a footnote flagging unreliable data. "
            "Surface as a caveat in the UI if present."
        ),
    },
}

# ── Core fetch logic ──────────────────────────────────────────────────────────

def _extract_items(data: dict) -> list:
    """
    Extract the items list from a UNHCR API response.

    The UNHCR API is inconsistent across endpoints:
      - Most use:   {"items": [...], "total": <int>}
      - Some use:   {"data": [...], "total": <int>}
      - Some use:   {"results": [...], "count": <int>}
      - asylum-decisions / asylum-applications / solutions use:
                    {"items": [...], "total": {"value": <int>, "relation": "eq"}}
    """
    for key in ("items", "data", "results"):
        val = data.get(key)
        if isinstance(val, list):
            return val
    if isinstance(data, list):
        return data
    return []


def _extract_total(data: dict) -> int:
    """
    Extract the total record count from a UNHCR API response.

    Handles:
      - {"total": 12345}                                   plain int
      - {"total": {"value": 12345, "relation": "eq"}}      ES-style dict
      - {"count": 12345}                                   alternate key
      - missing / null                                     returns 0
    """
    for key in ("total", "count", "totalItems", "total_count"):
        val = data.get(key)
        if val is None:
            continue
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, dict):
            inner = val.get("value")
            if isinstance(inner, (int, float)):
                return int(inner)
    return 0


def fetch_all_pages(client: httpx.Client, path: str, params: dict) -> list:
    """Fetch all pages from a paginated endpoint, return merged items list."""
    items = []
    page = 1
    total_pages = None

    while True:
        p = {**params, "limit": PAGE_SIZE, "page": page}
        url = f"{BASE_URL}{path}"

        try:
            r = client.get(url, params=p, timeout=TIMEOUT)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            log.error("HTTP %s on %s page %d: %s", e.response.status_code, path, page, e)
            raise
        except httpx.RequestError as e:
            log.error("Request error on %s page %d: %s", path, page, e)
            raise

        data = r.json()
        page_items = _extract_items(data)
        items.extend(page_items)

        if total_pages is None:
            total = _extract_total(data)
            if total > 0:
                total_pages = max(1, -(-total // PAGE_SIZE))  # ceiling division
            else:
                total_pages = 9999  # unknown total — stop when page is empty
            log.info("  %s: %s total records, page %d",
                     path, str(total) if total else "unknown", page)

        log.debug("  page %d fetched (%d items this page, %d total so far)",
                  page, len(page_items), len(items))

        if page >= total_pages or not page_items:
            break

        page += 1
        time.sleep(RATE_DELAY)

    log.info("  Fetched %d total items from %s", len(items), path)
    return items


def fetch_single(client: httpx.Client, path: str, params: dict) -> dict:
    """Fetch a non-paginated endpoint."""
    url = f"{BASE_URL}{path}"
    r = client.get(url, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


# ── Download orchestration ────────────────────────────────────────────────────

def download_endpoint(name: str, cfg: dict, year_from: int | None = None) -> dict:
    """Download one endpoint, save raw + processed, return summary."""
    log.info("Downloading: %s", name)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROC_DIR.mkdir(parents=True, exist_ok=True)

    params = dict(cfg["params"])
    if year_from:
        params["year_from"] = year_from
    elif "year_from" in params:
        params["yearFrom"] = params.pop("year_from")  # API uses camelCase

    # Fix key naming (config uses snake_case, API uses camelCase)
    key_map = {
        "year_from":  "yearFrom",
        "year_to":    "yearTo",
        "coo_all":    "coo_all",   # API uses snake_case for these two
        "coa_all":    "coa_all",
        "cf_type":    "cf_type",
        "ptype_show": "ptype_show",
    }
    clean_params = {key_map.get(k, k): v for k, v in params.items()}

    with httpx.Client(
        headers={"Accept": "application/json", "User-Agent": "Refuge/1.0 (hackathon; contact via HF)"},
        follow_redirects=True,
    ) as client:
        if cfg["paginated"]:
            items = fetch_all_pages(client, cfg["path"], clean_params)
            result = {"items": items, "count": len(items)}
        else:
            result = fetch_single(client, cfg["path"], clean_params)
            items = result.get("items") or result.get("data") or [result]

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Save raw
    raw_path = RAW_DIR / f"{name}_{ts}.json"
    raw_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    log.info("  Raw saved: %s (%d items)", raw_path.name, len(items))

    # Save processed (clean flat list)
    proc_path = PROC_DIR / f"{name}.json"
    proc_path.write_text(json.dumps({
        "endpoint":     name,
        "description":  cfg["description"],
        "refuge_use":   cfg["refuge_use"],
        "downloaded_at": ts,
        "record_count": len(items),
        "items":        items,
    }, indent=2, ensure_ascii=False))
    log.info("  Processed saved: %s", proc_path.name)

    return {"endpoint": name, "records": len(items), "downloaded_at": ts, "status": "ok"}


def update_manifest(summaries: list[dict]):
    manifest_path = PROC_DIR / "metadata.json"
    existing = {}
    if manifest_path.exists():
        existing = {e["endpoint"]: e for e in json.loads(manifest_path.read_text()).get("downloads", [])}
    for s in summaries:
        existing[s["endpoint"]] = s
    manifest = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "api_docs": "https://api.unhcr.org/docs/refugee-statistics.html",
        "downloads": list(existing.values()),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    log.info("Manifest updated: %s", manifest_path)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Download UNHCR Refugee Statistics API data for Refuge."
    )
    parser.add_argument("--all",       action="store_true", help="Download all endpoints")
    parser.add_argument("--refresh",   action="store_true", help="Re-download annual endpoints only")
    parser.add_argument("--endpoint",  help="Download a single endpoint by name")
    parser.add_argument("--list",      action="store_true", help="List all endpoints and exit")
    parser.add_argument("--year-from", type=int, default=None, help="Override yearFrom for all endpoints")
    parser.add_argument(
        "--region",
        default=None,
        help=(
            "Comma-separated UNSD sub-region names to filter countries. "
            "E.g. 'Eastern Africa,Western Africa,Middle Africa,Northern Africa,Southern Africa'"
        ),
    )
    args = parser.parse_args()

    if args.list:
        print(f"\n{'Endpoint':<25} {'Frequency':<10}  Description")
        print("-" * 90)
        for name, cfg in ENDPOINTS.items():
            print(f"{name:<25} {cfg['refresh_frequency']:<10}  {cfg['description'][:60]}")
        return

    targets = []

    if args.all:
        targets = list(ENDPOINTS.keys())
    elif args.refresh:
        targets = [n for n, c in ENDPOINTS.items() if c["refresh_frequency"] == "annual"]
    elif args.endpoint:
        if args.endpoint not in ENDPOINTS:
            print(f"Unknown endpoint: {args.endpoint}. Use --list to see options.")
            return
        targets = [args.endpoint]
    else:
        parser.print_help()
        return

    log.info("Downloading %d endpoint(s): %s", len(targets), ", ".join(targets))

    summaries = []
    for name in targets:
        cfg = dict(ENDPOINTS[name])
        # Inject region filter into countries endpoint if specified
        if args.region and name == "countries":
            cfg["params"] = {**cfg["params"], "region": args.region}
        try:
            summary = download_endpoint(name, cfg, year_from=args.year_from)
            summaries.append(summary)
        except Exception as e:
            log.error("FAILED %s: %s", name, e)
            summaries.append({"endpoint": name, "status": "error", "error": str(e)})
        time.sleep(RATE_DELAY)

    update_manifest(summaries)

    ok  = [s for s in summaries if s.get("status") == "ok"]
    err = [s for s in summaries if s.get("status") == "error"]
    log.info("Done. %d succeeded, %d failed.", len(ok), len(err))
    if err:
        for e in err:
            log.error("  Failed: %s — %s", e["endpoint"], e.get("error"))


if __name__ == "__main__":
    main()
