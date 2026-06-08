"""app/phases/assessment.py — Phase 3 situation assessment (T037-T040).

Matches mockup.html #phase-3: a facts sidebar (what the person shared) and a
live reasoning stream the person can watch, with a progress bar and tool-call
status chips ("Searching: …"). The agent reasons with the real ``web_search``
and ``country_lookup`` tools; its final ``@@ASSESSMENT`` block is parsed into
``session.assessment`` (convention grounds, risk, ranked recommended countries
attached with authoritative country_lookup data — never the origin country).
"""

from __future__ import annotations

import html
from dataclasses import dataclass

import gradio as gr

from agent.events import ErrorEvent, TextDeltaEvent, ToolEndEvent, ToolStartEvent
from agent.loop import LoopHooks
from agent.tools.asylum_stats import asylum_stats_tool
from agent.tools.country_lookup import (
    country_lookup_tool,
    lookup_country,
    strong_asylum_destinations,
    work_route_countries,
)
from agent.tools.guideline_search import guideline_search_tool
from app.assessment_parse import parse_assessment
from app.mdlite import md_to_html
from app.phases.interview import advance_to
from app.prompt_loader import compose
from app.state.session import SessionState, State

# Web search is intentionally OFF: the assessment is grounded only in sources we
# control — the curated country data (country_lookup / asylum_stats) and the
# UNHCR guidelines (guideline_search) — so it can't surface unvetted web claims.
ASSESSMENT_TOOLS = [guideline_search_tool, country_lookup_tool, asylum_stats_tool]

# Facts shown in the left panel: (label, attribute, kind). Eight interview
# fields (SC-030).
FACT_FIELDS = [
    ("Country of origin", "origin_country", "text"),
    ("Current location", "current_country", "text"),
    ("What happened", "free_text_history", "text"),
    ("Reason", "persecution_types", "chips"),
    ("Immediate danger", "immediate_danger", "bool"),
    ("Time displaced", "displacement_duration", "text"),
    ("Documents", "documents_available", "list"),
    ("Languages", "languages_spoken", "list"),
    ("Destination preference", "destination_preferences", "list"),
]

ASSESSMENT_CSS = """
#assess-screen { background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-lg); box-shadow: var(--shadow-md); overflow: hidden;
  max-width: 1180px; margin: 0 auto; }
.assess { display:grid; grid-template-columns:300px 1fr; }
@media(max-width:760px){ .assess { grid-template-columns:1fr; } }
.assess__facts { background:var(--surface-2); border-right:1px solid var(--line); padding:clamp(18px,4vw,26px); }
@media(max-width:760px){ .assess__facts { border-right:0; border-bottom:1px solid var(--line); } }
.assess__facts h3 { font-family:var(--font-ui); font-size:15px; font-weight:700; margin:0 0 16px; color:var(--text); }
.assess .fact { padding:12px 0; border-bottom:1px solid var(--line); }
.assess .fact:last-child { border-bottom:0; }
.assess .fact dt { font-size:11.5px; letter-spacing:.06em; text-transform:uppercase; color:var(--text-muted); font-weight:600; margin-bottom:3px; }
.assess .fact dd { margin:0; font-size:14.5px; color:var(--text); font-weight:500; }
.assess .chip { display:inline-block; background:var(--primary-tint); color:var(--primary-deep); font-size:12px; font-weight:600; padding:3px 9px; border-radius:var(--r-full); margin:2px 4px 2px 0; }

.assess__reason { padding:clamp(18px,4vw,28px); background:var(--surface); position:relative; }
.assess__bar { margin-bottom:20px; }
.assess__bar .row { display:flex; justify-content:space-between; align-items:baseline; font-size:13px; color:var(--text-secondary); margin-bottom:8px; }
.assess__bar .row b { color:var(--text); font-weight:600; }
.assess .track { height:8px; border-radius:var(--r-full); background:var(--primary-tint-2); overflow:hidden; }
.assess .track > i { display:block; height:100%; border-radius:var(--r-full);
  background:linear-gradient(90deg,var(--primary),var(--secondary)); transition:width .6s cubic-bezier(.4,0,.1,1); }
.assess .tool-chip { display:inline-flex; align-items:center; gap:7px; margin-top:10px; font-size:12.5px;
  font-weight:600; color:var(--primary-deep); background:var(--primary-tint); padding:5px 11px; border-radius:var(--r-full); }
.reason-doc { font-size:14.5px; line-height:1.7; color:var(--text-secondary); }
.reason-doc p { margin:0 0 12px; }
.reason-doc h4 { font-family:var(--font-ui); font-size:14px; font-weight:700; color:var(--text);
  margin:18px 0 8px; letter-spacing:.01em; }
.reason-doc strong { color:var(--text); font-weight:600; }
.reason-doc em { font-style:italic; }
.reason-doc ul, .reason-doc ol { margin:0 0 12px; padding-left:20px; }
.reason-doc li { margin-bottom:6px; }
.reason-doc code { background:var(--primary-tint); padding:1px 5px; border-radius:4px; font-size:13px; }
#assess-proceed-row { padding:18px clamp(18px,4vw,28px); border-top:1px solid var(--line); justify-content:flex-end; }
#assess-proceed, #assess-proceed button { background:var(--accent) !important; color:var(--on-accent) !important;
  box-shadow:0 2px 0 var(--accent-deep) !important; border:0 !important; font-weight:600 !important;
  border-radius:var(--r-md) !important; padding:13px 24px !important; }
#assess-proceed:hover, #assess-proceed button:hover { background:var(--accent-deep) !important; }
"""


# --------------------------------------------------------------------------
# Rendering helpers
# --------------------------------------------------------------------------

def _fact_value(interview, attr: str, kind: str) -> str:
    val = getattr(interview, attr, None)
    if val is None or val == [] or val == "":
        return '<span style="color:var(--text-muted)">—</span>'
    if kind == "bool":
        return "Yes" if val else "No"
    if kind == "chips":
        return "".join(f'<span class="chip">{html.escape(str(v))}</span>' for v in val)
    if kind == "list":
        return html.escape(", ".join(str(v) for v in val))
    return html.escape(str(val))


def render_facts(session: SessionState) -> str:
    rows = []
    for label, attr, kind in FACT_FIELDS:
        rows.append(
            f'<div class="fact"><dt>{html.escape(label)}</dt>'
            f'<dd>{_fact_value(session.interview, attr, kind)}</dd></div>'
        )
    return (
        '<aside class="assess__facts" aria-label="What you have shared">'
        "<h3>What you've shared</h3><dl style=\"margin:0\">" + "".join(rows) + "</dl></aside>"
    )


def render_reason(text: str) -> str:
    visible, _ = parse_assessment(text)
    if not visible.strip():
        return '<div class="reason-doc"><p>Beginning your assessment…</p></div>'
    return f'<div class="reason-doc">{md_to_html(visible)}</div>'


def render_progress(pct: int, status: str = "") -> str:
    pct = max(0, min(100, int(pct)))
    chip = ""
    if status:
        chip = f'<div class="tool-chip">🔎 {html.escape(status)}</div>'
    return (
        '<div class="assess__bar"><div class="row">'
        f"<span>Assessing your case…</span><b>{pct}%</b></div>"
        f'<div class="track"><i style="width:{pct}%"></i></div>{chip}</div>'
    )


_CASE_LABEL = {
    "refugee": "a refugee claim under the 1951 Refugee Convention",
    "broader_protection": "a claim for broader protection (e.g. fleeing conflict)",
    "statelessness": "a statelessness case",
    "economic_or_other": "mainly economic or other migration rather than a protection claim",
    "unclear": "a case that needs more information to classify",
}


# Maps the interview's persecution-type labels to 1951 Convention grounds, so a
# substantive analysis can be derived deterministically even if the model is terse.
_GROUND_MAP = {
    "Political": "political opinion",
    "Ethnic": "race or nationality (ethnicity)",
    "Religious": "religion",
    "Gender-based": "membership of a particular social group (gender)",
    "Sexual orientation": "membership of a particular social group (sexual orientation)",
}


def _derive_case(session: SessionState) -> tuple[str, list[str], str]:
    """Deterministic (case_type, grounds, risk) read from the interview alone —
    the safety net when the model returns nothing parseable."""
    iv = session.interview
    types = iv.persecution_types or []
    grounds = [_GROUND_MAP[t] for t in types if t in _GROUND_MAP]
    if grounds:
        case = "refugee"
    elif "Climate displacement" in types:
        case = "broader_protection"
    elif iv.immediate_danger:
        case = "unclear"
    else:
        case = "economic_or_other"
    risk = "high" if iv.immediate_danger else ("moderate" if grounds else "low")
    return case, grounds, risk


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def _rec_reason(rec: dict) -> str:
    bits = []
    if rec.get("unhcrOffice"):
        bits.append(f"UNHCR office in {rec['unhcrOffice']}")
    elif rec.get("unhcrPresence"):
        bits.append("UNHCR presence")
    rate = rec.get("acceptanceRate")
    if rate not in (None, "", "PENDING"):
        try:
            pct = float(rate)
            pct = pct * 100 if pct <= 1 else pct
            bits.append(f"~{round(pct)}% recognition recently")
        except (TypeError, ValueError):
            pass
    langs = rec.get("languages") or ([rec["primaryLanguage"]] if rec.get("primaryLanguage") else [])
    if langs:
        bits.append(f"{', '.join(langs[:2])} spoken")
    return "; ".join(bits)


def _synth_reasoning(session: SessionState, result, recs: list[dict],
                     case_type: str, grounds: list[str], risk: str) -> str:
    """A substantive, readable analysis built deterministically from the facts —
    used when the model's own narration was too thin to show. Markdown so the
    renderer gives it structure (bold, bullets)."""
    iv = session.interview
    in_origin = bool(iv.current_country and iv.origin_country
                     and iv.current_country.strip().lower() == iv.origin_country.strip().lower())
    paras: list[str] = []

    # 1 — the situation
    where = f"you are from **{iv.origin_country}**" if iv.origin_country else "I've read your situation"
    if in_origin:
        where += f", and you are still inside {iv.current_country} — the country you fear"
    elif iv.current_country:
        where += f", and you are now in **{iv.current_country}**"
    p1 = f"Based on what you shared, {where}."
    if iv.free_text_history:
        p1 += f" In your words: “{iv.free_text_history.strip().rstrip('.')}.”"
    paras.append(p1)

    # 2 — what kind of case this is
    g = result.grounds or grounds
    p2 = f"**What this means:** this looks like {_CASE_LABEL.get(case_type, case_type)}."
    if g:
        p2 += f" The Convention ground that fits your situation is {_join(g)}."
    if case_type == "refugee":
        p2 += (" Under the 1951 Refugee Convention, a person with a well‑founded fear "
               "of persecution on such a ground, who cannot rely on their own state for "
               "protection, qualifies for refugee status.")
    paras.append(p2)

    # 3 — risk and why protection must be sought elsewhere
    r = (result.risk or risk or "").lower()
    risk_word = {"high": "high", "moderate": "moderate", "low": "lower"}.get(r, r)
    if risk_word:
        p3 = f"**The risk you face looks {risk_word}**"
        p3 += ", and you told me you are in immediate danger." if iv.immediate_danger else "."
        if in_origin and case_type in ("refugee", "broader_protection", "unclear"):
            p3 += (f" Because you are still in {iv.current_country}, you cannot be protected "
                   "there — to claim asylum you will need to reach a country with an active "
                   "asylum system and register with UNHCR or the authorities on arrival.")
        paras.append(p3)

    # 4 — where to go
    if recs and case_type == "economic_or_other":
        names = _join([r_.get("country", "") for r_ in recs])
        paras.append("Asylum is not the right route for this. Countries with accessible "
                     f"work‑visa pathways for foreign workers to consider: **{names}** — "
                     "read each one's conditions carefully.")
    elif recs:
        lines = []
        for rec in recs[:3]:
            reason = _rec_reason(rec)
            lines.append(f"- **{rec.get('country')}**" + (f" — {reason}" if reason else ""))
        paras.append("**Realistic places to seek protection**, with active asylum "
                     "programmes that fit your profile:\n" + "\n".join(lines))

    # 5 — what's next
    if case_type != "economic_or_other" and recs:
        paras.append("Next I'll show you these destinations with a step‑by‑step roadmap, "
                     "and prepare your documents so you're ready to file.")
    return "\n\n".join(paras)


def _facts_summary(session: SessionState) -> str:
    """Plain-text recap of the interview to seed the assessment prompt."""
    iv = session.interview
    bits = []
    for label, attr, _kind in FACT_FIELDS:
        val = getattr(iv, attr, None)
        if val in (None, [], ""):
            continue
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val)
        bits.append(f"- {label}: {val}")
    return "\n".join(bits)


# --------------------------------------------------------------------------
# Streaming core (used by both the UI handler and the integration test)
# --------------------------------------------------------------------------

def _tool_status(name: str, args: dict) -> str:
    if name == "web_search":
        return f"Searching: {args.get('query', '')}"
    if name == "country_lookup":
        return f"Looking up: {args.get('country', '')}"
    if name == "asylum_stats":
        return f"Checking acceptance rates: {args.get('origin', '')} → {args.get('asylum', '')}"
    if name == "guideline_search":
        return f"Consulting UNHCR guidelines: {args.get('query', '')}"
    return f"Running: {name}"


async def stream_assessment(session: SessionState, loop):
    """Run the assessment turn. Yields (facts_html, reason_html, progress_html);
    mutates ``session.assessment``. Uses the real model + real tools."""
    if session.state < State.ASSESSMENT:
        advance_to(session, State.ASSESSMENT)

    facts_html = render_facts(session)
    system_prompt = compose("system", "assessment")
    summary = _facts_summary(session)
    prompt = (
        "Please assess my situation now, based on what I have told you. Work "
        "through your steps, use your tools for country facts and current "
        "information, and end with your structured summary.\n\n"
        + (f"What I told you:\n{summary}" if summary else "")
    )

    acc = ""
    pct = 5
    status = ""
    looked_up: list[str] = []  # countries the agent actually researched

    # Agentic control (ported from pi's AgentLoopConfig hooks):
    #  * stop once the structured @@ASSESSMENT block is produced (no rambling)
    #  * privacy guard: never let the person's free-text story into a web query
    def _stop(assistant_message, history):
        return "@@ASSESSMENT" in (assistant_message or {}).get("content", "")

    story = (session.interview.free_text_history or "").strip().lower()

    def _guard(name, args):
        if name == "web_search" and story:
            q = str((args or {}).get("query", "")).lower()
            if story and (story[:40] in q):
                return {"block": True, "reason": "query contained personal narrative (privacy)"}
        return None

    hooks = LoopHooks(should_stop_after_turn=_stop, before_tool_call=_guard)

    yield facts_html, render_reason(acc), render_progress(pct, "")

    async for ev in loop.run(
        prompt, session, system_prompt=system_prompt,
        tools=ASSESSMENT_TOOLS, thinking_level="off", hooks=hooks,
    ):
        if isinstance(ev, TextDeltaEvent):
            acc += ev.delta
            yield facts_html, render_reason(acc), render_progress(pct, status)
        elif isinstance(ev, ToolStartEvent):
            status = _tool_status(ev.name, ev.args)
            if ev.name == "country_lookup":
                c = (ev.args or {}).get("country")
                if c:
                    looked_up.append(c)
            pct = min(90, pct + 12)
            yield facts_html, render_reason(acc), render_progress(pct, status)
        elif isinstance(ev, ToolEndEvent):
            pct = min(92, pct + 6)
            yield facts_html, render_reason(acc), render_progress(pct, status)
        elif isinstance(ev, ErrorEvent):
            acc += f"\n\n(Something went wrong: {ev.message})"
            yield facts_html, render_reason(acc), render_progress(pct, status)

    visible, result = parse_assessment(acc)
    origin = (session.interview.origin_country or "").strip().lower()

    def _collect(names: list[str], into: list[dict], seen: set[str]) -> None:
        # Protection-case destinations only: a country must actually be a party to
        # the Refugee Convention. Non-signatories (e.g. Pakistan) have no asylum
        # system, so recommending them — or showing a UNHCR/RSD roadmap for them —
        # would be misleading.
        for name in names:
            rec = lookup_country(name)
            if rec.get("error") or not rec.get("isSignatory"):
                continue
            cname = (rec.get("country") or "").strip()
            if not cname or cname.lower() == origin or cname.lower() in seen:
                continue
            seen.add(cname.lower())
            into.append(rec)

    # Fall back to a deterministic read of the interview for anything the model
    # left blank, so the case is never classified as "nothing".
    case_d, grounds_d, risk_d = _derive_case(session)
    case_type = result.case_type or case_d

    def _add(rec: dict) -> None:
        cname = (rec.get("country") or "").strip()
        if cname and not rec.get("error") and cname.lower() != origin and cname.lower() not in seen:
            seen.add(cname.lower())
            recs.append(rec)

    recs: list[dict] = []
    seen: set[str] = set()
    if case_type == "economic_or_other":
        # Not a protection case: asylum destinations would be misleading. Use the
        # curated labour-migration shortlist (work-visa countries) deterministically
        # — never the small model's possibly-Western asylum picks.
        for rec in work_route_countries():
            _add(rec)
    else:
        _collect(result.countries, recs, seen)
        # Fallback: the countries the agent actually looked up during reasoning…
        if not recs:
            _collect(looked_up, recs, seen)
        # …and a last-resort curated shortlist so the screen is never empty.
        if not recs:
            for rec in strong_asylum_destinations():
                _add(rec)

    # Guarantee a substantive reasoning even if the model's narration was thin.
    if len(visible.strip()) < 120:
        visible = _synth_reasoning(session, result, recs, case_type, grounds_d, risk_d)

    session.assessment.convention_grounds = result.grounds or grounds_d
    session.assessment.risk_level = result.risk or risk_d
    session.assessment.case_type = case_type
    session.assessment.reasoning_trace = visible
    session.assessment.recommended_countries = recs
    advance_to(session, State.RECOMMENDATIONS)

    yield render_facts(session), render_reason(visible), render_progress(100, "")


# --------------------------------------------------------------------------
# UI assembly
# --------------------------------------------------------------------------

@dataclass
class AssessmentUI:
    column: gr.Column
    facts: gr.HTML
    reason: gr.HTML
    progress: gr.HTML
    proceed: gr.Button
    start_fn: callable
    outputs: list


def build(visible: bool = False, session_st: gr.State | None = None, loop_st: gr.State | None = None) -> AssessmentUI:
    session_st = session_st or gr.State(None)
    loop_st = loop_st or gr.State(None)

    with gr.Column(visible=visible, elem_classes=["screen-wrap"]) as column:
        with gr.Column(elem_id="assess-screen"):
            with gr.Row(elem_classes=["assess"]):
                facts = gr.HTML('<aside class="assess__facts"></aside>')
                with gr.Column(elem_classes=["assess__reason"]):
                    progress = gr.HTML(render_progress(0, ""))
                    reason = gr.HTML('<div class="reason-doc"></div>')
            with gr.Row(elem_id="assess-proceed-row"):
                proceed = gr.Button("See your recommendations →", elem_id="assess-proceed", visible=False)

    # outputs order: facts, reason, progress, proceed(button), session
    outputs = [facts, reason, progress, proceed, session_st]

    async def start(session, loop):
        last = (gr.update(), gr.update(), gr.update())
        async for facts_html, reason_html, progress_html in stream_assessment(session, loop):
            last = (facts_html, reason_html, progress_html)
            # keep the proceed button hidden while reasoning streams
            yield facts_html, reason_html, progress_html, gr.update(visible=False), session
        # done — let the person read, then choose to continue
        yield last[0], last[1], last[2], gr.update(visible=True, value="See your recommendations →"), session

    return AssessmentUI(
        column=column, facts=facts, reason=reason, progress=progress, proceed=proceed,
        start_fn=start, outputs=outputs,
    )


__all__ = [
    "build",
    "AssessmentUI",
    "ASSESSMENT_CSS",
    "stream_assessment",
    "render_facts",
    "render_reason",
    "render_progress",
    "ASSESSMENT_TOOLS",
]
