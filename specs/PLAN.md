# PLAN.md — Fugee Implementation Plan

> Spec-Driven Development plan. Each phase has tasks, success criteria, and
> a hard human sign-off gate before the next phase begins.
>
> References: `ARCHITECTURE.md` (contracts), `DESIGN.md` (tokens), `mockup.html` (visual)

---

## Testing Philosophy

**Read this before writing a single test.**

Tests in this project are evidence, not ceremony. Their only value is proving
that real behaviour works for a real user. These rules are non-negotiable:

### What tests must do

- **E2E tests** call the real model, use real tool responses, and exercise the
  full data path from user input to final output. A test that skips the model
  or fabricates tool results is not an E2E test.
- **Integration tests** test real phase logic and the real state machine.
  HTTP calls to external APIs (UNHCR, search) may be stubbed at the HTTP
  client boundary (i.e. `httpx` mock, not a fake session object).
- **Unit tests** test pure functions: parsers, state transitions, document
  field extraction. No I/O, no model, no network.

### What tests must NOT do

- **Never fabricate data to pass a test.** If a country lookup returns no
  results, the test must surface that failure — not substitute invented data.
- **Never mark a criterion as met without running the test.** Evidence = the
  exact command run + the output (pass/fail/error text).
- **Never write tests whose only purpose is to increment a green count.** If a
  test would pass trivially regardless of implementation correctness, delete it.
- **No "smoke tests" that just check imports.** Every test must assert
  real observable behaviour.

### Light scaffolding exception

During Phase 0 setup, data-flow smoke tests may use a tiny synthetic session
object (e.g. `{"language": "en", "state": "INTAKE"}`) to verify wiring before
the model is integrated. These tests MUST be deleted or replaced with real-data
equivalents by the end of Phase 2. They are scaffolding, not evidence.

### Success criterion verification protocol

When all tasks in a phase are complete:

1. Run the full test suite for that phase
2. Capture the terminal output
3. For each SC item, state: SC-XXX | PASS/FAIL | evidence (line from output)
4. If any SC fails: do not proceed, fix and re-run
5. Present the table to the developer and wait for sign-off

---

## Phase 0 — Project Setup

**Goal:** Repository structure, environment, and tooling are ready. The app
launches and displays a blank Gradio skeleton. The agent loop module loads and
echoes a ping.

**Branch:** `feat/01-project-setup`

### Tasks

- [ ] T001 Create repository directory structure per `ARCHITECTURE.md §File Tree`
- [ ] T002 Create `requirements.txt` with pinned versions (Gradio, WeasyPrint, httpx, pytest)
- [ ] T003 Add Python agent loop dependencies to `requirements.txt`:
        `ollama`, `litellm` (optional multi-provider), `pytest-asyncio`
- [ ] T004 Create `app/app.py` — bare `gr.Blocks` that renders the Fugee wordmark and
        warm off-white background (`#F7F5F0`) matching `DESIGN.md §colors.background`
- [ ] T005 Inject DESIGN.md CSS tokens as `:root` block into Gradio via `gr.Blocks(css=...)`
        — verify all 20+ token variables are present and match `DESIGN.md` exactly
- [ ] T006 Create `agent/loop.py` — pure-Python `AgentLoop` class.
        **Source to port from:** https://github.com/earendil-works/pi/tree/main/packages/pi-agent-core/src
        Key files to read before writing a line: `agent-loop.ts` (the while-loop),
        `event-stream.ts` (AsyncGenerator wrapper), `types.ts` (event + tool schemas).
        Port the loop logic and event contracts to Python. Do NOT port the LLM layer —
        use `ollama.AsyncClient` (or `litellm.acompletion`) instead of `@earendil-works/pi-ai`.
        - `async def run(prompt, session, system_prompt, tools, thinking_level)` → `AsyncGenerator[AgentEvent, None]`
        - On first call: yields `AgentStartEvent`, sends prompt to LLM, yields `TextDeltaEvent` chunks, yields `AgentEndEvent`
        - LLM call via `ollama.AsyncClient` (or `litellm.acompletion` if `MODEL_PROVIDER != "ollama"`)
        - Read `MODEL_ID` from env (default: `qwen2.5:7b`)
- [ ] T007 Create `agent/events.py` — Python dataclasses for all `AgentEvent` types:
        `AgentStartEvent`, `TurnStartEvent`, `TextDeltaEvent`, `ToolStartEvent`,
        `ToolEndEvent`, `TurnEndEvent`, `AgentEndEvent`, `ErrorEvent`.
        Each has a `type: str` field matching the event name.
- [ ] T008 [P] Create `app/state/session.py` — `SessionState` dataclass + state machine enum
        matching `ARCHITECTURE.md §Session State Machine`
- [ ] T009 [P] Create `app/prompts/system.md` — master system prompt establishing Fugee's
        persona (compassionate case worker, plain language, never "the applicant")
- [ ] T010 Validate `DESIGN.md` tokens in Python — parse the YAML frontmatter and
        confirm every token referenced by the app's injected `:root` block resolves
        (no missing/undefined tokens). Pure Python, no Node/npm linter.
- [ ] T011 [P] Configure `pytest` in `pyproject.toml` or `pytest.ini`. Make the
        `agent` and `app` trees importable so tests and the entrypoint can use
        absolute imports (`from agent.loop import ...`, `from app.state.session import ...`):
        add `__init__.py` to `agent/`, `agent/tools/`, `app/`, `app/phases/`,
        `app/state/` (and `app/prompts/` if imported as a package), and set the
        import root (e.g. `[tool.pytest.ini_options] pythonpath = ["."]` plus a
        `[tool.setuptools.packages]`/`pip install -e .`, or equivalent). Confirm
        `python -c "import agent.loop, app.state.session"` succeeds from repo root.
- [ ] T012 Write `tests/unit/test_session.py` — state machine transitions:
        valid forward transitions pass, backward mutations raise `ValueError`
- [ ] T013 Run T012 tests — confirm fail (red) before implementation is complete
- [ ] T014 Implement state machine in `session.py` to make T012 tests pass
- [ ] T015 Write `tests/unit/test_loop_ping.py` — `AgentLoop.run()` yields an `AgentStartEvent` (ping → pong)
- [ ] T016 Run T015 — confirm pass (real loop, real LLM call)

### Success Criteria — Phase 0

| ID | Criterion | How to verify |
|----|-----------|---------------|
| SC-001 | `python app/app.py` launches without error and shows Fugee wordmark on `#F7F5F0` background | Run `python app/app.py`, open browser, visually confirm |
| SC-002 | Background color exactly matches `DESIGN.md colors.background` (`#F7F5F0`) | Use browser devtools color picker on the `<body>` |
| SC-003 | All `DESIGN.md` CSS tokens are present in the injected `:root` block | `grep --count "var(--" app/app.py` ≥ 20 |
| SC-004 | `AgentLoop.run()` yields an `AgentStartEvent` within 3 seconds of first call | `pytest tests/unit/test_loop_ping.py -v` passes |
| SC-005 | State machine rejects backward transitions (e.g. REVIEW → SITUATION) with `ValueError` | `pytest tests/unit/test_session.py -v` passes |
| SC-006 | Every `DESIGN.md` token used in the app's `:root` block resolves (no undefined tokens) | Run the Python token validator from T010, show output |
| SC-007 | `requirements.txt` and `pyproject.toml` committed with pinned versions | `git diff --stat HEAD` shows both files |

**⏸ STOP — present SC table to developer. Await explicit go-ahead before Phase 1.**

---

## Phase 1 — Agent Loop + Interview Core

**Goal:** The Python agent loop is production-ready. The agent conducts a
real multi-turn interview via the agent loop, with real streaming events flowing
to Gradio. Session state updates correctly after each turn.

**Branch:** `feat/02-agent-loop`

### Tasks

- [ ] T017 Extend `AgentLoop` to handle all event types in the full turn cycle:
        (`agent_start`, `turn_start`, `text_delta`, `tool_start`/`tool_end`,
        `turn_end`, `agent_end`, `error`) — yield each as a typed Python dict
- [ ] T018 Add `steer()` and `abort()` to `AgentLoop` — steer injects a message
        into the steering queue mid-run; abort sets the `abort_event` asyncio flag
- [ ] T019 Add session isolation to `AgentLoop` — each Gradio session gets its
        own loop instance (stateless factory pattern); no shared mutable state
- [ ] T020 Write `app/prompts/interview.md` — question bank for all 5 interview
        sub-phases (SITUATION, HISTORY, GOALS, REVIEW) with structured response
        type annotations (`type: choice | country | text`)
- [ ] T021 Update `AgentLoop` system prompt injection to include interview question
        bank and structured responder instructions
- [ ] T022 Implement `app/phases/interview.py` — Gradio `gr.Blocks` column:
        - Phase progress rail (5 dots: Intake/Situation/History/Goals/Review)
          matching `mockup.html #phase-2` progress rail
        - Chat message rendering: agent bubbles (primary-tint, left) and user
          bubbles (accent-tint, right) per `DESIGN.md §message-agent / message-user`
        - Structured responder switcher: Choice pills / Country selector / Free text
          per `DESIGN.md §structured responder` and `mockup.html` Phase 2 detail
        - "Agent is thinking..." indicator (3 teal dots) during streaming
        - "Save and continue later" ghost button
- [ ] T023 Wire Gradio streaming: on user submit → `agent_loop.run()` → yield
        `text_delta` deltas → update chat bubble in real time
- [ ] T024 On `turn_end` event: extract question type from agent message metadata →
        update structured responder to show correct input mode
- [ ] T025 On `agent_end` event: update `session.state` to next state machine state
- [ ] T026 Write `tests/integration/test_interview_flow.py`:
        - Uses real agent loop + real model (Qwen2.5-7B via Ollama)
        - Sends: "I am from Ethiopia, currently in Sudan"
        - Asserts: agent asks a follow-up question (not an error)
        - Asserts: session state is still within SITUATION..REVIEW range
        - Asserts: streaming events arrive in correct order (agent_start before turn_start, etc.)
- [ ] T027 Run T026 — confirm it passes with real model response (not mocked)
- [ ] T028 Write `tests/unit/test_event_parser.py` — loop event parsing:
        all 7 event types instantiated correctly from their dataclass constructors
- [ ] T029 Run T028 — confirm pass

### Success Criteria — Phase 1

| ID | Criterion | How to verify |
|----|-----------|---------------|
| SC-008 | A real multi-turn conversation completes: user sends 3 messages, agent responds 3 times with different questions | Run `test_interview_flow.py`, examine 3 distinct agent responses |
| SC-009 | Streaming works: first token from the model appears in the Gradio UI within 3 seconds of submit | Time manually with stopwatch in browser: submit → first character visible |
| SC-010 | `text_delta` delta events arrive and update the chat bubble character-by-character (not buffered) | Observe streaming in browser; no "pop in" of full response |
| SC-011 | Structured responder switches mode correctly: when agent asks a yes/no question, pills appear; when asking for country, country selector appears | Run interview to each question type, visually verify mode switch |
| SC-012 | Agent bubbles are `primary-tint` (`#E5EFEA`), user bubbles are `accent-tint` (`#FBEDE1`) | Browser devtools computed style check |
| SC-013 | "Save and continue later" ghost button is present and styled with transparent background and teal text per `DESIGN.md §button-ghost` | Visual + devtools check |
| SC-014 | Session state advances from `INTAKE` → `SITUATION` → `HISTORY` correctly after agent turns | `pytest tests/integration/test_interview_flow.py -v` — check state assertions |
| SC-015 | Loop handles exceptions: if `AgentLoop.run()` raises, an `ErrorEvent` is yielded and a visible error message appears in the Gradio UI (not a silent hang) | Patch LLM client to raise mid-stream; verify UI shows error, not spinner |

**⏸ STOP — present SC table to developer. Await explicit go-ahead before Phase 2.**

---

## Phase 2 — Intake UI + Language Selection

**Goal:** Phase 1 (Intake) Gradio screen is complete and matches `mockup.html #phase-1`
exactly. Language selection works, welcome copy renders correctly, trust note is visible.

**Branch:** `feat/03-intake-ui`

### Tasks

- [ ] T030 Implement `app/phases/intake.py` — full Gradio intake screen matching
        `mockup.html #phase-1`:
        - Fugee wordmark in Fraunces font
        - Tagline: "Safe guidance for people on the move"
        - Language pills grid (≥ 8 languages: English, French, Arabic, Swahili,
          Amharic, Somali, Hausa, Portuguese) per `DESIGN.md §language-pill`
        - Each pill shows language name in its own script
        - "Begin in [Language]" amber primary button per `DESIGN.md §button-primary`
        - Trust note chip with lock glyph: "This conversation is private.
          Nothing is stored without your consent."
- [ ] T031 Language selection state: clicking a pill sets `session.language` and
        updates the button label. Second click on same pill deselects.
        Only one pill can be selected at a time.
- [ ] T032 On "Begin" click: session state transitions `LANGUAGE_SELECT → INTAKE`,
        intake screen hides, interview screen becomes visible
- [ ] T033 Verify layout at 390px viewport: pills wrap, button is full-width,
        Fraunces heading scales with `clamp(38px, 6vw, 58px)` per `DESIGN.md §h1`
- [ ] T034 Write `tests/unit/test_intake_state.py`:
        - Language selection sets `session.language`
        - Selecting a new language replaces the old one (no multi-select)
        - `Begin` without language selection raises `ValueError`

### Success Criteria — Phase 2

| ID | Criterion | How to verify |
|----|-----------|---------------|
| SC-016 | Intake screen visually matches `mockup.html #phase-1` — wordmark, tagline, pill grid, trust note, begin button all present | Open both in browser side by side |
| SC-017 | All 8 language pills render, each in its native script (e.g. Arabic pill shows "العربية") | Visual check in browser |
| SC-018 | Selected pill fills teal (`#0E6A58`) with white text per `DESIGN.md §language-pill selected` | Devtools computed style after clicking |
| SC-019 | Button label updates to "Begin in [Language]" after pill selection | Click "Français" pill, verify button reads "Begin in Français" |
| SC-020 | Trust note chip is present, small, and uses rounded-full radius (`9999px`) per `DESIGN.md §Trust note` | Visual + devtools check |
| SC-021 | On mobile (390px): pills wrap naturally, no horizontal scroll, button is full-width | Chrome devtools mobile emulation |
| SC-022 | `pytest tests/unit/test_intake_state.py -v` passes | Run and show output |

**⏸ STOP — present SC table to developer. Await explicit go-ahead before Phase 3.**

---

## Phase 3 — Situation Assessment (Reasoning Stream)

**Goal:** Phase 3 (Assessment) screen is complete. The agent's reasoning trace
streams visibly to the user. Tool calls (web_search, country_lookup) are
wired and return real data. Assessment produces a structured output that
populates `session.assessment`.

**Branch:** `feat/04-assessment`

### Tasks

- [ ] T035 Implement `agent/tools/web_search.py` as an `AgentTool`:
        - Input: `{ query: string, focus?: "asylum|safety|process|contacts" }`
        - Calls a real search API (Tavily, Serper, or Modal-hosted endpoint)
        - Returns: `{ results: [{ title, url, snippet }], query }`
        - Error handling: if API fails, throw (do not return fake results)
- [ ] T036 Implement `agent/tools/country_lookup.py` as an `AgentTool`:
        - **Prerequisite:** Before implementing or testing this task, run the
          data pipeline and verify data quality. See `specs/CHANGELOG.md
          §Pre-Implementation — Data Layer` for the full checklist. In short:
          ```bash
          cd data/scripts
          python unhcr_downloader.py --all        # ~7 min
          python enrich_downloader.py             # ~4 min
          ```
          Then spot-check 5 tier-1 countries in `countries_enriched.json` —
          `stats` fields must be numeric, not `"PENDING"`. SC-026 cannot pass
          without this.
        - Input: `{ country: string, profile?: { origin, persecutionType } }`
        - Data source (priority order):
            1. `specs/data/countries_enriched.json` — if present (post `enrich_downloader.py`)
            2. `specs/data/countries.json`           — always present (curated fallback)
          Load the file once at startup; do NOT re-read on each call.
          Both files share the same schema — see `specs/data/README.md`.
        - Returns: `{ country, unhcrPresence, processingTimeMonths, acceptanceRate,
                    totalProtectionRate, primaryLanguage, requiredDocuments,
                    legalAidOrgs, unhcrOffice, tier, warning? }`
        - Error handling: if country not found, return `{ error: "not_found" }`
          (do not fabricate data)
- [ ] T037 Register both tools with `AgentLoop` in `app/app.py`:
        `loop = AgentLoop(tools=[web_search_tool, country_lookup_tool])`
- [ ] T038 Write `app/prompts/assessment.md` — reasoning scaffold:
        - Step 1: Review 1951 Refugee Convention grounds
        - Step 2: Check AU Refugee Convention (broader grounds)
        - Step 3: Assess safety of transit/current country
        - Step 4: Search for active asylum programs for this profile
        - Step 5: Rank 2–3 destination options
        - Instruct model to write reasoning visibly, in plain language,
          as a stream (not JSON)
- [ ] T039 Implement `app/phases/assessment.py` — Gradio assessment screen
        matching `mockup.html #phase-3`:
        - Left panel: structured summary of collected facts (dl/dt/dd per
          `ARCHITECTURE.md §Session object`)
        - Right panel: live reasoning stream (text deltas from `text_delta`
          events → append to `gr.Textbox` or `gr.HTML`)
        - Progress bar: "Assessing your case… N%" (update on `tool_end`)
        - Tool call indicators: when `tool_start` fires, show
          "Searching: [query]" as a small teal status chip
- [ ] T040 On `agent_end`: parse the final assistant message for structured
        assessment JSON (convention grounds, risk level, country recommendations)
        and populate `session.assessment`
- [ ] T041 Write `tests/integration/test_assessment.py`:
        - Uses a real seeded session (`origin: "Ethiopia"`, `persecution: "political"`,
          `current: "Sudan"`) — this is a real scenario, not fabricated
        - Runs full assessment phase with real model + real tool calls
        - Asserts: reasoning trace is non-empty (> 100 chars)
        - Asserts: `session.assessment.recommended_countries` has ≥ 1 entry
        - Asserts: each recommended country has `unhcrPresence` field
        - Asserts: no recommended country is the person's origin country
- [ ] T042 Run T041 — confirm pass (real data, real model, real tools)
- [ ] T043 Write `tests/unit/test_country_lookup.py`:
        - Kenya returns `unhcrPresence: true`
        - An invented country name returns `{ error: "not_found" }` (not an exception)

### Success Criteria — Phase 3

| ID | Criterion | How to verify |
|----|-----------|---------------|
| SC-023 | Reasoning trace renders progressively in the right panel as the model streams — not as a pop-in block | Watch streaming in browser; text should appear character by character |
| SC-024 | Tool call status shows in UI: "Searching: [actual query]" chip appears when `web_search` fires | Observe assessment run in browser |
| SC-025 | `web_search` returns real results (not mocked): the query "Kenya asylum Ethiopia 2026" returns at least 1 result with a real URL | `pytest tests/integration/test_assessment.py -v -k "test_web_search_real"` |
| SC-026 | `country_lookup` for "Kenya" returns `unhcrPresence: true` and `processingTimeMonths > 0` | `pytest tests/unit/test_country_lookup.py -v` |
| SC-027 | Assessment for seeded Ethiopian/Sudan session produces ≥ 1 recommended country | `pytest tests/integration/test_assessment.py -v` |
| SC-028 | No recommended country is the origin country | Assertion in T041 test output |
| SC-029 | `session.assessment` is populated with structured data after assessment completes (not null/empty) | Print `session.assessment` after T041 test |
| SC-030 | Left facts panel shows all 8 interview fields (origin, current location, persecution type, etc.) | Visual check against `mockup.html #phase-3` left panel |

**⏸ STOP — present SC table to developer. Await explicit go-ahead before Phase 4.**

---

## Phase 4 — Country Recommendations + Roadmap

**Goal:** Phase 4 (Recommendations) screen is complete. Country cards render
with real data from `session.assessment`. User can select a country. Roadmap
updates to the selected country. `session.selected_country` is set.

**Branch:** `feat/05-recommendations`

### Tasks

- [ ] T044 Implement `app/phases/recommendations.py` — country cards grid matching
        `mockup.html #phase-4`:
        - 2–3 country cards per `DESIGN.md §country-card`
        - Each card: flag emoji + Fraunces country name + match badge
          (success-tint "Strong match" or warning-tint "Moderate match")
        - Facts block: processing time, UNHCR office (✓/✗), acceptance rate,
          primary language — all from real `country_lookup` tool result
        - Expandable "What you need to prepare" (`<details>` / `gr.Accordion`)
        - "Select this country" secondary button
        - Selected card: primary border + 3px primary-tint ring + white fill +
          "✓ Selected" teal button per `DESIGN.md §country-card selected`
- [ ] T045 Country selection: clicking a card sets `session.selected_country`,
        updates card visual state, renders roadmap for that country
- [ ] T046 Implement roadmap component:
        - Vertical numbered timeline: 42px teal nodes + primary-tint-2 spine
        - 5 generic asylum steps (Register UNHCR → File claim → Interview →
          Decision → Integration) adapted to selected country specifics
        - Each step: bold title + plain description + "who to contact" chip +
          "estimated time" chip
        - Header shows selected country name; updates on card change
- [ ] T047 Write `tests/integration/test_recommendations.py`:
        - Seeds session with completed assessment (real Ethiopian/Sudan scenario)
        - Renders recommendations component
        - Asserts: exactly 2–3 country cards rendered
        - Asserts: each card shows a real country name (not placeholder text)
        - Asserts: selecting a card updates `session.selected_country`
        - Asserts: roadmap header contains the selected country name
- [ ] T048 Run T047 — confirm pass

### Success Criteria — Phase 4

| ID | Criterion | How to verify |
|----|-----------|---------------|
| SC-031 | Country cards match `mockup.html #phase-4` — flag, name, match badge, facts block all present | Side-by-side browser comparison |
| SC-032 | Match badges use correct colors: strong match uses `success-tint` (`#E4F1EA`) background, moderate uses `warning-tint` (`#F6ECD6`) | Devtools computed style on badge element |
| SC-033 | Country card facts are real data from `country_lookup` tool (not hardcoded) | Temporarily break the tool; verify card shows error state, not fabricated data |
| SC-034 | Selecting a card highlights it with `primary` (`#0E6A58`) border + 3px ring and changes button to "✓ Selected" teal state | Visual check in browser |
| SC-035 | Roadmap renders with ≥ 4 steps for the selected country | Count steps in rendered UI |
| SC-036 | Roadmap header updates when user switches between country cards | Click card 1, read header; click card 2, verify header changed |
| SC-037 | `pytest tests/integration/test_recommendations.py -v` passes | Run and show output |

**⏸ STOP — present SC table to developer. Await explicit go-ahead before Phase 5.**

---

## Phase 5 — Document Package

**Goal:** Phase 5 (Documents) screen is complete. All 4 documents are generated
from real session data. Downloads work. Pre-filled fields are highlighted.
Checklist is functional.

**Branch:** `feat/06-documents`

### Tasks

- [ ] T049 Implement `agent/tools/doc_generator.py`:
        - Input: `session` object (completed, with `selected_country` set)
        - Generates 4 PDFs using WeasyPrint from HTML templates
        - Pre-filled fields tagged with amber highlight (see `DESIGN.md §document-item`)
        - All pre-filled values must come from `session.interview.*` — no invented data
        - Logs every filled field: `logger.info("Filling field %s from %s", field, source_key)`
- [ ] T050 Create 4 HTML/CSS document templates in `agent/tools/templates/`:
        - `personal_statement.html` — structured narrative with fillable sections
        - `action_plan.html` — step-by-step plan for selected country
        - `emergency_contacts.html` — UNHCR + legal aid org list
        - `rights_summary_card.html` — single-page rights card, print-friendly
- [ ] T051 Implement `app/phases/documents.py` — document package screen matching
        `mockup.html #phase-5`:
        - Document preview panel: white page-like card with bottom fade,
          amber-tint highlights on pre-filled fields
        - Evidence checklist: 6–8 items with `gr.Checkbox`, partially checked
          based on `session.interview.documents_available`
        - File list: 4 document items per `DESIGN.md §document-item`
          (38px primary-tint file icon, title, meta, download button)
        - "Download all" amber primary button
        - "Start over for a different country" ghost button
- [ ] T052 Wire downloads via `gr.File` or `gr.DownloadButton` components
- [ ] T053 Write `tests/integration/test_documents.py`:
        - Seeds a complete session (real interview data for Ethiopian/Sudan scenario)
        - Calls `doc_generator.generate(session)`
        - Asserts: 4 PDF files are created and non-empty
        - Asserts: personal statement PDF contains the person's origin country
          ("Ethiopia") — proves real data was used, not placeholder
        - Asserts: no field contains the string "PLACEHOLDER" or "[NAME]"
        - Asserts: all 4 PDFs are valid (WeasyPrint renders without error)
- [ ] T054 Run T053 — confirm pass (real session data, real PDF generation)
- [ ] T055 Write `tests/unit/test_doc_fields.py`:
        - Tests that every pre-filled field traces to a real session key
        - Tests that a session with `origin_country: None` produces a PDF
          with that field blank (not a crash)

### Success Criteria — Phase 5

| ID | Criterion | How to verify |
|----|-----------|---------------|
| SC-038 | Document screen matches `mockup.html #phase-5` — preview, checklist, file list, download all button all present | Side-by-side browser comparison |
| SC-039 | Personal statement PDF contains "Ethiopia" (the seeded origin country) — proves real data, not placeholder | Open generated PDF, search for "Ethiopia" |
| SC-040 | No generated PDF contains literal strings "PLACEHOLDER", "[NAME]", or "[COUNTRY]" | `pytest tests/integration/test_documents.py -v -k "test_no_placeholders"` |
| SC-041 | Pre-filled fields in document preview have amber-tint highlight (`#FBEDE1` background) per `DESIGN.md §document-item` | Devtools computed style on highlighted spans |
| SC-042 | "Download all" button triggers download of all 4 files as a zip or sequential downloads | Click button in browser, verify file(s) downloaded |
| SC-043 | Checklist items checked if `session.interview.documents_available` contains that document type | Seed session with `documents_available: ["passport"]`, verify passport checkbox is pre-checked |
| SC-044 | `pytest tests/integration/test_documents.py -v` passes | Run and show output |

**⏸ STOP — present SC table to developer. Await explicit go-ahead before Phase 6.**

---

## Phase 6 — End-to-End Integration + Polish

**Goal:** The full 5-phase flow works end-to-end with a real user scenario.
UI matches `mockup.html` at both desktop (1280px) and mobile (390px).
App is deployable to HF Spaces.

**Branch:** `feat/07-e2e-polish`

### Tasks

- [ ] T056 Write `tests/e2e/test_full_flow.py`:
        - Uses `playwright` or `selenium` to drive a real browser session
        - Scenario: "Amina" — Ethiopian, political persecution, currently in Sudan,
          speaks Amharic + English, destination preference Kenya
        - Completes full flow: language select → interview (all 5 sub-phases) →
          assessment → country selection → document download
        - Asserts at each phase boundary: correct state, correct UI elements visible
        - Total test time logged (target: < 3 minutes wall clock)
- [ ] T057 Run T056 with `--model qwen2.5:7b` — must complete without human
        intervention, all assertions pass
- [ ] T058 Responsive QA: open app in Chrome devtools at 390px, verify:
        - Phase pills show dots only, no text labels (per `DESIGN.md §phase-pill mobile`)
        - All buttons are ≥ 44px tall
        - No horizontal overflow
        - All text ≥ 13.5px
- [ ] T059 Verify WCAG AA on each phase via a manual browser devtools audit against the
        `DESIGN.md` accessibility rules (contrast ≥ 4.5:1, visible focus rings, touch
        targets ≥ 44px) — 0 contrast failures. No Node/npm tooling (axe-core, Lighthouse).
- [ ] T060 Write `README.md` for the HF Space:
        - Brief description of Fugee
        - How to run locally
        - Model requirements (`≥7B, tool-calling capable`)
        - Privacy note (no data stored)
- [ ] T061 Add `demo_video_script.md` — 2-minute walkthrough script for the
        hackathon submission video
- [ ] T062 Test on HF Space: push to a private HF Space, run E2E test against the
        live URL (not localhost), verify full flow completes

### Success Criteria — Phase 6

| ID | Criterion | How to verify |
|----|-----------|---------------|
| SC-045 | Full E2E test `test_full_flow.py` passes with `qwen2.5:7b` — no mock data, no human intervention | `pytest tests/e2e/test_full_flow.py -v` — show terminal output |
| SC-046 | E2E test completes in under 3 minutes wall clock | Test log shows duration |
| SC-047 | App renders correctly at 390px: dots-only progress rail, full-width buttons, no overflow | Chrome devtools screenshot at 390px for each phase |
| SC-048 | All body text ≥ 13.5px at every phase | Browser devtools font-size audit |
| SC-049 | Manual WCAG audit passes on all 5 phases: every input shows a visible focus ring, text/background contrast ≥ 4.5:1 against `DESIGN.md` tokens, and all touch targets ≥ 44px | Browser devtools audit at 390px against the `DESIGN.md` accessibility rules — record findings |
| SC-050 | App deploys to HF Space and full flow completes against the live URL | `pytest tests/e2e/test_full_flow.py --base-url=https://huggingface.co/spaces/<space>` |
| SC-051 | HF Space `README.md` present with correct model requirements and privacy note | Check file exists, read it |

**⏸ STOP — present SC table to developer. Final review before hackathon submission.**

---

## Dependency Map

```
Phase 0 (Setup)
    └── Phase 1 (Agent Loop + Interview Core)  — requires: agent loop, state machine
            └── Phase 2 (Intake UI)        — requires: session state, Gradio skeleton
            └── Phase 3 (Assessment)       — requires: Phase 1 interview complete
                    └── Phase 4 (Recs)     — requires: session.assessment populated
                            └── Phase 5 (Docs) — requires: session.selected_country set
                                    └── Phase 6 (E2E) — requires: all phases complete
```

Phases 2 and 3 can begin in parallel after Phase 1 is complete.
All other phases are strictly sequential.

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Qwen2.5-7B insufficient for legal reasoning quality | Medium | High | Test early (Phase 3); fall back to 14B or 32B if needed |
| `country_lookup` data is stale or incomplete | Medium | Medium | Supplement with `web_search` in assessment; surface uncertainty to user |
| WeasyPrint PDF generation fails on HF Spaces | Low | Medium | Test on HF Space in Phase 6 before deadline; have markdown fallback |
| Agent loop asyncio contention under concurrent Gradio sessions | Low | Low | Each session gets its own loop instance (T019); no shared state |
| Hackathon deadline (June 15) | High | Critical | Phase 0–3 are MVP. Phases 4–6 are polish. Cutoff at any phase is submittable. |

---

## Minimal Viable Submission (if time runs short)

If the deadline is approaching, a submission with these phases complete is
viable and demonstrable:

- **Phase 0 + 1 + 2 + 3** = intake + full interview + visible agent reasoning
  with real tool calls. This alone demonstrates the core innovation.
- Phase 4 (cards) and Phase 5 (docs) are polish and add hackathon badge points
  but are not required for a compelling demo.

Do not rush Phase 3 (assessment + real tool calls) — this is the centrepiece.
