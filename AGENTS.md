# AGENTS.md — Fugee

> Configuration for all AI agents working in this repository.
> Codex, Cursor, Gemini CLI, and any other agent must read this file before
> working in this project. This is the single, canonical agent doc.

---

## Project Identity

**Refuge** — agentic asylum guidance assistant
**Hackathon**: Hugging Face Build Small Hackathon, June 5–15 2026
**Stack**: Python + Gradio (UI) / Pure-Python agent loop (ported from pi-agent-core) / ≤32B LLM via Ollama
**Audience**: Displaced people, asylum seekers, refugees. High-stakes product.

---

## Context Files — Read Order

Agents MUST read these files in order before starting any task:

| Order | File | What it contains |
|---|---|---|
| 1 | `README.md` | Project overview, how to run, deploy summary |
| 2 | `DESIGN.md` | Design tokens — colors, typography, spacing, components |
| 3 | `specs/ARCHITECTURE.md` | System design, data flow, component contracts |
| 4 | `specs/PLAN.md` | Phases, tasks, success criteria, checkpoints |
| 5 | `specs/CHANGELOG.md` | Build history and decisions — read before assuming anything is pending |
| 6 | `mockup.html` | Visual reference — open in browser before any UI work |
| 7 | `specs/data/README.md` | Country data schema — read before touching country_lookup or data scripts |

Do not skip steps. These files exist because agents that skip context produce
wrong output, and wrong output here affects vulnerable people.

---

## Agent Roles

This project supports a single human developer assisted by one or more AI
coding agents. The roles are:

| Role | Responsibility |
|---|---|
| **Human developer** | Final authority on all decisions. Signs off each phase before next begins. |
| **Primary agent** (you) | Implements tasks in `PLAN.md` sequentially. Runs tests. Reports results. Waits for sign-off. |
| **Secondary agent** (if used) | May work on a separate phase branch in parallel. Must not merge without primary agent review and human sign-off. |

There is no automated merge. All merges require explicit human approval.

---

## Hard Rules for All Agents

### 1. No fabricated data — ever

Do not substitute mock, placeholder, or invented data for real data in any
context that reaches the running application or its tests. Specifically:

- Do not fake tool call responses to make a test pass
- Do not hardcode country data that should come from a live tool call
- Do not pre-fill document fields with data not derived from the interview
- Do not generate "example output" and label it as test evidence

The only exception: **unit tests may stub HTTP calls at the network boundary**
(i.e. mock the HTTP client, not the business logic). See `PLAN.md §Testing Philosophy`.

### 2. Tests run before implementation

For each user story:
1. Write the test(s)
2. Run them — confirm they fail (red)
3. Implement until they pass (green)
4. Never write the implementation first

If you are asked to skip this, refuse and explain why.

### 3. Never self-certify success criteria

A success criterion is met when the test passes and you can show the output.
Never write "✅ SC-001 met" without:
- The exact command you ran
- The output (pass/fail/error)
- The actual behaviour observed

### 4. Stop at phase checkpoints

Every phase in `PLAN.md` ends with `⏸ Await human sign-off`. This is a hard
stop. Do not proceed to the next phase. Do not start "preparatory work."
Wait for the human developer to explicitly say "proceed."

### 5. One primary (amber) action per screen

When implementing Gradio UI components, enforce the design rule from `DESIGN.md`:
a single `button-primary` (amber) per phase screen. If you find yourself adding
two, flag it to the developer — one of them should be secondary or ghost.

### 6. Design tokens are not negotiable

All colors, spacing, and typography come from `DESIGN.md`. Do not invent new
values. Do not use Tailwind defaults, Bootstrap colors, or Gradio's default
theme values directly. Map every styling decision to a `DESIGN.md` token.

### 7. Disclose agent identity in PRs

If you post a PR comment or commit message on behalf of the human developer,
include: "Posted by [agent name] on behalf of @[developer]."

---

## Capabilities by Agent

### Codex CLI (OpenAI)

- Context file: `AGENTS.md` (this file)
- Skills path: `.agents/skills/`
- Preferred for: Python agent loop, tool implementations, Gradio UI
- Argument placeholder: `$ARGUMENTS`
- Install: see the Codex CLI's own documentation (do not add its installer to this repo)

### Gemini CLI

- Context file: `GEMINI.md` (if present, else fall back to `AGENTS.md`)
- Commands path: `.gemini/commands/`
- Preferred for: research tasks, cross-reference asylum policy data
- Argument placeholder: `{{args}}`

### Cursor / Windsurf

- Rules path: `.cursor/rules/` or `.windsurf/rules/`
- Same rules as above apply — read `AGENTS.md` first

---

## Branch Strategy

```
main                    # stable, demo-ready at all times
feat/01-project-setup   # Phase 0
feat/02-agent-bridge    # Phase 1
feat/03-interview-ui    # Phase 2
feat/04-assessment      # Phase 3
feat/05-recommendations # Phase 4
feat/06-documents       # Phase 5
feat/07-e2e-polish      # Phase 6
```

Each phase branch is created by the developer, not the agent. The agent
commits to the active branch. The developer merges.

---

## Commit Message Convention

Every commit MUST follow this exact format:

```
[T###] Imperative description in ≤72 chars

Optional body: what changed and why (≤500 chars).
Reference the PLAN.md task and any SC IDs this advances.

Co-authored-by: Codex <noreply@openai.com>
```

**The `Co-authored-by` trailer is mandatory on every commit.**

Rules:
- The blank line before `Co-authored-by` is required by the Git trailer spec
- The trailer must be the last line of the commit body
- Never omit the trailer — it is required for hackathon Codex track eligibility
  and provides an audit trail for the judge (Codex itself)
- The task ID `[T###]` must match a real task in `PLAN.md`

**Good examples:**

```
[T001] Scaffold Gradio app.py with Blocks layout

Creates bare gr.Blocks with warm off-white background (#F7F5F0).
Injects DESIGN.md CSS token block into :root. Advances SC-001, SC-002.

Co-authored-by: Codex <noreply@openai.com>
```

```
[T035] Add web_search AgentTool to agent/tools/web_search.py

Implements web_search as Python AgentTool dataclass. Calls Tavily API.
Returns {results, query}. Raises on API failure (no fake fallback).
Advances SC-025.

Co-authored-by: Codex <noreply@openai.com>
```

Include the task ID from `PLAN.md` in every commit.

---

## Escalation Protocol

If you encounter any of the following, **stop work and ask the developer**:

- A requirement that conflicts between `PLAN.md`, `ARCHITECTURE.md`, and `DESIGN.md`
- A test that is impossible to write without real external data you cannot access
- A design decision not covered by `DESIGN.md` or `mockup.html`
- Any output that involves legal advice, country-specific legal facts, or
  claims about a person's asylum eligibility — flag for human review

Do not improvise on any of the above. This product is used by vulnerable people.
Wrong output is not a "best effort" — it causes harm.

---

## Testing Philosophy (summary — see `PLAN.md` for full detail)

- **E2E tests**: real model, real tool calls, real data flow end-to-end
- **Integration tests**: real phase logic, real state machine, stubbed HTTP only
- **Unit tests**: pure logic, no I/O, no model calls, no network

Tests are evidence, not formality. A passing test that uses fake data is not a
passing test — it is a false signal. The value of a test is that it proves the
real system works for a real user in a real scenario.

---

*Last updated: June 2026. Maintained by the human developer.*
*Agents: do not modify this file without explicit instruction.*
