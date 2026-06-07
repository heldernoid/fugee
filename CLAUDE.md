# CLAUDE.md — Refuge

> Agent context file. Read this before touching any file in the repository.
> This is the single source of truth for how you work in this project.

---

## What Refuge Is

Refuge is an agentic AI assistant for displaced people, asylum seekers, and
refugees. It conducts a structured multi-phase interview, reasons about the
person's legal situation against international frameworks (1951 Refugee
Convention, AU Refugee Convention), recommends destination countries with
open asylum programs, and generates a personalised documentation package.

It runs as a **single-process Gradio application** backed by a **small LLM (≤32B parameters)**
and a pure-Python agent loop (`agent/loop.py`). The loop is ported from pi-agent-core's
design patterns — while-loop, typed event stream, tool lifecycle, steering queue — but
implemented entirely in Python. No Node.js, no subprocess, no NDJSON bridge.

This is a hackathon submission for the **Hugging Face Build Small Hackathon
(June 5–15, 2026)**. Quality bar is "demo-ready, real user can use it."

---

## Design Authority

**Two files are the authoritative source of truth for all visual decisions:**

| File | Authority |
|---|---|
| `DESIGN.md` | Design tokens (colors, typography, spacing, components) — machine-readable YAML + human rationale |
| `mockup.html` | Visual reference for every phase and component — open in a browser before implementing any UI |

Never deviate from `DESIGN.md` tokens. If you are unsure what something should
look like, open `mockup.html` first.

Key design rules from `DESIGN.md`:
- Primary color `#0E6A58` (teal) = Refuge's voice, structure, agent
- Accent color `#E07B39` (amber) = the person's actions, calls to action
- Background `#F7F5F0` (warm off-white) — never pure white `#FFFFFF` as page bg
- Fonts: `Fraunces` (serif, display/headings) + `Inter` (UI/body)
- One primary (amber) action per screen — never stack two
- Show agent reasoning visibly — no spinners hiding the thought process
- Person is always "you" — never "the applicant," "the case," or "the user"

---

## Architecture Overview

```
refuge/
├── agent/                    # Pure-Python agent loop + tools (top-level package)
│   ├── loop.py               # Pure-Python agent loop (ported from pi-agent-core patterns)
│   ├── events.py             # AgentEvent dataclasses (TextDeltaEvent, ToolStartEvent, etc.)
│   └── tools/
│       ├── web_search.py     # Asylum policy / UNHCR search tool
│       ├── country_lookup.py # Country data tool — reads specs/data/countries_enriched.json
│       │                     #   (falls back to specs/data/countries.json if not enriched yet)
│       └── doc_generator.py  # PDF/text document package generator
├── app/                      # Gradio application
│   ├── app.py                # Gradio entrypoint — `python app/app.py`; mounts all phases
│   ├── phases/
│   │   ├── intake.py         # Phase 1: language selection + welcome
│   │   ├── interview.py      # Phase 2: structured interview UI
│   │   ├── assessment.py     # Phase 3: reasoning stream display
│   │   ├── recommendations.py# Phase 4: country cards + roadmap
│   │   └── documents.py      # Phase 5: document package + download
│   ├── state/
│   │   └── session.py        # Interview state machine + session manager
│   └── prompts/
│       ├── system.md         # Master system prompt for the agent
│       ├── interview.md      # Per-phase interview question banks
│       └── assessment.md     # Reasoning scaffold prompt
├── data/                     # UNHCR data pipeline (scripts + raw/processed cache)
│   └── scripts/
│       ├── unhcr_downloader.py   # Full UNHCR API downloader
│       ├── enrich_downloader.py  # Per-country stats enrichment → specs/data/countries_enriched.json
│       ├── query_data.py         # Runtime query layer (no network at runtime)
│       └── refresh_data.py       # Staleness check + re-download
├── specs/                    # Specs + reference data (read these before coding)
│   ├── PLAN.md               # Implementation phases + success criteria
│   ├── ARCHITECTURE.md       # System architecture + data flow
│   ├── CHANGELOG.md          # Per-phase change log + data-layer pre-work
│   └── data/
│       ├── countries.json    # Curated country reference (committed fallback)
│       ├── countries_enriched.json  # Enriched stats (gitignored, regenerable)
│       └── README.md         # Country data schema
├── tests/
│   ├── e2e/                  # End-to-end flow tests (real model, real data)
│   ├── integration/          # Phase-level integration tests
│   └── unit/                 # Pure logic unit tests (state machine, tools)
├── DESIGN.md                 # Design system tokens (YAML frontmatter + human rationale)
├── mockup.html               # Visual reference — all 5 phases
├── CLAUDE.md                 # This file
├── AGENTS.md                 # Agent configuration + multi-agent rules
└── requirements.txt          # Python deps
```

See `specs/ARCHITECTURE.md` for the full data flow diagram and component contracts.
See `specs/PLAN.md` for the phased implementation plan and success criteria.

---

## Technology Stack

| Layer | Technology | Notes |
|---|---|---|
| UI framework | Gradio (Python) | Custom CSS via `gr.HTML` + `gr.Blocks` theming |
| Agent loop | Pure Python (`agent/loop.py`) | Ported from pi-agent-core patterns; no Node, no subprocess |
| LLM | ≤32B model via Ollama / Modal | Qwen2.5-7B default; swappable via env var |
| LLM client | `ollama` Python SDK + `litellm` | `ollama` for local; `litellm` for multi-provider if needed |
| Tools | Python (`agent/tools/`) | search, country lookup, doc gen — all pure Python, no bridge |
| Document generation | WeasyPrint (Python) | PDF output for the document package |
| State | Python dict + Gradio session state | No external DB required for hackathon |
| Hosting | Hugging Face Spaces | Public Gradio Space |

---

## Critical Rules

### Code

1. **Never fabricate data.** If a tool call fails, surface the error to the UI —
   do not substitute mock/fake data silently. See `specs/PLAN.md §Testing Philosophy`.
2. **Never hide the agent loop.** Streaming events from `agent/loop.py` must flow
   to the UI in real time. No buffering an entire response then dumping it.
3. **Session state is append-only during an interview.** Never mutate earlier
   interview answers once submitted. The state machine in `app/state/session.py` enforces this.
4. **Document generation uses only interview-derived data.** No hallucinated
   facts in the PDF output. Pre-filled fields are tagged as agent-suggested and
   the person can edit them.
5. **Model is a parameter, not a constant.** Always read from `MODEL_ID` env var.
   Default: `qwen2.5:7b`.

### Design

6. **Read `mockup.html` before implementing any Gradio component.** Reference
   the exact phase you're building.
7. **CSS tokens in `DESIGN.md` are canonical.** Do not invent new colors.
   Map every Gradio theme override to an existing token.
8. **One amber (primary) action per phase screen.** If you find yourself adding
   two, one of them should be secondary or ghost.
9. **Every input must have a visible focus ring** (`outline: 3px solid var(--accent)`).
10. **Touch targets ≥ 44px.** Check on a 390px viewport.

### Testing

11. **Tests use real model calls for E2E, not mocks.** Stub only at the network
    boundary for unit tests (tool HTTP calls). See `specs/PLAN.md §Testing Philosophy`.
12. **Write tests before implementation for each phase.** Confirm they fail red
    before writing the implementation.
13. **Never mark a success criterion as met without running the actual test.**
    Do not self-certify. Run the test, show the output.

---

## Development Commands

```bash
# Install Python deps
pip install -r requirements.txt

# Run the app locally
python app/app.py

# Run all tests
pytest tests/ -v

# Run E2E only
pytest tests/e2e/ -v --model qwen2.5:7b

# Run unit + integration (no model required)
pytest tests/unit/ tests/integration/ -v
```

> **No Node.js / npm anywhere in this project.** Refuge is a pure-Python,
> single-process app. The only external repo the agent may touch is `pi`
> (cloned to `/tmp/pi`) — and its agent-loop patterns are *ported to Python*,
> never invoked as JavaScript. Do not add npm/npx/Node tooling, including
> design-token or accessibility linters.

---

## Git Conventions

Follow spec-kit branch naming:

```
feat/<number>-<slug>   # new feature (e.g. feat/01-agent-loop)
fix/<number>-<slug>    # bug fix
docs/<slug>            # documentation only
```

Commit after each completed task in `specs/PLAN.md`. Commit message format:

```
[T###] Brief description of what was done
```

---

## Human Developer Sign-Off

Each phase in `specs/PLAN.md` ends with a **STOP — await human sign-off** checkpoint.
Do not begin the next phase until the developer explicitly says "proceed" or
"go ahead." This is not a suggestion — it is a hard gate.

When you reach a checkpoint:
1. Run all success criteria tests for that phase
2. Summarise results in a short table (criterion, status, evidence)
3. State clearly: `⏸ Awaiting developer go-ahead to proceed to Phase N`
4. Stop. Do not continue.

---

## Asking for Help

If you are blocked or uncertain about a requirement, say so explicitly.
Do not make assumptions that affect correctness or safety of the output.
This is a product for vulnerable people — wrong output is worse than no output.
