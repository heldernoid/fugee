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
from agent.tools.country_lookup import country_lookup_tool, lookup_country
from agent.tools.web_search import web_search_tool
from app.assessment_parse import parse_assessment
from app.phases.interview import advance_to
from app.prompt_loader import compose
from app.state.session import SessionState, State

ASSESSMENT_TOOLS = [web_search_tool, country_lookup_tool]

# Facts shown in the left panel: (label, attribute, kind). Eight interview
# fields (SC-030).
FACT_FIELDS = [
    ("Country of origin", "origin_country", "text"),
    ("Current location", "current_country", "text"),
    ("Reason for leaving", "persecution_types", "chips"),
    ("Immediate danger", "immediate_danger", "bool"),
    ("Family situation", "family_situation", "text"),
    ("Languages", "languages_spoken", "list"),
    ("Destination preference", "destination_preferences", "list"),
    ("Time displaced", "displacement_duration", "text"),
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
.reason-doc { font-size:14.5px; line-height:1.75; color:var(--text-secondary); }
.reason-doc .ln { display:block; margin-bottom:10px; padding-left:18px; position:relative; }
.reason-doc .ln::before { content:""; position:absolute; left:0; top:9px; width:7px; height:7px; border-radius:50%; background:var(--primary); opacity:.5; }
.reason-doc .ln strong { color:var(--text); font-weight:600; }
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
        visible = "Beginning your assessment…"
    paras = [p.strip() for p in visible.split("\n") if p.strip()]
    lns = "".join(f'<span class="ln">{html.escape(p)}</span>' for p in paras)
    return f'<div class="reason-doc">{lns}</div>'


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
    yield facts_html, render_reason(acc), render_progress(pct, "")

    async for ev in loop.run(
        prompt, session, system_prompt=system_prompt,
        tools=ASSESSMENT_TOOLS, thinking_level="medium",
    ):
        if isinstance(ev, TextDeltaEvent):
            acc += ev.delta
            yield facts_html, render_reason(acc), render_progress(pct, status)
        elif isinstance(ev, ToolStartEvent):
            status = _tool_status(ev.name, ev.args)
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
    recs: list[dict] = []
    seen: set[str] = set()
    for name in result.countries:
        rec = lookup_country(name)
        if rec.get("error"):
            continue
        cname = (rec.get("country") or "").strip()
        if cname.lower() == origin or cname.lower() in seen:
            continue
        seen.add(cname.lower())
        recs.append(rec)

    session.assessment.convention_grounds = result.grounds
    session.assessment.risk_level = result.risk
    session.assessment.reasoning_trace = visible
    session.assessment.recommended_countries = recs
    advance_to(session, State.RECOMMENDATIONS)

    yield render_facts(session), render_reason(acc), render_progress(100, "")


# --------------------------------------------------------------------------
# UI assembly
# --------------------------------------------------------------------------

@dataclass
class AssessmentUI:
    column: gr.Column
    facts: gr.HTML
    reason: gr.HTML
    progress: gr.HTML
    start_fn: callable
    outputs: list


def build(visible: bool = False, session_st: gr.State | None = None, loop_st: gr.State | None = None) -> AssessmentUI:
    session_st = session_st or gr.State(None)
    loop_st = loop_st or gr.State(None)

    with gr.Column(elem_id="assess-screen", visible=visible) as column:
        with gr.Row(elem_classes=["assess"]):
            facts = gr.HTML('<aside class="assess__facts"></aside>')
            with gr.Column(elem_classes=["assess__reason"]):
                progress = gr.HTML(render_progress(0, ""))
                reason = gr.HTML('<div class="reason-doc"></div>')

    outputs = [facts, reason, progress, session_st]

    async def start(session, loop):
        async for facts_html, reason_html, progress_html in stream_assessment(session, loop):
            yield facts_html, reason_html, progress_html, session

    return AssessmentUI(
        column=column, facts=facts, reason=reason, progress=progress,
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
