"""app/phases/interview.py — Phase 2 fully-scripted, multilingual interview.

The interview is 100% deterministic: a fixed set of questions
(app/interview_script.py), each with a fixed control, pre-translated into every
language, templated with already-collected values. The LLM is NOT used here at
all — that removes every source of inconsistency (wrong/repeated questions,
mismatched controls, drift). Answers are captured straight into
``session.interview``.
"""

from __future__ import annotations

import html

import gradio as gr

from agent.events import TextDeltaEvent
from agent.loop import create_loop
from app.countries import country_choices, country_name
from app.prompt_loader import load_prompt
from app.interview_script import (
    QUESTIONS,
    REVIEW_INDEX,
    Question,
    option_labels,
    question_text,
    t,
)
from app.state.session import SessionState, State

RAIL = [
    ("Intake", State.INTAKE), ("Situation", State.SITUATION), ("History", State.HISTORY),
    ("Goals", State.GOALS), ("Review", State.REVIEW),
]

AGENT_AVATAR = (
    '<svg width="18" height="18" viewBox="0 0 32 32" aria-hidden="true">'
    '<path d="M16 7l7 6.5V25h-4.6v-6.2h-4.8V25H9V13.5L16 7z" fill="#fff"/></svg>'
)

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

.iv-chat { padding:clamp(18px,4vw,30px); display:flex; flex-direction:column; gap:18px; background:var(--surface); min-height:140px; }
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

#iv-responder { border-top:1px solid var(--line); background:var(--surface-2); padding:clamp(16px,4vw,24px); }
#iv-responder .label-row { font-size:12px; letter-spacing:.04em; text-transform:uppercase;
  color:var(--text-muted); font-weight:600; margin-bottom:6px; }
#iv-choice .wrap label, #iv-multi .wrap label { border-radius:var(--r-full) !important; }
#iv-continue, #iv-continue button { background:var(--primary) !important; color:var(--on-primary) !important;
  box-shadow:0 2px 0 var(--primary-deep) !important; border:0 !important; font-weight:600 !important; }
#iv-continue:hover, #iv-continue button:hover { background:var(--primary-deep) !important; }
"""


# --------------------------------------------------------------------------
# Rendering
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
        pills.append(f'<div class="{cls}"><span class="dot">{dot}</span>'
                     f'<span class="t">{html.escape(label)}</span></div>')
    return f'<div class="iv-rail" aria-label="Interview progress">{"".join(pills)}</div>'


def _bubble(role: str, text: str, current: bool = False) -> str:
    safe = html.escape(text).replace("\n", "<br>")
    if role == "user":
        return ('<div class="iv-msg iv-msg--user"><div class="iv-msg__av"><span>You</span></div>'
                f'<div class="iv-msg__bubble">{safe}</div></div>')
    cur = " iv-msg--current" if current else ""
    return (f'<div class="iv-msg iv-msg--agent{cur}"><div class="iv-msg__av">{AGENT_AVATAR}</div>'
            f'<div class="iv-msg__bubble">{safe}</div></div>')


def render_chat(messages: list[dict]) -> str:
    rows = []
    visible = [m for m in messages if m.get("role") in ("user", "assistant")]
    last = len(visible) - 1
    for i, m in enumerate(visible):
        if not m.get("content", "").strip():
            continue
        role = "agent" if m["role"] == "assistant" else "user"
        rows.append(_bubble(role, m["content"], current=(role == "agent" and i == last)))
    return f'<div class="iv-chat">{"".join(rows)}</div>'


def advance_to(session: SessionState, target) -> None:
    if target is None:
        return
    if isinstance(target, str):
        try:
            target = State[target]
        except KeyError:
            return
    while session.state < target:
        session.advance()


# --------------------------------------------------------------------------
# Controls (deterministic per question)
# --------------------------------------------------------------------------

def control_updates(session: SessionState, idx: int):
    """(radio, multi, country, text) updates for the question at ``idx``."""
    lang = session.language
    if idx >= REVIEW_INDEX:
        choices = [t(lang, "review_yes"), t(lang, "review_no")]
        return (gr.update(visible=True, choices=choices, value=None),
                gr.update(visible=False), gr.update(visible=False), gr.update(visible=False))
    q = QUESTIONS[idx]
    if q.control == "yesno":
        return (gr.update(visible=True, choices=option_labels(lang, q), value=None),
                gr.update(visible=False), gr.update(visible=False), gr.update(visible=False))
    if q.control == "choice":
        return (gr.update(visible=False),
                gr.update(visible=True, choices=option_labels(lang, q), value=[]),
                gr.update(visible=False), gr.update(visible=False))
    if q.control == "country":
        return (gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=True, value=None), gr.update(visible=False))
    return (gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
            gr.update(visible=True, value=""))


def _store(session: SessionState, q: Question, radio_v, multi_v, country_v, text_v):
    lang = session.language
    if q.control == "country":
        raw = country_name(country_v) if country_v else (text_v or "").strip()
        if not raw:
            return None
        setattr(session.interview, q.field, raw)
        return raw
    if q.control == "yesno":
        if not radio_v:
            return None
        is_yes = radio_v == t(lang, "opt_yes")
        setattr(session.interview, q.field, is_yes)
        return radio_v
    if q.control == "choice":
        if not multi_v:
            return None
        # map translated labels back to canonical English labels
        rev = {t(lang, oid): t("English", oid) for oid in q.options}
        canon = [rev.get(v, v) for v in multi_v]
        setattr(session.interview, q.field, canon)
        return ", ".join(multi_v)
    # text
    raw = (text_v or "").strip()
    if not raw:
        return None
    if q.kind == "list_text":
        setattr(session.interview, q.field, [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()])
    else:
        setattr(session.interview, q.field, raw)
    return raw


def _facts_recap(session: SessionState) -> str:
    iv = session.interview
    bits = []
    for label, val in [
        ("•", iv.current_country), ("•", iv.origin_country),
        ("•", ", ".join(iv.persecution_types) if iv.persecution_types else None),
        ("•", iv.displacement_duration),
        ("•", ", ".join(iv.documents_available) if iv.documents_available else None),
        ("•", ", ".join(iv.languages_spoken) if iv.languages_spoken else None),
        ("•", ", ".join(iv.destination_preferences) if iv.destination_preferences else None),
    ]:
        if val:
            bits.append(f"{label} {val}")
    return "\n".join(bits)


def _agent_message_for(session: SessionState, idx: int, *, welcome: bool = False) -> str:
    text = question_text(session.language, QUESTIONS[idx], session)
    if welcome:
        return f"{t(session.language, 'welcome')}\n{text}"
    return text


def _labeled_facts(session: SessionState) -> str:
    iv = session.interview
    fields = [
        ("Country of origin", iv.origin_country),
        ("Current country", iv.current_country),
        ("What happened", iv.free_text_history),
        ("Immediate danger", None if iv.immediate_danger is None else ("yes" if iv.immediate_danger else "no")),
        ("Time since leaving", iv.displacement_duration),
        ("Documents", ", ".join(iv.documents_available) if iv.documents_available else None),
        ("Languages", ", ".join(iv.languages_spoken) if iv.languages_spoken else None),
        ("Preferred destination", ", ".join(iv.destination_preferences) if iv.destination_preferences else None),
    ]
    return "\n".join(f"{k}: {v}" for k, v in fields if v)


def _labeled_fallback(session: SessionState) -> str:
    lang = session.language
    return f"{t(lang, 'review_intro')}\n{_labeled_facts(session)}\n\n{t(lang, 'review_confirm')}"


async def _draft_review(session: SessionState, loop) -> str:
    """LLM-written labeled review summary in the person's language."""
    lang = session.language or "English"
    system_prompt = (
        load_prompt("system")
        + f"\n\n# Right now\nIn {lang}, briefly summarise back what the person told you so they "
        "can confirm. State each item on its own line, clearly labelled (country of origin, "
        "current country, what happened, immediate danger, time since leaving, documents, "
        "languages, preferred destination). Use ONLY the facts given — do not invent or omit. "
        "End by asking, in one short sentence, whether it is correct."
    )
    acc = ""
    try:
        async for ev in loop.run("Facts:\n" + _labeled_facts(session), session=None,
                                 system_prompt=system_prompt, thinking_level="off"):
            if isinstance(ev, TextDeltaEvent):
                acc += ev.delta
    except Exception:
        acc = ""
    return acc.strip() or _labeled_fallback(session)


# --------------------------------------------------------------------------
# UI assembly
# --------------------------------------------------------------------------

class InterviewUI:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def build(visible: bool = True, session_st=None, loop_st=None, slot_idx_st=None) -> InterviewUI:
    session_st = session_st or gr.State(None)
    loop_st = loop_st or gr.State(None)
    slot_idx_st = slot_idx_st or gr.State(0)

    with gr.Column(visible=visible) as column:
        with gr.Column(elem_id="iv-screen"):
            rail = gr.HTML(render_rail(State.SITUATION))
            chat = gr.HTML(render_chat([]))
            with gr.Column(elem_id="iv-responder"):
                lbl = gr.HTML('<div class="label-row">Your answer</div>')
                # Pre-mount with choices so they render immediately when shown
                # (Gradio is laggy updating choices on a freshly-revealed control).
                radio = gr.Radio(choices=["Yes", "No"], label="", show_label=False, visible=False, elem_id="iv-choice")
                multi = gr.CheckboxGroup(
                    choices=[t("English", oid) for q in QUESTIONS if q.control == "choice" for oid in q.options],
                    label="", show_label=False, visible=False, elem_id="iv-multi",
                )
                country = gr.Dropdown(choices=country_choices(), label="", show_label=False, visible=False,
                                      allow_custom_value=True, filterable=True, elem_id="iv-country")
                text = gr.Textbox(label="", show_label=False, lines=3, visible=False,
                                  placeholder="…", elem_id="iv-text")
                cont = gr.Button("Continue →", elem_id="iv-continue")

    stream_outputs = [chat, rail, radio, multi, country, text, session_st, loop_st, slot_idx_st]

    async def _present(session, loop, idx):
        """Append the agent's message (scripted question, or LLM review summary)
        and show the right control for the step."""
        target = State.REVIEW if idx >= REVIEW_INDEX else QUESTIONS[idx].phase
        advance_to(session, target)
        if idx >= REVIEW_INDEX:
            msg = await _draft_review(session, loop)
        else:
            msg = _agent_message_for(session, idx, welcome=(idx == 0))
        session.messages = list(session.messages) + [{"role": "assistant", "content": msg}]
        return (render_chat(session.messages), render_rail(session.state),
                *control_updates(session, idx), session, idx)

    async def start(session, loop, slot_idx=0):
        if session is None:
            session = SessionState(); session.transition_to(State.INTAKE)
        loop = loop or create_loop()
        out = await _present(session, loop, 0)
        yield (out[0], out[1], out[2], out[3], out[4], out[5], out[6], loop, out[7])

    async def on_continue(radio_v, multi_v, country_v, text_v, session, loop, idx):
        if session is None:
            session = SessionState(); session.transition_to(State.INTAKE)
            loop = loop or create_loop()
            o = await _present(session, loop, 0)
            return (o[0], o[1], o[2], o[3], o[4], o[5], o[6], loop, o[7])
        loop = loop or create_loop()
        lang = session.language

        if idx >= REVIEW_INDEX:
            if not radio_v:
                return (gr.update(), gr.update(), *control_updates(session, idx), session, loop, idx)
            session.messages = list(session.messages) + [{"role": "user", "content": radio_v}]
            if radio_v == t(lang, "review_yes"):
                advance_to(session, State.ASSESSMENT)  # triggers assessment via .then()
                return (render_chat(session.messages), render_rail(session.state),
                        gr.update(visible=False), gr.update(visible=False),
                        gr.update(visible=False), gr.update(visible=False), session, loop, idx)
            o = await _present(session, loop, 0)  # "something needs changing" → restart
            return (o[0], o[1], o[2], o[3], o[4], o[5], o[6], loop, o[7])

        q = QUESTIONS[idx]
        display = _store(session, q, radio_v, multi_v, country_v, text_v)
        if display is None:
            return (gr.update(), gr.update(), *control_updates(session, idx), session, loop, idx)
        session.messages = list(session.messages) + [{"role": "user", "content": display}]
        o = await _present(session, loop, idx + 1)
        return (o[0], o[1], o[2], o[3], o[4], o[5], o[6], loop, o[7])

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


__all__ = ["build", "InterviewUI", "INTERVIEW_CSS", "render_chat", "render_rail",
           "advance_to", "control_updates"]
