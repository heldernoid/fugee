"""tests/unit/test_country_lookup.py — country_lookup tool (T043 / SC-026).

Offline: reads the committed curated data. Kenya must report UNHCR presence and
a positive processing time; an invented country must return a structured
not_found error (never an exception, never fabricated data).
"""

import asyncio

from agent.tools.country_lookup import country_lookup_tool, lookup_country


def test_kenya_has_unhcr_presence_and_processing_time():
    rec = lookup_country("Kenya")
    assert rec.get("unhcrPresence") is True
    assert isinstance(rec.get("processingTimeMonths"), (int, float))
    assert rec["processingTimeMonths"] > 0
    assert rec["country"] == "Kenya"
    assert rec["primaryLanguage"]  # has a primary language
    assert rec["legalAidOrgs"]     # has at least one legal-aid org


def test_lookup_by_iso3():
    rec = lookup_country("KEN")
    assert rec["country"] == "Kenya"


def test_invented_country_returns_not_found_not_exception():
    rec = lookup_country("Wakanda")
    assert rec.get("error") == "not_found"
    assert "country" in rec


def test_no_fabricated_pending_stats():
    # The curated fallback marks unenriched stats as "PENDING"; the tool must
    # surface that as missing (None), not pass the literal sentinel through.
    rec = lookup_country("Kenya")
    assert rec["acceptanceRate"] != "PENDING"


def test_tool_execute_is_async_and_matches_core():
    rec = asyncio.run(country_lookup_tool.execute({"country": "Kenya"}))
    assert rec["country"] == "Kenya"
    assert rec["unhcrPresence"] is True
