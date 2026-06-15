"""
UNHCR Data Refresh Script
==========================
Run this to update the local UNHCR data cache with the latest figures.

Schedule: run once after the hackathon, then annually (UNHCR updates mid-year).
For nowcasting: run monthly if needed.

Usage
-----
  python3 refresh_data.py              # refresh all annual endpoints
  python3 refresh_data.py --full       # re-download everything including raw
  python3 refresh_data.py --nowcast    # refresh only nowcasting (monthly data)
  python3 refresh_data.py --check      # check what data exists and how old it is

Output
------
  Prints a table of each endpoint, record count, last download date, staleness.
  Updates data/processed/*.json and data/processed/metadata.json.

Co-authored-by: Codex <noreply@openai.com>
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROC_DIR = Path(__file__).parent.parent / "processed"
DOWNLOADER = Path(__file__).parent / "unhcr_downloader.py"

# How many days before we consider data stale
STALE_DAYS = {
    "annual":  366,
    "monthly": 31,
}


def load_manifest() -> dict:
    p = PROC_DIR / "metadata.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def check_staleness():
    manifest = load_manifest()
    downloads = {d["endpoint"]: d for d in manifest.get("downloads", [])}

    print(f"\n{'Endpoint':<25} {'Records':>8}  {'Downloaded':<22}  {'Status'}")
    print("-" * 75)

    from unhcr_downloader import ENDPOINTS  # noqa: E402
    now = datetime.now(timezone.utc)

    for name, cfg in ENDPOINTS.items():
        if name in downloads:
            d = downloads[name]
            ts = datetime.fromisoformat(d["downloaded_at"].replace("Z", "+00:00"))
            age_days = (now - ts).days
            threshold = STALE_DAYS.get(cfg["refresh_frequency"], 366)
            status = "✅ fresh" if age_days <= threshold else f"⚠️  stale ({age_days}d)"
            records = d.get("records", "?")
            print(f"{name:<25} {records:>8}  {d['downloaded_at']:<22}  {status}")
        else:
            print(f"{name:<25} {'—':>8}  {'not downloaded':<22}  ❌ missing")
    print()


def run_downloader(args: list[str]):
    cmd = [sys.executable, str(DOWNLOADER)] + args
    print(f"Running: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Refresh UNHCR data for Fugee.")
    parser.add_argument("--full",     action="store_true", help="Re-download all endpoints")
    parser.add_argument("--nowcast",  action="store_true", help="Refresh nowcasting only")
    parser.add_argument("--check",    action="store_true", help="Check data freshness and exit")
    args = parser.parse_args()

    if args.check:
        check_staleness()
        return

    if args.nowcast:
        run_downloader(["--endpoint", "nowcasting"])
        return

    if args.full:
        run_downloader(["--all"])
        return

    # Default: refresh annual endpoints + check staleness after
    check_staleness()
    print("Refreshing annual endpoints (this may take several minutes)...\n")
    rc = run_downloader(["--refresh"])
    if rc == 0:
        print("\nRefresh complete. Updated manifest:\n")
        check_staleness()
    else:
        print(f"\nRefresh exited with code {rc}. Check logs above.")


if __name__ == "__main__":
    main()
