"""app/phases/interview.py — Phase 2 structured interview screen (T022-T025).

Renders the interview as in mockup.html #phase-2: a progress rail, agent/user
chat bubbles, a "Refuge is listening" thinking indicator, and a structured
responder that switches between Choice pills / Country selector / Free text based
on the agent's ``@@RESPONDER`` directive. Agent replies stream token-by-token via
``AgentLoop.run`` (no buffering).

State lives in per-session ``gr.State`` (session, loop, current responder spec),
so concurrent sessions stay isolated (T019).
"""

from __future__ import annotations

import html
from dataclasses import dataclass

import gradio as gr

from agent.events import AgentEndEvent, ErrorEvent, TextDeltaEvent
from agent.loop import create_loop
from app.countries import country_choices, country_name
from app.prompt_loader import interview_system_prompt
from app.responder import ResponderSpec, parse, strip_directive
from app.state.session import SessionState, State

# Order of the progress rail (Intake is "done" once the interview starts).
RAIL = [
    ("Intake", State.INTAKE),
    ("Situation", State.SITUATION),
    ("History", State.HISTORY),
    ("Goals", State.GOALS),
    ("Review", State.REVIEW),
]

# Internal first-turn instruction — never shown to the person or resent.
BOOTSTRAP = "Please begin the interview now with your first question."


def _bootstrap_for(session) -> str:
    """First-turn instruction, asking the agent to greet in the chosen language."""
    lang = getattr(session, "language", None)
    if lang:
        return (
            f"The person has chosen to continue in {lang}. Greet them warmly and ask "
            f"your first question in {lang}. {BOOTSTRAP}"
        )
    return BOOTSTRAP

AGENT_AVATAR = (
    '<svg width="18" height="18" viewBox="0 0 32 32" aria-hidden="true">'
    '<path d="M16 7l7 6.5V25h-4.6v-6.2h-4.8V25H9V13.5L16 7z" fill="#fff"/></svg>'
)

# CSS lifted from mockup.html #phase-2 — variable names already match the
# injected :root block (app/design_tokens.py).
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

.iv-chat { padding:clamp(18px,4vw,30px); display:flex; flex-direction:column; gap:18px; background:var(--surface); }
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
  color:var(--text-muted); font-weight:600; }

/* Native Gradio controls themed to match the responder */
#iv-choice .wrap label, #iv-multi .wrap label { border-radius:var(--r-full) !important; }
#iv-continue button { background:var(--primary) !important; color:var(--on-primary) !important;
  box-shadow:0 2px 0 var(--primary-deep) !important; border:0 !important; font-weight:600 !important; }
#iv-continue button:hover { background:var(--primary-deep) !important; }
#iv-save button { background:transparent !important; color:var(--primary-deep) !important;
  border:0 !important; box-shadow:none !important; font-weight:600 !important; }
#iv-save button:hover { background:var(--primary-tint) !important; }
"""


# --------------------------------------------------------------------------
# Rendering helpers (pure functions → HTML)
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
        return (
            '<div class="iv-msg iv-msg--user"><div class="iv-msg__av"><span>You</span></div>'
            f'<div class="iv-msg__bubble">{safe}</div></div>'
        )
    cur = " iv-msg--current" if current else ""
    return (
        f'<div class="iv-msg iv-msg--agent{cur}"><div class="iv-msg__av">{AGENT_AVATAR}</div>'
        f'<div class="iv-msg__bubble">{safe}</div></div>'
    )


def render_chat(messages: list[dict], streaming_text: str | None = None, thinking: bool = False) -> str:
    """Render the visible conversation. Agent directives are stripped."""
    rows: list[str] = []
    visible_msgs = [m for m in messages if m.get("role") in ("user", "assistant")]
    last_idx = len(visible_msgs) - 1
    for i, m in enumerate(visible_msgs):
        role = m["role"]
        content = m.get("content", "")
        if role == "assistant":
            content = strip_directive(content)
            if not content.strip():
                continue
            rows.append(_bubble("agent", content, current=(streaming_text is None and i == last_idx)))
        else:
            rows.append(_bubble("user", content))
    if streaming_text is not None:
        rows.append(_bubble("agent", strip_directive(streaming_text) or "…", current=True))
    if thinking:
        rows.append(
            '<div class="iv-thinking" aria-live="polite"><span class="dots">'
            "<i></i><i></i><i></i></span> Refuge is listening</div>"
        )
    return f'<div class="iv-chat">{"".join(rows)}</div>'


# --------------------------------------------------------------------------
# State helpers
# --------------------------------------------------------------------------

def advance_to(session: SessionState, target: "State | str | None") -> None:
    """Step the state machine forward to ``target`` (never backward).

    ``target`` may be a State or a phase name string (e.g. "SITUATION") as
    produced by the responder directive.
    """
    if target is None:
        return
    if isinstance(target, str):
        try:
            target = State[target]
        except KeyError:
            return
    while session.state < target:
        session.advance()


def derive_answer(spec: ResponderSpec, radio_v, multi_v, country_v, text_v) -> str:
    if spec.mode == "choice" and spec.multi:
        return ", ".join(multi_v) if multi_v else ""
    if spec.mode == "choice":
        return radio_v or ""
    if spec.mode == "country":
        return country_name(country_v) if country_v else ""
    return (text_v or "").strip()


def responder_updates(spec: ResponderSpec):
    """gr.update() tuple for (radio, multi, country, text) given the spec."""
    is_choice_single = spec.mode == "choice" and not spec.multi
    is_choice_multi = spec.mode == "choice" and spec.multi
    is_country = spec.mode == "country"
    is_text = spec.mode == "text"
    return (
        gr.update(visible=is_choice_single, choices=spec.options if is_choice_single else [], value=None),
        gr.update(visible=is_choice_multi, choices=spec.options if is_choice_multi else [], value=[]),
        gr.update(visible=is_country, value=None),
        gr.update(
            visible=is_text,
            value="",
            placeholder=spec.placeholder or "Take your time. You can write in any language.",
        ),
    )


# --------------------------------------------------------------------------
# UI assembly
# --------------------------------------------------------------------------

@dataclass
class InterviewUI:
    column: gr.Column
    session: gr.State
    loop: gr.State
    spec: gr.State
    start_fn: callable
    start_inputs: list
    stream_outputs: list
    continue_btn: gr.Button
    continue_event: object  # the cont.click dependency, for .then() chaining


def build(
    visible: bool = True,
    session_st: gr.State | None = None,
    loop_st: gr.State | None = None,
    spec_st: gr.State | None = None,
) -> InterviewUI:
    """Build the interview screen inside the current gr.Blocks context.

    ``visible`` starts the screen hidden when the intake screen precedes it
    (Phase 2 navigation). The session/loop states may be shared across phases
    so the assessment screen sees the same session.
    """
    session_st = session_st or gr.State(None)
    loop_st = loop_st or gr.State(None)
    spec_st = spec_st or gr.State(ResponderSpec())

    with gr.Column(elem_id="iv-screen", visible=visible) as column:
        rail = gr.HTML(render_rail(State.SITUATION))
        chat = gr.HTML(render_chat([], thinking=True))

        with gr.Column(elem_id="iv-responder"):
            gr.HTML('<div class="label-row">Your answer</div>')
            radio = gr.Radio(choices=[], label="", visible=False, elem_id="iv-choice")
            multi = gr.CheckboxGroup(choices=[], label="", visible=False, elem_id="iv-multi")
            country = gr.Dropdown(
                choices=country_choices(), label="", visible=False,
                allow_custom_value=True, filterable=True, elem_id="iv-country",
            )
            text = gr.Textbox(
                label="", lines=3, visible=False, elem_id="iv-text",
                placeholder="Take your time. You can write in any language.",
            )
            with gr.Row():
                save = gr.Button("⤓ Save and continue later", elem_id="iv-save", scale=1)
                cont = gr.Button("Continue →", elem_id="iv-continue", scale=1)

    stream_outputs = [chat, rail, radio, multi, country, text, session_st, loop_st, spec_st]

    # -- handlers -------------------------------------------------------

    async def _run_turn(prompt, session, loop):
        """Shared streaming routine. ``prompt`` is the new user turn, or ""
        when the user message is already appended to ``session.messages``."""
        system_prompt = interview_system_prompt()
        acc = ""
        final_messages = list(session.messages)
        async for ev in loop.run(prompt, session, system_prompt=system_prompt):
            if isinstance(ev, TextDeltaEvent):
                acc += ev.delta
                yield render_chat(session.messages, streaming_text=acc), None
            elif isinstance(ev, AgentEndEvent):
                final_messages = ev.messages
            elif isinstance(ev, ErrorEvent):
                acc += f"\n\n_(Something went wrong: {ev.message})_"
                yield render_chat(session.messages, streaming_text=acc), None

        session.messages = final_messages
        _, spec = parse(acc)
        advance_to(session, spec.phase)
        yield render_chat(session.messages), spec

    async def start(session, loop):
        if session is None:
            session = SessionState()
            session.transition_to(State.INTAKE)
            loop = create_loop()
        # entering the interview shows the thinking indicator immediately
        yield (
            render_chat(session.messages, thinking=True), render_rail(session.state),
            gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), session, loop, ResponderSpec(),
        )
        spec = ResponderSpec()
        boot = _bootstrap_for(session)
        async for chat_html, maybe_spec in _run_turn(boot, session, loop):
            if maybe_spec is None:
                yield (chat_html, render_rail(session.state), *(_NO_CHANGE * 4),
                       session, loop, gr.update())
            else:
                spec = maybe_spec
        # The bootstrap instruction is internal — never show or resend it.
        session.messages = [
            m for m in session.messages
            if not (m.get("role") == "user" and m.get("content") == boot)
        ]
        r_up = responder_updates(spec)
        yield (render_chat(session.messages), render_rail(session.state), *r_up,
               session, loop, spec)

    async def on_continue(radio_v, multi_v, country_v, text_v, session, loop, spec):
        if session is None:
            session = SessionState(); session.transition_to(State.INTAKE)
            loop = create_loop()
        answer = derive_answer(spec, radio_v, multi_v, country_v, text_v)
        if not answer:
            # nothing chosen — leave everything as-is
            yield (gr.update(), gr.update(), *(_NO_CHANGE * 4), session, loop, spec)
            return
        # Append the answer now so it shows during streaming; pass "" to the
        # loop so it isn't added a second time.
        session.messages = list(session.messages) + [{"role": "user", "content": answer}]
        yield (
            render_chat(session.messages, thinking=True), render_rail(session.state),
            gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=False), session, loop, spec,
        )
        new_spec = spec
        async for chat_html, maybe_spec in _run_turn("", session, loop):
            if maybe_spec is None:
                yield (chat_html, render_rail(session.state), *(_NO_CHANGE * 4),
                       session, loop, gr.update())
            else:
                new_spec = maybe_spec
        r_up = responder_updates(new_spec)
        yield (render_chat(session.messages), render_rail(session.state), *r_up,
               session, loop, new_spec)

    continue_event = cont.click(
        on_continue,
        inputs=[radio, multi, country, text, session_st, loop_st, spec_st],
        outputs=stream_outputs,
    )

    return InterviewUI(
        column=column,
        session=session_st,
        loop=loop_st,
        spec=spec_st,
        start_fn=start,
        start_inputs=[session_st, loop_st],
        stream_outputs=stream_outputs,
        continue_btn=cont,
        continue_event=continue_event,
    )


# A no-op gr.update placeholder used when a yield doesn't touch a control.
_NO_CHANGE = (gr.update(),)


__all__ = [
    "build",
    "InterviewUI",
    "INTERVIEW_CSS",
    "render_chat",
    "render_rail",
    "advance_to",
    "derive_answer",
]
