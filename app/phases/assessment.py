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
from agent.tools.country_lookup import country_lookup_tool, lookup_country
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


def _synth_reasoning(session: SessionState, result, recs: list[dict]) -> str:
    """Readable fallback summary if the model returned only the structured block."""
    iv = session.interview
    lines = []
    if iv.origin_country:
        lines.append(f"Based on what you shared, you are from {iv.origin_country}"
                     + (f" and are currently in {iv.current_country}" if iv.current_country else "") + ".")
    if iv.free_text_history:
        lines.append(f"You told me: {iv.free_text_history}")
    ct = result.case_type or session.assessment.case_type
    if ct:
        lines.append(f"This appears to be {_CASE_LABEL.get(ct, ct)}.")
    if result.grounds:
        lines.append("Relevant ground(s): " + ", ".join(result.grounds) + ".")
    if result.risk:
        lines.append(f"Overall risk: {result.risk}.")
    if recs:
        names = ", ".join(r.get("country", "") for r in recs if r.get("country"))
        if names:
            lines.append(f"Realistic destinations to consider: {names}.")
    if not lines:
        lines.append("I could not complete a full assessment from the information provided.")
    return "\n".join(lines)


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
        for name in names:
            rec = lookup_country(name)
            if rec.get("error"):
                continue
            cname = (rec.get("country") or "").strip()
            if not cname or cname.lower() == origin or cname.lower() in seen:
                continue
            seen.add(cname.lower())
            into.append(rec)

    recs: list[dict] = []
    seen: set[str] = set()
    _collect(result.countries, recs, seen)
    # Fallback: if the structured block yielded no resolvable countries, use the
    # ones the agent actually looked up during reasoning (real, not fabricated).
    if not recs:
        _collect(looked_up, recs, seen)

    # Guarantee a readable reasoning even if the model skipped narration.
    if len(visible.strip()) < 80:
        visible = _synth_reasoning(session, result, recs)

    session.assessment.convention_grounds = result.grounds
    session.assessment.risk_level = result.risk
    session.assessment.case_type = result.case_type
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

    with gr.Column(visible=visible) as column:
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
