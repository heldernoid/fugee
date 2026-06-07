---
description: "Refuge — agentic asylum guidance assistant. Full project context and working conventions for Codex."
---

# Refuge — Codex Skill

You are the primary coding agent for **Refuge**, a hackathon submission for
the Hugging Face Build Small Hackathon (June 5–15, 2026).

## What Refuge does

Refuge guides displaced people, asylum seekers, and refugees through a
5-phase agentic flow: language selection → structured interview → situation
assessment (visible reasoning) → country recommendations → document package.

It runs as a single-process Gradio application (Python) with a pure-Python agent
loop (`agent/loop.py`) ported from pi-agent-core patterns. No Node.js, no subprocess,
no NDJSON bridge. The LLM (≤32B parameters) is called directly via the `ollama` Python
SDK or `litellm` for multi-provider support.

## Before you write any code

Read these files **in order**. Do not skip any.

| # | File | What it contains |
|---|---|---|
| 1 | `AGENTS.md` | Your rules, roles, commit format, escalation protocol |
| 2 | `CLAUDE.md` | Project overview, critical rules, dev commands |
| 3 | `DESIGN.md` | Design tokens — colors, typography, spacing. Canonical. |
| 4 | `specs/ARCHITECTURE.md` | System contracts, data flow, component schemas |
| 5 | `specs/PLAN.md` | Phased tasks (T001–T062) and success criteria (SC-001–SC-051) |
| 6 | `specs/CHANGELOG.md` | What has been built and decided — read before assuming anything is pending |
| 7 | `mockup.html` | Open in browser before implementing any UI component |
| 8 | `specs/data/README.md` | Country data schema — read before touching `country_lookup.js` or `enrich_downloader.py` |

## Data files

| File | Status | Purpose |
|---|---|---|
| `specs/data/countries.json` | ✅ committed | 146 signatory + 23 non-signatory countries. Curated. Always present. |
| `specs/data/countries_enriched.json` | generated (gitignored) | Same schema + live UNHCR stats. Produced by `data/scripts/enrich_downloader.py`. |

`country_lookup.js` must load `countries_enriched.json` if present, fall back to
`countries.json` if not. See `specs/PLAN.md T036` for the full spec.

## Working conventions

### Tasks

Always work from the current phase in `specs/PLAN.md`. Pick up at the first
unchecked task `[ ]`. Do not skip tasks. Do not start the next phase
before the human developer gives explicit go-ahead.

### Commits

Every commit must follow this format exactly:

```
[T###] Imperative description in ≤72 chars

Optional body explaining what changed and why.
Keep to ≤500 chars.

Co-authored-by: Codex <noreply@openai.com>
```

The blank line before `Co-authored-by` is mandatory. The trailer must be
present on every commit — required for hackathon Codex track eligibility.

### Tests

- Write tests before implementation. Confirm they fail (red) first.
- E2E tests use the real model and real tool calls. No mocks.
- Unit tests may stub HTTP at the network boundary only.
- Never fake data to make a test pass. Surface failures to the developer.

### Design

- All colors, spacing, and typography come from `DESIGN.md` tokens.
- Never use raw hex values not in `DESIGN.md`. Map everything to a token.
- Primary amber (`#E07B39`) = one per screen maximum.
- Check `mockup.html` Phase N before implementing Phase N UI.

### Human sign-off gates

Each phase in `specs/PLAN.md` ends with a `⏸ Await human sign-off` checkpoint.
When you reach one:
1. Run all SC tests for that phase
2. Present a table: SC-ID | PASS/FAIL | evidence
3. State: `⏸ Awaiting developer go-ahead to proceed to Phase N`
4. Stop. Do not continue.

### What never to do

- Never fabricate data (tool responses, session fields, country data)
- Never self-certify a success criterion without running the test
- Never use colors or spacing values outside `DESIGN.md`
- Never start the next phase without explicit go-ahead
- Never modify `AGENTS.md`, `CLAUDE.md`, `specs/PLAN.md`, or `specs/ARCHITECTURE.md`
  without explicit developer instruction

## Tech stack summary

| Layer | Technology |
|---|---|
| UI | Python + Gradio 4.x, custom CSS via DESIGN.md tokens |
| Agent loop | Pure Python — `agent/loop.py` (ported from pi-agent-core patterns) |
| LLM | Qwen2.5-7B via Ollama (default), swappable via MODEL_ID env var |
| LLM client | `ollama` Python SDK (local) or `litellm` (multi-provider) |
| Tools | web_search (Python) + country_lookup (Python) + doc_generator (Python) |
| PDF | WeasyPrint (Python) |
| Tests | pytest (Python) only — no Node test runner |

## Quick commands

```bash
python app/app.py                          # run the app
pytest tests/ -v                           # all tests
pytest tests/e2e/ -v                       # E2E (needs real model)
pytest tests/unit/ tests/integration/      # no model required
cd data/scripts && python unhcr_downloader.py --all   # download UNHCR data
cd data/scripts && python enrich_downloader.py        # enrich countries.json

# No npm install — pure Python, no Node dependencies
```
