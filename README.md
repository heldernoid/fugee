---
title: Fugee
emoji: 🏠
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 6.15.2
app_file: app/app.py
pinned: false
license: mit
short_description: Agentic AI guidance for displaced people, on a small (≤32B) LLM
---

<!-- The block above is Hugging Face Space metadata (required for the Space to
     build). The hackathon submission tool appends track/badge tags to it. -->

<div align="center">

# 🏠 Fugee

**Safe guidance for people on the move.**

An agentic AI assistant for displaced people, asylum seekers, and refugees —
powered by a small (≤32B) local LLM.

</div>

---

## What it is

Fugee conducts a calm, structured, multilingual interview, reasons about the
person's situation against international refugee law (the 1951 Refugee
Convention and the 1969 AU Convention), recommends realistic destination
countries, and generates a personalised documentation package they can download
and edit.

It is a **single-process Gradio web app** backed by a **pure-Python agent loop**
(`agent/loop.py`, ported from pi-agent-core's patterns) and a **small (≤32B) LLM**
served by Ollama. No Node.js, no microservices, no external database.

> **This Space** runs the Gradio UI on free CPU and calls the LLM (`lfm2.5:8b`)
> and embeddings (`nomic-embed-text`) on a GPU **Ollama** endpoint hosted on
> [Modal](https://modal.com) — so the same code and the same small model run
> unchanged, just on rented GPU. See [`deploy/DEPLOY.md`](deploy/DEPLOY.md).

The design point: *a genuinely useful agentic product running on a small model.*
The interview is fully **deterministic** (fixed questions and controls,
hand-translated into 10 languages) and the LLM is used only where it adds real
intelligence — the legal **assessment**, the document **drafting**, and the
spoken-back **review summary**.

### The five phases

1. **Intake** — language selection + a calm welcome.
2. **Interview** — a fixed, deterministic question flow (current/origin country,
   what happened, persecution grounds, danger, documents, languages, goals).
3. **Assessment** — the agent reasons openly about the case: classifies it
   (refugee / broader protection / statelessness / economic), names the
   Convention ground, gauges risk, and ranks destinations. Grounded in curated
   country data and the UNHCR Handbook & Guidelines (RAG) — **not** the open web.
4. **Recommendations** — 2–3 country cards with real UNHCR/processing data and a
   step-by-step roadmap. Economic (non-protection) cases get honest **work-route**
   guidance instead of a doomed asylum claim.
5. **Documents** — an LLM-drafted, editable **Word (.docx) + PDF** package,
   branded and laid out with bundled fonts (fully offline).

---

## Requirements

- **Python ≥ 3.10**
- **[Ollama](https://ollama.com)** running somewhere you can reach (local or LAN),
  with:
  - a **tool-calling-capable instruct model, ≤32B** (e.g. `lfm2.5:8b`,
    `qwen2.5:7b`, `gemma2:9b`), and
  - **`nomic-embed-text`** (used to build the UNHCR-guidelines search index).
- A few hundred MB of disk for the Python deps and the (regenerable) RAG index.

> No Node.js / npm anywhere — Fugee is pure Python.

---

## Quick start

```bash
# 1. Clone and enter the repo
cd fugee

# 2. Create a virtualenv and install deps  (uv recommended; plain venv also fine)
uv venv && source .venv/bin/activate          # or: python -m venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt            # or: pip install -r requirements.txt

# 3. Configure the model + host
cp .env.example .env
#   then edit .env:  set OLLAMA_HOST and MODEL_ID to what your Ollama actually has

# 4. Pull the models on your Ollama host (skip any you already have)
ollama pull lfm2.5:8b          # or your chosen ≤32B instruct model
ollama pull nomic-embed-text   # embeddings for the guidelines RAG index

# 5. Build the UNHCR-guidelines search index (one-time; regenerable, gitignored)
python data/scripts/build_guidelines_index.py

# 6. Run the app
python app/app.py
```

Open **http://localhost:7860** in a browser. (The server binds `0.0.0.0:7860`, so
it's reachable from other machines on your network too.)

### Configuration (`.env`)

Read at startup by `app/config.py` (no `python-dotenv` dependency):

| Variable        | Meaning                                                        | Example |
|-----------------|----------------------------------------------------------------|---------|
| `OLLAMA_HOST`   | Base URL of the Ollama server (local, LAN, or Modal endpoint)  | `http://127.0.0.1:11434` |
| `MODEL_ID`      | The single ≤32B tool-calling instruct model for the whole app  | `lfm2.5:8b` |
| `MODEL_PROVIDER`| `ollama` (default) or a litellm provider name                  | `ollama` |
| `NUM_CTX`       | Ollama context window — keep large; the small default truncates the assessment prompt | `16384` |
| `MODAL_KEY` / `MODAL_SECRET` | Proxy-auth headers when `OLLAMA_HOST` is a protected Modal endpoint (hosted demo only) | — |

> **One model, no fallback.** The hackathon build deliberately uses a single
> small model end to end. `web_search` is **disabled** — the assessment is
> grounded only in sources we control (curated country data + UNHCR guidelines),
> so no Tavily key is required.

---

## Live demo: Hugging Face Space + Modal

The deployed demo splits into two pieces so it runs **free** and **fast** without
changing the app or the model:

```
HF Space (free CPU, Gradio)            Modal (GPU, Ollama)
┌──────────────────────────┐  HTTPS   ┌──────────────────────────────┐
│ app/app.py + curated data │ ───────▶ │ ollama serve                 │
│ + guidelines RAG (cosine) │  proxy   │   • lfm2.5:8b   (assessment) │
│ OLLAMA_HOST → Modal URL   │  auth    │   • nomic-embed-text  (RAG)  │
└──────────────────────────┘          └──────────────────────────────┘
```

The Space sets `OLLAMA_HOST` to the Modal endpoint and sends the proxy-auth
headers (`agent/ollama_auth.py`); everything else is identical to local. Full,
copy-pasteable steps — create the Space, deploy Modal, set secrets, upload the
RAG index — are in **[`deploy/DEPLOY.md`](deploy/DEPLOY.md)**.

---

## Project layout

```
fugee/
├── agent/                  # Pure-Python agent loop + tools
│   ├── loop.py             #   while-loop, typed events, hooks, steering (ported from pi)
│   ├── drafting.py         #   LLM document drafting
│   └── tools/              #   country_lookup, asylum_stats, guideline_search, doc_generator
├── app/                    # Gradio application
│   ├── app.py              #   entrypoint — `python app/app.py`
│   ├── phases/             #   intake / interview / assessment / recommendations / documents
│   ├── interview_script.py #   fixed questions + 10-language translations
│   ├── state/session.py    #   forward-only interview state machine
│   └── prompts/            #   system / assessment prompts (Markdown)
├── data/scripts/           # UNHCR data pipeline + guidelines RAG index builder
├── specs/                  # PLAN.md, ARCHITECTURE.md, ISSUES.md, curated country data
│   └── data/countries.json #   authoritative country reference (signatories + non-signatories)
├── tests/                  # unit / integration (no model) + e2e (real model)
├── DESIGN.md               # design tokens (authoritative)
├── mockup.html             # visual reference for every phase
├── CLAUDE.md               # agent working rules for this repo
└── requirements.txt
```

---

## Running the tests

```bash
# Fast: pure logic + phase integration (no model needed)
pytest tests/unit tests/integration -v

# End-to-end with a real model (needs Ollama + your MODEL_ID)
pytest tests/e2e -v
```

Testing philosophy: unit tests stub only at the network boundary; E2E uses real
model calls. Tools never fabricate data — a failed lookup surfaces an error
rather than inventing one.

---

## Languages

English · Français · Español · Português · العربية · हिन्दी · 中文 · 日本語 · 한국어 · Русский

The interview questions, options, and chrome are hand-translated for all ten.

---

## For contributors / agents

- **`CLAUDE.md`** — the single source of truth for how to work in this repo
  (critical rules, design authority, sign-off gates). Read it first.
- **`DESIGN.md` + `mockup.html`** — authoritative for every visual decision.
- **`specs/ISSUES.md`** — hard-won gotchas and their real fixes (e.g. the Gradio
  `CheckboxGroup` reveal bug). Read before touching the interview UI or the
  assessment/recommendation logic — it will save you a long debugging loop.
- **`specs/ARCHITECTURE.md` / `specs/PLAN.md`** — system design and phased plan.

---

## Status & disclaimer

Built for the **Hugging Face Build Small Hackathon (June 2026)**. Quality bar:
demo-ready, real-user-usable.

Fugee provides **guidance, not legal advice**. It helps a person understand and
prepare; it is not a substitute for a qualified immigration lawyer or an accredited
adviser. It is deliberately honest about what does and does not qualify for
protection — wrong output is worse than no output.
