# CHANGELOG — Fugee

All notable changes to Fugee are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

Each release corresponds to a completed PLAN.md phase, signed off by the
human developer. Codex-attributed commits are tracked per release.

> **Hackathon build — June 5–15, 2026**
> Built with [OpenAI Codex](https://openai.com/codex) as primary coding agent.
> All Codex commits carry `Co-authored-by: Codex <noreply@openai.com>`.

---

## [Unreleased]

*Active development. See `specs/PLAN.md` for current phase and task status.*

### Stack Decision: Pure Python Agent Loop (June 2026)

> This decision was made early in the session and overrides the original
> `ARCHITECTURE.md` spec which called for a pi-agent-core (Node.js) subprocess.
> All spec files have been updated to reflect the final decision.

**Decision:** Port the pi-agent-core agent loop to Python. No Node.js, no
subprocess bridge, no NDJSON IPC. Single-process Gradio application.

**Rationale:**

The original spec called for a Python/Gradio frontend bridging to a Node.js
`pi-agent-core` runner via stdin/stdout NDJSON. After evaluation:

1. HF Spaces is hostile to subprocess spawning — lifecycle management, signal
   handling, and buffering in a sandboxed environment are non-trivial failure modes.
2. The pi-agent-core loop itself is ~300 lines of logic (while-loop, typed events,
   tool execution, steering queue). Porting to Python is a morning's work.
3. Python's `asyncio` and Gradio's `async` generator support make the loop
   integrate directly — no IPC layer, events flow straight to the UI.
4. The LLM provider layer (`@earendil-works/pi-ai`) was NOT ported — Python has
   better equivalents: `ollama` SDK (2 lines for local Ollama), `litellm` for
   multi-provider abstraction. No need to port 20-provider TS code.

**What was kept from pi-agent-core's design:**
- The while-loop structure with tool execution and event emission
- Typed event contracts (ported to Python dataclasses in `agent/events.py`)
- Steering queue (inject messages mid-run without interrupting the loop)
- Tool definition schema (ported to Python `TypedDict` / dataclass)

**What replaced Node equivalents:**

| Old (Node) | New (Python) |
|---|---|
| `agent/runner.js` | `agent/loop.py` |
| `agent/bridge.py` | *(removed — no IPC needed)* |
| `agent/package.json` | *(removed — no npm)* |
| `agent/tools/web_search.js` | `agent/tools/web_search.py` |
| `agent/tools/country_lookup.js` | `agent/tools/country_lookup.py` |
| `tests/unit/test_bridge_ping.py` | `tests/unit/test_loop_ping.py` |
| NDJSON event stream | Python `AsyncGenerator[AgentEvent, None]` |
| `vitest` | *(removed — pytest only)* |

### Pre-Implementation — Data Layer (June 2026)

> This work was completed before Phase 0 coding began. It establishes the
> country reference dataset and data pipeline that `country_lookup.js` (T036)
> depends on. No PLAN.md tasks are checked off yet — Phase 0 T001 is next.

#### What was researched and decided

**Convention signatory mapping.** The 1951 Refugee Convention and its 1967
Protocol have 149 states parties as of 2025 (UNHCR official count). We
mapped all 149, classified them into four tiers by asylum system quality, and
added 23 key non-signatory countries with alternative pathway guidance. The
final dataset covers 172 countries total.

**Two countries are formally signatories but listed in `non_signatories`:**
- China (acceded 1982) — near-0% recognition rate, forcibly returns North
  Korean defectors. Listed as `non_signatory_not_recommended` with a
  `note_on_classification` field explaining the anomaly.
- Russia (acceded 1992) — active war in Ukraine since 2022, hostile political
  environment. Same treatment.

**Tier system rationale:**
- Tier 1 (35 countries): Full entry — procedures, legal aid orgs, UNHCR
  office, step-by-step registration, required documents. Major active systems.
- Tier 2 (28 countries): Active system — moderate volume or significant for
  specific origin profiles.
- Tier 3 (54 countries): Functioning but low volume, primarily transit or
  origin. Summary entry with `strategic_note`.
- Tier 4 (29 countries): Signatory in name only — micro-states, collapsed
  states, or non-functional systems. Minimal entry; `warning` field added
  where dangerous (active war, slavery documented, etc.).

**Non-signatory tiers:**
- `non_signatory_viable_temporary` (1): UAE — Humanitarian Resident Permit
  (2025–2026), Green Residency, Golden Visa. Viable temporary stay while
  pursuing formal asylum elsewhere.
- `non_signatory_skilled_only` (5): Gulf states (excl. Kuwait) — formal
  employment required; no protection framework; kafala noted.
- `non_signatory_resettlement_pipeline` (5): Jordan, India, Malaysia,
  Indonesia, Thailand — UNHCR RSD active; value is third-country resettlement
  pipeline, not local integration.
- `non_signatory_not_recommended` (12): Kuwait, Iraq, Syria, Libya (EXTREME
  DANGER — slavery documented), Lebanon, Pakistan, Bangladesh, Cuba, Eritrea,
  Mongolia, China, Russia.

**Notable safety flags added:**
- Libya: `warning` field with EXTREME DANGER — active slavery and trafficking
  of migrants documented; EU-funded detention condemned.
- Active war countries (Sudan, South Sudan, Yemen, Ukraine, Mali, Burkina
  Faso, CAF, Burundi, Haiti, Venezuela): `warning` field + tier 4.
- Turkey: tier 1 but with prominent caveat — geographic limitation retained
  (only European-origin refugees get full Convention status; all others get
  conditional/subsidiary protection). Deportations increasing since 2023.

#### `specs/data/countries.json` — curated reference layer

**Schema** (full definition in `specs/data/README.md`):
```
{
  "_meta": { schema_version, sources, tier_system, enrichment_mapping },
  "signatories": {
    "<ISO3>": {
      name, iso3, flag, tier, region, unhcr_region,
      convention: { 1951, 1967, oau_1969, year, notes },
      asylum_system: {
        body, unhcr_present, unhcr_office, procedure,
        work_right, education_right, movement,
        processing_months: { min, max, typical },
        appeal, legal_aid, orgs, steps, docs_required
      },
      profile: { languages, secondary, hosts, integration, safety, economic_access },
      stats: {
        acceptance_rate_recent,        ← PENDING until enrich_downloader.py runs
        total_protection_rate_recent,  ← PENDING
        applications_last_year,        ← PENDING
        refugee_population_total,      ← PENDING
        data_year                      ← PENDING
      }
    }
  },
  "non_signatories": {
    "<ISO3>": {
      tier, convention, alternative_pathways, strategic_guidance,
      kafala?, warning?, languages, safety, economic_opportunity
    }
  }
}
```

All `stats` fields are `"PENDING"` in the committed file. They are populated
by running `data/scripts/enrich_downloader.py`, which produces
`specs/data/countries_enriched.json` (gitignored). `country_lookup.js` (T036)
loads the enriched file if present, falls back to the curated file if not.

**Data sources used to build the curated layer:**
- UNHCR States Parties list (official 149 count)
- UNHCR Refugee Statistics API (`/countries/` endpoint for UNHCR code mapping)
- AIDA (Asylum Information Database) — procedures, processing times, appeal
  paths for European countries
- UNHCR country pages — UNHCR office locations, presence, and contacts
- DWRAP (World Bank/UNHCR Joint Data Center) — secondary reference
- Country asylum authority websites — official body names per entry

#### `data/scripts/` — pipeline scripts

**`unhcr_downloader.py`** — full UNHCR API downloader.
- Fetches all 11 endpoints: `countries`, `regions`, `years`, `population`,
  `asylum-applications`, `asylum-decisions`, `demographics`, `solutions`,
  `idmc`, `unrwa`, `nowcasting`, `footnotes`.
- Two bugs were found and fixed:
  1. Three endpoints (`asylum-decisions`, `asylum-applications`, `solutions`)
     return `total` as an Elasticsearch-style dict `{"value": N, "relation": "eq"}`
     not a plain integer. `_extract_total()` helper was added to handle both.
  2. Endpoints without a `total` field defaulted to `total_pages=1` and
     silently truncated at 300 records. Fixed with a sentinel (9999) and
     stop-on-empty-page logic.
- Config: `PAGE_SIZE=1000` (API supports up to 1000), `yearFrom=2019` on all
  large endpoints (6 years is sufficient for enrichment; reduces `population`
  endpoint from ~463 pages to ~56).
- Output: `data/raw/<endpoint>_<timestamp>.json` (raw) +
  `data/processed/<endpoint>.json` (merged flat) + `data/processed/metadata.json`.

**`enrich_downloader.py`** — targeted per-country enrichment downloader.
- Does NOT use `coa_all=true`. Instead fires one request per country-of-asylum
  (`coa=<unhcr_code>`) for three endpoints: `asylum-decisions`,
  `asylum-applications`, `population`.
- Builds ISO3 → UNHCR code mapping first via `/countries/` (14 known
  differences, e.g. DEU→GFR, GMB→GAM, CIV→ICO, ZMB→ZAM).
- Computes per-country stats: `acceptance_rate` = `dec_recognized / dec_total`,
  `total_protection_rate` = `(dec_recognized + dec_complementary) / dec_total`,
  uses most recent year with ≥10 total decisions to avoid noise.
- Output: `specs/data/countries_enriched.json` (gitignored).
- Time: ~4 min (152 countries × 3 endpoints × 0.4s) vs ~30+ min for full
  `unhcr_downloader.py --all` with `coa_all=true`.

**`query_data.py`** — runtime query layer used by `country_lookup.js` at
agent runtime. Reads local processed JSON files. No network at runtime.

**`refresh_data.py`** — staleness check + re-download. Run annually or
before demos.

#### Agent tasks required before Phase 1 coding (data quality gate)

Before T036 (`country_lookup.js`) can be implemented and tested, the
following must be done and verified by the agent. These are not in `PLAN.md`
as numbered tasks — treat them as prerequisites that must be confirmed before
marking T036 ready:

1. **Run the downloader:**
   ```bash
   cd data/scripts && python unhcr_downloader.py --all
   ```
   Confirm: `data/processed/metadata.json` shows all endpoints with `status: ok`.

2. **Run the enrichment:**
   ```bash
   python enrich_downloader.py
   ```
   Confirm: `specs/data/countries_enriched.json` is produced. Spot-check
   5 tier-1 countries (e.g. KEN, DEU, CAN, AUS, FRA) — `stats` fields must
   be numeric (not `"PENDING"`).

3. **Data quality checks — run and report results:**
   - Countries where `total_protection_rate_recent == 0.0` and
     `refugee_population_total > 1000` — flag as potential data gap (not
     necessarily wrong, but worth surfacing).
   - Countries where `data_year < 2021` — flag as stale data.
   - Tier 1/2 countries where any `stats` field is still `"PENDING"` after
     enrichment — these indicate a UNHCR code mapping miss; add to
     `enrich_downloader.py`'s code map manually.
   - Non-signatory resettlement-pipeline countries (JOR, IND, MYS, IDN, THA)
     — these have `unhcr_rsd: true` but are not Convention signatories; verify
     their `stats` enriched correctly (they should, as UNHCR tracks them).

4. **Verify `country_lookup.js` returns live data, not PENDING:**
   SC-026 (`country_lookup` for "Kenya" returns `unhcrPresence: true` and
   `processingTimeMonths > 0`) cannot pass if the enriched file is missing.
   Run enrich before running T036 tests.

5. **Commit enriched file or document why it is gitignored:**
   `countries_enriched.json` is gitignored because it is large and
   regenerable. Confirm the `.gitignore` rule is present and that
   `countries.json` (the curated fallback) is committed. The repo must
   always be usable without the enriched file — `country_lookup.js` must
   degrade gracefully to `countries.json` if `countries_enriched.json` is
   absent.

---

<!-- Entries are added here by Codex at the end of each phase, after human sign-off. -->
<!-- Format:                                                                          -->
<!--                                                                                  -->
<!-- ## [0.N.0] — YYYY-MM-DD                                                         -->
<!-- ### Added / Changed / Fixed                                                      -->
<!-- - Description (T### — SC-###)                                                    -->
<!--                                                                                  -->
<!-- *Phase N complete — N Codex-attributed commits in this release*                 -->
<!-- *Human sign-off: @developer — YYYY-MM-DD*                                       -->

---

## Legend

| Tag | Meaning |
|-----|---------|
| `Added` | New feature or component |
| `Changed` | Modification to existing behaviour |
| `Fixed` | Bug fix |
| `Tested` | Test added or updated |
| `Design` | Visual/UI change referencing DESIGN.md |

Each entry references the PLAN.md task ID (T###) and success criterion (SC-###)
it satisfies, so the judge can trace from changelog → spec → commit → test.
