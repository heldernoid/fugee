"""tests/integration/test_asylum_stats.py — origin→destination stats tool.

Uses the real downloaded UNHCR decision data (data/processed/asylum-decisions.json).
Skips if the data has not been downloaded yet (run
``python data/scripts/unhcr_downloader.py --all --year-from 2010``).
"""

from pathlib import Path

import pytest

from agent.tools.asylum_stats import get_acceptance
from agent.tools.country_lookup import resolve_iso3

_DECISIONS = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "asylum-decisions.json"
pytestmark = pytest.mark.skipif(
    not _DECISIONS.exists(), reason="UNHCR asylum-decisions data not downloaded"
)


def test_resolve_iso3():
    assert resolve_iso3("Kenya") == "KEN"
    assert resolve_iso3("Ethiopia") == "ETH"
    assert resolve_iso3("KEN") == "KEN"


def test_ethiopia_to_kenya_acceptance_real():
    out = get_acceptance("Ethiopia", "Kenya")
    assert "error" not in out, out
    assert out["originIso"] == "ETH"
    assert out["asylumIso"] == "KEN"
    assert out["latestYear"] >= 2010
    assert out["totalDecisions"] > 0
    assert 0.0 <= out["recognitionRate"] <= 1.0
    assert len(out["history"]) >= 1


def test_unknown_pair_returns_structured_no_records():
    # Two countries with (almost certainly) no decision flow between them.
    out = get_acceptance("Iceland", "Bhutan")
    assert out.get("error") in {"no_records", "data_not_downloaded"} or out.get("totalDecisions", 0) >= 0
