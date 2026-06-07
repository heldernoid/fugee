"""app/phases/interview.py — Phase 2 structured interview (deterministic flow).

Design: the **app** deterministically drives a slot-filling interview — a fixed,
ordered set of questions, each with a fixed answer control and a known target
field — and guarantees progression through Situation → History → Goals → Review
→ Assessment. The **LLM** only does what it is reliable at: phrasing each
question warmly in the person's chosen language and acknowledging their previous
answer. The model never decides the input control or the flow, so the UI is
consistent every run (this replaced an earlier, brittle "model emits a
@@RESPONDER directive" approach).

Answers are captured straight from the controls into ``session.interview`` (real
structured data for the assessment facts panel and the document package).
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field

import gradio as gr

from agent.events import AgentEndEvent, ErrorEvent, TextDeltaEvent
from agent.loop import create_loop
from app.countries import country_choices, country_name
from app.prompt_loader import load_prompt
from app.state.session import SessionState, State

# Progress rail (Intake is "done" once the interview starts).
RAIL = [
    ("Intake", State.INTAKE),
    ("Situation", State.SITUATION),
    ("History", State.HISTORY),
    ("Goals", State.GOALS),
    ("Review", State.REVIEW),
]

AGENT_AVATAR = (
    '<svg width="18" height="18" viewBox="0 0 32 32" aria-hidden="true">'
    '<path d="M16 7l7 6.5V25h-4.6v-6.2h-4.8V25H9V13.5L16 7z" fill="#fff"/></svg>'
)


@dataclass
class Slot:
    key: str          # session.interview attribute to fill
    phase: State      # which sub-phase this belongs to
    intent: str       # what to learn (hint for the LLM phrasing)
    control: str      # "country" | "choice" | "text"
    options: list = field(default_factory=list)
    multi: bool = False
    kind: str = "str"  # how to store: str | bool | list | list_text


# The fixed interview plan. Order defines the flow; phase drives the rail.
SLOTS: list[Slot] = [
    Slot("current_country", State.SITUATION, "which country they are currently in", "country"),
    Slot("origin_country", State.SITUATION, "which country they are originally from", "country"),
    Slot("persecution_types", State.SITUATION,
         "the primary reason(s) they had to leave home", "choice",
         ["Political", "Ethnic", "Religious", "Gender-based", "Sexual orientation",
          "Climate displacement", "Other"], multi=True, kind="list"),
    Slot("immediate_danger", State.SITUATION,
         "whether they are in immediate danger right now", "choice", ["Yes", "No"], kind="bool"),
    Slot("displacement_duration", State.HISTORY, "how long ago they had to leave home", "text"),
    Slot("prior_claims", State.HISTORY,
         "whether they have applied for asylum or refugee status anywhere before",
         "choice", ["Yes", "No"], kind="bool"),
    Slot("documents_available", State.HISTORY,
         "which identity or travel documents they still have", "choice",
         ["Passport", "National ID", "Birth certificate", "None", "Other"],
         multi=True, kind="list"),
    Slot("family_situation", State.GOALS, "who they are travelling with (family situation)", "text"),
    Slot("languages_spoken", State.GOALS, "which languages they speak", "text", kind="list_text"),
    Slot("destination_preferences", State.GOALS,
         "whether they have a country or place they would prefer to seek safety in",
         "text", kind="list_text"),
]
REVIEW_INDEX = len(SLOTS)  # the review step sits after the last slot

INTERVIEW_CSS = """
#iv-screen { background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-lg); box-shadow: var(--shadow-md); overflow: hidden;
  max-width: var(--maxw); margin: 0 auto; }

.iv-rail { display:flex; align-items:center; gap:6px; padding:18px clamp(18px,4vw,28px);
  background:var(--surface-2); border-bottom:1px solid var(--line); flex-wrap:wrap; }
.iv-pill { display:flex; align-items:center; gap:8px; font-size:13px; color:var(--text-muted); font-weight:500; }
.iv-pill .dot { width:22px; height:22px; border-radius:var(--r-full); border:1.5px solid var(--line-strong);
  display:flex; align-items:center; justify-content:center; font-size:11px; font-weight:700;
  color:var(--text-muted); background:var(--surface); }
.iv-pill.done .dot { background:var(--primary); border-color:var(--primary); color:#fff; }
.iv-pill.done { color:var(--text-secondary); }
.iv-pill.active .dot { background:var(--accent); border-color:var(--accent); color:#fff; box-shadow:0 0 0 4px var(--accent-tint); }
.iv-pill.active { color:var(--text); font-weight:600; }
.iv-sep { width:18px; height:1.5px; background:var(--line-strong); flex:0 0 auto; }
@media(max-width:620px){ .iv-pill span.t{display:none;} .iv-sep{width:10px;} }

.iv-chat { padding:clamp(18px,4vw,30px); display:flex; flex-direction:column; gap:18px; background:var(--surface); min-height:120px; }
.iv-msg { display:flex; gap:12px; max-width:88%; }
.iv-msg__av { flex:0 0 auto; width:34px; height:34px; border-radius:var(--r-full); background:var(--primary);
  display:flex; align-items:center; justify-content:center; box-shadow:var(--shadow-sm); }
.iv-msg__bubble { padding:13px 16px; border-radius:14px; font-size:15px; line-height:1.55; }
.iv-msg--agent .iv-msg__bubble { background:var(--primary-tint); color:#15302a; border-bottom-left-radius:5px; }
.iv-msg--user { margin-left:auto; flex-direction:row-reverse; }
.iv-msg--user .iv-msg__bubble { background:var(--accent-tint); color:#5c3415; border-bottom-right-radius:5px; }
.iv-msg--user .iv-msg__av { background:var(--accent); }
.iv-msg--user .iv-msg__av span { color:#fff; font-size:13px; font-weight:600; }
.iv-msg--current .iv-msg__bubble { background:var(--surface); border:1.5px solid var(--primary-tint-2);
  box-shadow:var(--shadow-sm); font-weight:500; color:var(--text); }

.iv-thinking { display:inline-flex; align-items:center; gap:9px; font-size:13px; color:var(--text-muted); padding:2px 0 0 46px; }
.iv-thinking .dots { display:inline-flex; gap:4px; }
.iv-thinking .dots i { width:6px; height:6px; border-radius:50%; background:var(--primary); opacity:.4; animation:ivblink 1.2s infinite; display:inline-block; }
.iv-thinking .dots i:nth-child(2){ animation-delay:.2s; }
.iv-thinking .dots i:nth-child(3){ animation-delay:.4s; }
@keyframes ivblink { 0%,60%,100%{opacity:.25;transform:translateY(0);} 30%{opacity:1;transform:translateY(-2px);} }

#iv-responder { border-top:1px solid var(--line); background:var(--surface-2); padding:clamp(16px,4vw,24px); }
#iv-responder .label-row { font-size:12px; letter-spacing:.04em; text-transform:uppercase;
  color:var(--text-muted); font-weight:600; margin-bottom:6px; }
#iv-choice .wrap label, #iv-multi .wrap label { border-radius:var(--r-full) !important; }
#iv-continue, #iv-continue button { background:var(--primary) !important; color:var(--on-primary) !important;
  box-shadow:0 2px 0 var(--primary-deep) !important; border:0 !important; font-weight:600 !important; }
#iv-continue:hover, #iv-continue button:hover { background:var(--primary-deep) !important; }
"""


# --------------------------------------------------------------------------
# Rendering helpers
# --------------------------------------------------------------------------

def render_rail(state: State) -> str:
    pills = []
    for i, (label, st) in enumerate(RAIL):
        if i:
            pills.append('<span class="iv-sep"></span>')
        if state > st:
            cls, dot = "iv-pill done", "✓"
        elif state == st:
            cls, dot = "iv-pill active", str(i + 1) if i else "✓"
        else:
            cls, dot = "iv-pill", str(i + 1)
        pills.append(
            f'<div class="{cls}"><span class="dot">{dot}</span>'
            f'<span class="t">{html.escape(label)}</span></div>'
        )
    return f'<div class="iv-rail" aria-label="Interview progress">{"".join(pills)}</div>'


def _bubble(role: str, text: str, current: bool = False) -> str:
    safe = html.escape(text).replace("\n", "<br>")
    if role == "user":
        return ('<div class="iv-msg iv-msg--user"><div class="iv-msg__av"><span>You</span></div>'
                f'<div class="iv-msg__bubble">{safe}</div></div>')
    cur = " iv-msg--current" if current else ""
    return (f'<div class="iv-msg iv-msg--agent{cur}"><div class="iv-msg__av">{AGENT_AVATAR}</div>'
            f'<div class="iv-msg__bubble">{safe}</div></div>')


def render_chat(messages: list[dict], streaming_text: str | None = None, thinking: bool = False) -> str:
    rows: list[str] = []
    visible = [m for m in messages if m.get("role") in ("user", "assistant")]
    last = len(visible) - 1
    for i, m in enumerate(visible):
        if m["role"] == "assistant":
            if not m.get("content", "").strip():
                continue
            rows.append(_bubble("agent", m["content"], current=(streaming_text is None and i == last)))
        else:
            rows.append(_bubble("user", m["content"]))
    if streaming_text is not None:
        rows.append(_bubble("agent", streaming_text or "…", current=True))
    if thinking:
        rows.append('<div class="iv-thinking" aria-live="polite"><span class="dots">'
                    "<i></i><i></i><i></i></span> Refuge is listening</div>")
    return f'<div class="iv-chat">{"".join(rows)}</div>'


# --------------------------------------------------------------------------
# State helpers
# --------------------------------------------------------------------------

def advance_to(session: SessionState, target) -> None:
    """Step the state machine forward to ``target`` (never backward)."""
    if target is None:
        return
    if isinstance(target, str):
        try:
            target = State[target]
        except KeyError:
            return
    while session.state < target:
        session.advance()


def control_updates(slot: Slot | None):
    """Deterministic (radio, multi, country, text) visibility for a slot."""
    is_single = bool(slot) and slot.control == "choice" and not slot.multi
    is_multi = bool(slot) and slot.control == "choice" and slot.multi
    is_country = bool(slot) and slot.control == "country"
    is_text = bool(slot) and slot.control == "text"
    return (
        gr.update(visible=is_single, choices=slot.options if is_single else [], value=None),
        gr.update(visible=is_multi, choices=slot.options if is_multi else [], value=[]),
        gr.update(visible=is_country, value=None),
        gr.update(visible=is_text, value=""),
    )


def hide_controls():
    return (gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), gr.update(visible=False))


def store_answer(session: SessionState, slot: Slot, radio_v, multi_v, country_v, text_v):
    """Store the control's value into session.interview; return display text or None."""
    if slot.control == "country":
        raw = country_name(country_v) if country_v else (text_v or "").strip()
    elif slot.control == "choice" and slot.multi:
        raw = multi_v or []
    elif slot.control == "choice":
        raw = radio_v or (text_v or "").strip()
    else:
        raw = (text_v or "").strip()

    if not raw:
        return None

    if slot.kind == "bool":
        setattr(session.interview, slot.key, str(raw).strip().lower().startswith("y"))
        return str(raw)
    if slot.kind == "list":
        lst = raw if isinstance(raw, list) else [raw]
        setattr(session.interview, slot.key, lst)
        return ", ".join(lst)
    if slot.kind == "list_text":
        lst = [p.strip() for p in str(raw).replace(";", ",").split(",") if p.strip()]
        setattr(session.interview, slot.key, lst)
        return ", ".join(lst)
    setattr(session.interview, slot.key, str(raw))
    return str(raw)


# --------------------------------------------------------------------------
# LLM phrasing (the only model use in the interview)
# --------------------------------------------------------------------------

def _phrasing_system(session: SessionState, instruction: str) -> str:
    lang = getattr(session, "language", None) or "English"
    return (
        load_prompt("system")
        + f"\n\n# Right now\nReply in {lang}. {instruction} "
        "Ask exactly ONE short question (or give the short summary requested). "
        "Briefly acknowledge what the person just said if relevant. Do not list "
        "answer options, do not add any markup or labels — just speak naturally."
    )


def _facts_recap(session: SessionState) -> str:
    iv = session.interview
    parts = []
    for label, val in [
        ("currently in", iv.current_country), ("originally from", iv.origin_country),
        ("reason for leaving", iv.persecution_types), ("immediate danger", iv.immediate_danger),
        ("time displaced", iv.displacement_duration), ("applied before", iv.prior_claims),
        ("documents", iv.documents_available), ("family", iv.family_situation),
        ("languages", iv.languages_spoken), ("destination preference", iv.destination_preferences),
    ]:
        if val in (None, "", []):
            continue
        if isinstance(val, bool):
            val = "yes" if val else "no"
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val)
        parts.append(f"{label}: {val}")
    return "; ".join(parts)


# --------------------------------------------------------------------------
# UI assembly
# --------------------------------------------------------------------------

@dataclass
class InterviewUI:
    column: gr.Column
    session: gr.State
    loop: gr.State
    slot_idx: gr.State
    start_fn: callable
    start_inputs: list
    stream_outputs: list
    continue_btn: gr.Button
    continue_event: object


def build(visible: bool = True, session_st=None, loop_st=None, slot_idx_st=None) -> InterviewUI:
    session_st = session_st or gr.State(None)
    loop_st = loop_st or gr.State(None)
    slot_idx_st = slot_idx_st or gr.State(0)

    with gr.Column(visible=visible) as column:
        gr.HTML(
            '<div class="phase-head"><span class="ptag">Phase 2 — Structured Interview</span>'
            '<span class="pdesc">A calm, one-question-at-a-time conversation. Refuge offers the '
            "right kind of answer control for each question.</span></div>"
        )
        with gr.Column(elem_id="iv-screen"):
            rail = gr.HTML(render_rail(State.SITUATION))
            chat = gr.HTML(render_chat([], thinking=True))
            with gr.Column(elem_id="iv-responder"):
                gr.HTML('<div class="label-row">Your answer</div>')
                radio = gr.Radio(choices=[], label="", show_label=False, visible=False, elem_id="iv-choice")
                multi = gr.CheckboxGroup(choices=[], label="", show_label=False, visible=False, elem_id="iv-multi")
                country = gr.Dropdown(choices=country_choices(), label="", show_label=False, visible=False,
                                      allow_custom_value=True, filterable=True, elem_id="iv-country")
                text = gr.Textbox(label="", show_label=False, lines=3, visible=True,
                                  placeholder="Type your answer here…", elem_id="iv-text")
                cont = gr.Button("Continue →", elem_id="iv-continue")

    stream_outputs = [chat, rail, radio, multi, country, text, session_st, loop_st, slot_idx_st]

    # -- phrasing turn (stream one question) ----------------------------

    async def _ask(session, loop, instruction, *, welcome=False):
        """Stream an LLM-phrased question; append it to history; return its text."""
        system_prompt = _phrasing_system(session, instruction)
        # Provide the conversation so far for context + acknowledgement.
        ctx = [m for m in session.messages if m.get("role") in ("user", "assistant")]
        nudge = "Greet the person warmly, then ask." if welcome else "Ask the next question now."
        acc = ""
        final = list(session.messages)
        async for ev in loop.run(nudge, type("S", (), {"messages": ctx})(),
                                 system_prompt=system_prompt, thinking_level="off"):
            if isinstance(ev, TextDeltaEvent):
                acc += ev.delta
                yield ("stream", acc)
            elif isinstance(ev, AgentEndEvent):
                final = ev.messages
            elif isinstance(ev, ErrorEvent):
                acc += f"\n\n(Something went wrong: {ev.message})"
                yield ("stream", acc)
        # Persist only the assistant question (drop the internal nudge turn).
        session.messages = list(session.messages) + [{"role": "assistant", "content": acc.strip()}]
        yield ("done", acc.strip())

    def _instruction_for(idx: int, session) -> tuple[str, bool]:
        if idx >= REVIEW_INDEX:
            recap = _facts_recap(session)
            return (f"Summarise back what you understood ({recap}) in 2-3 short sentences, "
                    "then ask the person to confirm it is correct.", False)
        return (f"Learn {SLOTS[idx].intent}.", idx == 0)

    async def _present(session, loop, idx):
        """Advance to the slot's phase, stream its question, then show its control."""
        target_phase = State.REVIEW if idx >= REVIEW_INDEX else SLOTS[idx].phase
        advance_to(session, target_phase)
        instruction, welcome = _instruction_for(idx, session)
        # thinking state
        yield (render_chat(session.messages, thinking=True), render_rail(session.state),
               *hide_controls(), session, loop, idx)
        async for kind, payload in _ask(session, loop, instruction, welcome=welcome):
            if kind == "stream":
                yield (render_chat(session.messages, streaming_text=payload), render_rail(session.state),
                       *hide_controls(), session, loop, idx)
        # show the right control for this step
        if idx >= REVIEW_INDEX:
            ctrl = control_updates(Slot("_", State.REVIEW, "", "choice",
                                        ["Yes, that's correct", "Something needs changing"]))
        else:
            ctrl = control_updates(SLOTS[idx])
        yield (render_chat(session.messages), render_rail(session.state),
               *ctrl, session, loop, idx)

    # -- handlers -------------------------------------------------------

    async def start(session, loop, slot_idx=0):
        if session is None:
            session = SessionState()
            session.transition_to(State.INTAKE)
            loop = create_loop()
        async for out in _present(session, loop, 0):
            yield out

    async def on_continue(radio_v, multi_v, country_v, text_v, session, loop, idx):
        if session is None:
            session = SessionState(); session.transition_to(State.INTAKE); loop = create_loop()
            async for out in _present(session, loop, 0):
                yield out
            return

        # Review step: record the confirmation and stop (assessment is triggered
        # by the chained handler in app.py).
        if idx >= REVIEW_INDEX:
            answer = radio_v or (text_v or "").strip()
            if not answer:
                yield (gr.update(), gr.update(), *hide_controls(), session, loop, idx); return
            session.messages = list(session.messages) + [{"role": "user", "content": answer}]
            yield (render_chat(session.messages, thinking=True), render_rail(session.state),
                   *hide_controls(), session, loop, idx)
            return

        slot = SLOTS[idx]
        display = store_answer(session, slot, radio_v, multi_v, country_v, text_v)
        if display is None:
            # nothing entered — keep the same control visible
            yield (gr.update(), gr.update(), *control_updates(slot), session, loop, idx); return
        session.messages = list(session.messages) + [{"role": "user", "content": display}]
        # move to the next step and present it
        async for out in _present(session, loop, idx + 1):
            yield out

    continue_event = cont.click(
        on_continue,
        inputs=[radio, multi, country, text, session_st, loop_st, slot_idx_st],
        outputs=stream_outputs,
    )

    return InterviewUI(
        column=column, session=session_st, loop=loop_st, slot_idx=slot_idx_st,
        start_fn=start, start_inputs=[session_st, loop_st, slot_idx_st],
        stream_outputs=stream_outputs, continue_btn=cont, continue_event=continue_event,
    )


__all__ = ["build", "InterviewUI", "INTERVIEW_CSS", "SLOTS", "Slot",
           "render_chat", "render_rail", "advance_to", "store_answer", "control_updates"]
