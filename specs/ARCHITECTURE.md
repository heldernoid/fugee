# ARCHITECTURE.md — Refuge

> System architecture, data flow, and component contracts.
> Read `AGENTS.md` first, then this file, then `PLAN.md`.

---

## System Overview

Refuge is a **single-process Python application**: a Gradio frontend and a
pure-Python agent loop running in the same process. There is no subprocess,
no Node.js, no NDJSON bridge.

The agent loop is ported from the structural patterns of pi-agent-core
(the loop, event stream, tool lifecycle, steering queue) but implemented
entirely in Python. LLM calls go directly to Ollama or any OpenAI-compatible
endpoint via the `ollama` or `litellm` Python SDK.

```
┌─────────────────────────────────────────────────────────┐
│                     HF Space / Browser                   │
│  ┌───────────────────────────────────────────────────┐   │
│  │                  Gradio App (Python)               │   │
│  │                                                    │   │
│  │  Phase 1   Phase 2   Phase 3   Phase 4   Phase 5  │   │
│  │  Intake    Interview  Assessment  Recs    Docs     │   │
│  │     │          │          │         │       │      │   │
│  │     └──────────┴──────────┴─────────┴───────┘      │   │
│  │                      │                              │   │
│  │              AgentLoop (agent/loop.py)              │   │
│  │         async generator — yields AgentEvent         │   │
│  └──────────────────────┼──────────────────────────────┘   │
│                         │                                   │
│  ┌──────────────────────▼──────────────────────────────┐   │
│  │              Python Agent Loop                       │   │
│  │              agent/loop.py                          │   │
│  │                                                      │   │
│  │  ┌─────────────┐   ┌──────────────┐                 │   │
│  │  │  LLM client │   │  AgentTools  │                 │   │
│  │  │  (ollama /  │   │  web_search  │                 │   │
│  │  │   litellm)  │   │  country_lookup│               │   │
│  │  └──────┬──────┘   └──────┬───────┘                 │   │
│  └─────────┼─────────────────┼─────────────────────────┘   │
│            │                 │                               │
│    ┌───────▼──────┐  ┌───────▼──────────┐                   │
│    │  LLM endpoint│  │  External APIs   │                   │
│    │  (Ollama /   │  │  (UNHCR, asylum  │                   │
│    │   Modal)     │  │   policy search) │                   │
│    └──────────────┘  └──────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Design Decision: Why Pure Python

The original spec called for a pi-agent-core (Node.js) subprocess bridge.
After evaluation, we ported the agent loop to Python instead. Reasons:

1. **HF Spaces constraint** — spawning a Node subprocess on a Gradio Space
   is fragile (subprocess lifecycle, signal handling, buffering in sandbox).
2. **Single process** — Gradio's `async` generator support means the loop
   can yield events directly into the UI with no IPC layer.
3. **Porting cost is low** — the pi-agent-core loop is ~300 lines of logic.
   Python's `asyncio`, `typing`, and `dataclasses` map cleanly.
4. **LLM layer is commodity** — `ollama` Python SDK covers the Ollama case
   in 2 lines; `litellm` covers multi-provider if needed. No need to port
   pi-ai's 20-provider abstraction.

What was kept from pi-agent-core's design:
- The while-loop with tool execution and event emission pattern
- Typed event contracts (ported to Python dataclasses)
- Steering queue (inject messages mid-run)
- Tool definition schema (ported to Python TypedDict / Pydantic)

**Source:** https://github.com/earendil-works/pi/tree/main/packages/pi-agent-core/src
Read `agent-loop.ts`, `event-stream.ts`, and `types.ts` before implementing `agent/loop.py`.

---

## Component Contracts

### 1. Agent Loop (`agent/loop.py`)

Pure Python async generator. Gradio phases call `loop.run(prompt, session)`
and iterate over the yielded `AgentEvent` objects.

**Event types** (Python dataclasses in `agent/events.py`):

```python
@dataclass
class AgentStartEvent:    type: str = "agent_start"
@dataclass
class TurnStartEvent:     type: str = "turn_start"
@dataclass
class TextDeltaEvent:     type: str = "text_delta";  delta: str = ""
@dataclass
class ToolStartEvent:     type: str = "tool_start";  name: str = ""; args: dict = field(default_factory=dict)
@dataclass
class ToolEndEvent:       type: str = "tool_end";    name: str = ""; result: dict = field(default_factory=dict)
@dataclass
class TurnEndEvent:       type: str = "turn_end";    message: dict = field(default_factory=dict)
@dataclass
class AgentEndEvent:      type: str = "agent_end";   messages: list = field(default_factory=list)
@dataclass
class ErrorEvent:         type: str = "error";       message: str = ""

AgentEvent = Union[AgentStartEvent, TurnStartEvent, TextDeltaEvent,
                   ToolStartEvent, ToolEndEvent, TurnEndEvent,
                   AgentEndEvent, ErrorEvent]
```

**Loop contract:**

```python
async def run(
    prompt: str,
    session: SessionState,
    system_prompt: str,
    tools: list[AgentTool],
    thinking_level: Literal["low", "medium", "high"] = "low",
) -> AsyncGenerator[AgentEvent, None]:
    ...
```

- MUST NOT buffer; yield each event as it is produced
- MUST propagate errors as `ErrorEvent` (never raise through Gradio)
- MUST support `steering_queue` injection mid-run (for follow-up questions)
- MUST support `abort_event` to stop the loop gracefully

**Loop internals (ported from pi-agent-core patterns):**

```python
# Simplified structure — see agent/loop.py for full implementation
async def run(...):
    yield AgentStartEvent()
    messages = list(session.messages)
    messages.append({"role": "user", "content": prompt})

    while True:
        yield TurnStartEvent()
        response = await llm.stream(messages, tools, system_prompt)

        # Stream text deltas
        async for chunk in response:
            if chunk.type == "text":
                yield TextDeltaEvent(delta=chunk.text)
            elif chunk.type == "tool_call":
                yield ToolStartEvent(name=chunk.name, args=chunk.args)
                result = await execute_tool(chunk.name, chunk.args, tools)
                yield ToolEndEvent(name=chunk.name, result=result)

        # Check steering queue
        if not steering_queue.empty():
            steer_msg = await steering_queue.get()
            messages.append({"role": "user", "content": steer_msg})
            continue

        yield TurnEndEvent(message=response.final_message)
        break

    yield AgentEndEvent(messages=messages)
```

---

### 2. Agent Tools (`agent/tools/`)

Tools are Python callables registered with the loop. Each tool is a
`AgentTool` dataclass:

```python
@dataclass
class AgentTool:
    name: str
    description: str
    parameters: dict           # JSON Schema object
    execute: Callable          # async (args: dict) -> dict
```

**`web_search` tool** (`agent/tools/web_search.py`):
```python
AgentTool(
    name="web_search",
    description="Search for current asylum policies, UNHCR data, country safety",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "focus": {"type": "string", "enum": ["asylum", "safety", "process", "contacts"]}
        },
        "required": ["query"]
    },
    execute=web_search_execute   # calls Tavily or Serper API
)
```

**`country_lookup` tool** (`agent/tools/country_lookup.py`):
```python
AgentTool(
    name="country_lookup",
    description="Look up a country's asylum program: acceptance rates, processing times, UNHCR presence",
    parameters={
        "type": "object",
        "properties": {
            "country": {"type": "string"},
            "profile": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string"},
                    "persecutionType": {"type": "string"}
                }
            }
        },
        "required": ["country"]
    },
    # Data source: specs/data/countries_enriched.json (preferred, post enrich_downloader.py)
    #              specs/data/countries.json           (curated fallback, always present)
    # Both share the same schema — see specs/data/README.md.
    # Load at startup; do NOT re-read per call. Fail loudly if neither file exists.
    execute=country_lookup_execute
)
```

---

### 3. Session State Machine (`app/state/session.py`)

The interview follows a strict state machine. States are append-only — no
going back to modify earlier answers once the user has moved forward.

```
LANGUAGE_SELECT
      │
      ▼
INTAKE          ← Phase 1 complete
      │
      ▼
SITUATION       ─ "What type of persecution?"
      │            "Are you in immediate danger?"
      │            "Current location / transit countries?"
      ▼
HISTORY         ─ "How long have you been displaced?"
      │            "Have you made prior asylum claims?"
      │            "What documents do you have?"
      ▼
GOALS           ─ "Do you have destination preferences?"
      │            "Family or connections in specific countries?"
      │            "Languages spoken?"
      ▼
REVIEW          ─ Structured summary, user confirms
      │
      ▼
ASSESSMENT      ← Phase 3 begins
      │
      ▼
RECOMMENDATIONS ← Phase 4 begins
      │
      ▼
DOCUMENTS       ← Phase 5 begins
      │
      ▼
COMPLETE
```

**Session object schema:**

```python
{
  "session_id": str,           # UUID
  "language": str,             # ISO 639-1 (e.g. "fr", "ar", "sw")
  "state": str,                # current state machine state
  "interview": {
    "origin_country": str | None,
    "current_country": str | None,
    "persecution_types": list[str],   # ["political", "ethnic", ...]
    "immediate_danger": bool | None,
    "family_situation": str | None,
    "documents_available": list[str],
    "languages_spoken": list[str],
    "destination_preferences": list[str],
    "prior_claims": bool | None,
    "displacement_duration": str | None,
    "free_text_history": str | None,
  },
  "assessment": {
    "convention_grounds": list[str],  # 1951 + AU Refugee Convention
    "risk_level": str,                # "high" | "moderate" | "low"
    "reasoning_trace": str,           # full visible reasoning text
    "recommended_countries": list[CountryRecommendation],
  },
  "selected_country": str | None,
  "messages": list[dict],            # full conversation history
  "created_at": str,                 # ISO 8601
  "updated_at": str,
}
```

---

### 4. Gradio Phases (`app/phases/`)

Each phase is a self-contained Python module that exports a `build(session)`
function returning a `gr.Blocks` or `gr.Column` component tree.

**Phase ↔ State contract:**

| Phase module | Entry state | Exit state | Gradio yield pattern |
|---|---|---|---|
| `intake.py` | `LANGUAGE_SELECT` | `INTAKE` | `gr.update()` on language pill click |
| `interview.py` | `INTAKE` | `REVIEW` | Streaming via `AgentLoop.run()` async generator |
| `assessment.py` | `ASSESSMENT` | `RECOMMENDATIONS` | Streaming text delta to `gr.Textbox` |
| `recommendations.py` | `RECOMMENDATIONS` | `DOCUMENTS` | Card selection + roadmap render |
| `documents.py` | `DOCUMENTS` | `COMPLETE` | PDF download via `gr.File` |

**Consuming the agent loop in Gradio:**

```python
# In interview.py — streaming loop events into Gradio
async def on_submit(user_input, session_state):
    async for event in agent_loop.run(user_input, session_state, ...):
        if isinstance(event, TextDeltaEvent):
            yield gr.update(value=accumulated_text + event.delta)
        elif isinstance(event, ToolStartEvent):
            yield gr.update(value=f"[searching: {event.name}...]")
        elif isinstance(event, AgentEndEvent):
            session_state.messages = event.messages
            yield gr.update(value=accumulated_text)
```

**Gradio theming contract:**

All Gradio components use `elem_id` and `elem_classes` so custom CSS (injected
via `gr.HTML` or `gr.Blocks(css=...)`) can target them with DESIGN.md tokens.

Example mapping:
```python
gr.Button("Begin", elem_classes=["btn-primary"])  # → amber, DESIGN.md button-primary
gr.Button("Save and continue later", elem_classes=["btn-ghost"])
```

The CSS variable block from `DESIGN.md` tokens is injected as a `:root` block
at app startup. Never hardcode hex values in Python.

---

### 5. Document Generator (`agent/tools/doc_generator.py`)

Generates the Phase 5 document package. Input: completed session object.
Output: list of file paths (PDF + text).

**Documents produced:**

| File | Content | Pre-filled from |
|---|---|---|
| `personal_statement.pdf` | Structured personal statement template | `session.interview.*` |
| `action_plan.pdf` | Country-specific step-by-step action plan | `session.selected_country` + assessment |
| `emergency_contacts.pdf` | UNHCR offices + legal aid orgs | Country lookup tool result |
| `rights_summary_card.pdf` | Plain-language rights card | Selected country asylum law |

**Pre-filling rules:**
- Every pre-filled field is tagged with a visual amber highlight in the PDF
  (per `DESIGN.md §7 document-item`)
- No field is pre-filled with data not present in `session.interview`
- The document generator MUST log every field it fills and its source key

---

## Data Flow: Full Interview → Document

```
User selects language
        │
        ▼
Gradio intake.py → session.language = "fr"
        │
        ▼
agent_loop.run("Begin interview in French", session, ...)
        │  turns: SITUATION → HISTORY → GOALS → REVIEW
        │  tools: none in this phase
        │
        ▼
Events stream back → interview.py renders chat bubbles + structured responders
        │
        ▼
session.state = REVIEW → user confirms summary
        │
        ▼
agent_loop.run("Assess this case", session, thinking_level="medium")
        │
        ▼
  tool: web_search("Ethiopia asylum seeker Sudan UNHCR 2026")
  tool: country_lookup("Kenya", profile={origin:"Ethiopia", persecution:"political"})
  tool: country_lookup("Uganda", ...)
        │
        ▼
Events stream → assessment.py renders reasoning trace progressively
        │
        ▼
AgentEndEvent carries structured assessment JSON in final message
        │
        ▼
session.assessment populated → recommendations.py renders country cards
        │
        ▼
User selects country → session.selected_country = "Kenya"
        │
        ▼
doc_generator.py generates 4 PDFs from session
        │
        ▼
documents.py renders download list + preview
```

---

## Performance Targets

| Metric | Target | Notes |
|---|---|---|
| First agent token latency | < 3s | From user submission to first streaming character |
| Interview turn round-trip | < 8s | Single question turn on 7B model, Ollama local |
| Assessment completion | < 45s | Includes 2–3 tool calls + full reasoning trace |
| Document generation | < 10s | All 4 PDFs |
| App cold start | < 8s | Gradio only — no subprocess spawn needed |

---

## Security and Privacy Constraints

1. **No external logging of personal data.** Session objects are in-memory only
   for the hackathon. No database writes, no external analytics calls.
2. **Tool calls for country data only.** The `web_search` tool MUST be scoped
   to asylum/UNHCR/safety queries. Queries containing personal details from
   the interview MUST NOT be sent to external search APIs.
3. **Document files are ephemeral.** Generated PDFs are stored in a temp
   directory and deleted after download or session end.
4. **No PII in logs.** Log only state transitions and tool call metadata
   (not content). Never log interview answers.

---

## Dependency Versions (pinned)

```
# Python only — no Node.js dependencies
gradio==4.x
weasyprint==62.x
httpx==0.27.x
pytest==8.x
ollama==0.x          # LLM calls to local Ollama instance
litellm==1.x         # Optional: multi-provider abstraction (Ollama, Modal, OpenAI-compatible)
```

Lock file (`requirements.txt`) is committed.
Do not upgrade dependencies during a phase without explicit developer approval.
