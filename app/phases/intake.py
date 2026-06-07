"""app/phases/intake.py — Phase 1 intake + language selection (T030-T032).

Matches mockup.html #phase-1: a calm welcome with the Refuge wordmark, a
topographic backdrop, a grid of language pills each in its own script, an amber
"Begin in <language>" primary action, and a persistent privacy trust note.

Language selection is single-select with click-to-deselect (T031). Beginning the
interview without a language is a logic error (``begin_interview`` raises
ValueError) surfaced before any model call.
"""

from __future__ import annotations

from dataclasses import dataclass

import gradio as gr

from app.state.session import SessionState, State

# (native script label, English gloss). Limited to the languages the single
# model (lfm2.5:8b) handles reliably — verified by a language probe.
LANGUAGES = [
    ("English", "English"),
    ("Français", "French"),
    ("Español", "Spanish"),
    ("Português", "Portuguese"),
    ("العربية", "Arabic"),
    ("हिन्दी", "Hindi"),
    ("中文", "Chinese"),
    ("日本語", "Japanese"),
    ("한국어", "Korean"),
    ("Русский", "Russian"),
]

# Map a chosen pill label (native) to the English name stored on the session.
_NATIVE_TO_ENGLISH = {native: english for native, english in LANGUAGES}

INTAKE_CSS = """
#intake-screen { background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-lg); box-shadow: var(--shadow-md); overflow: hidden;
  max-width: var(--maxw); margin: 0 auto; }
.intake-wrap { position:relative; padding:clamp(40px,7vw,84px) clamp(20px,5vw,72px);
  text-align:center; overflow:hidden;
  background:linear-gradient(180deg,#FCFBF7 0%,#F4F1E9 100%); }
.intake-topo { position:absolute; inset:0; z-index:0; color:var(--primary); opacity:.10; pointer-events:none; }
.intake-inner { position:relative; z-index:1; max-width:560px; margin:0 auto; }
.intake-logo { width:64px; height:64px; margin:0 auto 22px; }
#intake-screen h1.intake-h1 { font-family:var(--font-display); font-size:clamp(38px,6vw,58px);
  font-weight:600; letter-spacing:-.02em; color:var(--primary-deep); margin:0; }
.intake-tagline { margin-top:10px; font-size:clamp(17px,2.4vw,20px); color:var(--text-secondary); font-weight:450; }
.intake-lbl { margin-top:38px; margin-bottom:14px; font-size:12px; letter-spacing:.12em;
  text-transform:uppercase; color:var(--text-muted); font-weight:600; }

/* language pills (native Gradio buttons themed as pills) */
#intake-langs { display:flex; flex-wrap:wrap; gap:10px; justify-content:center; max-width:480px; margin:0 auto; }
#intake-langs .lang button, #intake-langs button.lang {
  border:1px solid var(--line-strong) !important; background:var(--surface) !important;
  border-radius:var(--r-full) !important; padding:9px 16px !important; font-size:14px !important;
  font-weight:500 !important; color:var(--text-secondary) !important; line-height:1.2 !important;
  box-shadow:none !important; min-height:0 !important; width:auto !important; }
#intake-langs .lang button:hover, #intake-langs button.lang:hover {
  border-color:var(--primary) !important; color:var(--primary-deep) !important; background:var(--primary-tint) !important; }
#intake-langs .lang--selected button, #intake-langs button.lang--selected {
  background:var(--primary) !important; border-color:var(--primary) !important;
  color:var(--on-primary) !important; box-shadow:var(--shadow-sm) !important; }

.intake-cta { margin-top:30px; }
#intake-begin, #intake-begin button { background:var(--accent) !important; color:var(--on-accent) !important;
  box-shadow:0 2px 0 var(--accent-deep) !important; border:0 !important; border-radius:var(--r-md) !important;
  font-weight:600 !important; font-size:16px !important; padding:16px 28px !important; }
#intake-begin:hover, #intake-begin button:hover { background:var(--accent-deep) !important; box-shadow:0 2px 0 #a8531f !important; }

.intake-trust { margin-top:24px; display:inline-flex; align-items:center; gap:9px; font-size:13px;
  color:var(--text-muted); background:var(--surface-2); border:1px solid var(--line);
  padding:9px 16px; border-radius:var(--r-full); }
.intake-trust svg { flex:0 0 auto; color:var(--primary); }
"""

_TOPO_SVG = """
<svg class="intake-topo" viewBox="0 0 780 520" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
  <g fill="none" stroke="currentColor" stroke-width="1.4">
    <path d="M-20 120 C 160 70 260 180 420 150 C 560 124 660 60 820 110"/>
    <path d="M-20 180 C 150 130 280 240 430 205 C 580 172 680 120 820 168"/>
    <path d="M-20 250 C 170 196 270 300 440 268 C 600 238 690 188 820 232"/>
    <path d="M-20 330 C 160 270 300 372 450 338 C 610 304 700 250 820 300"/>
    <path d="M-20 414 C 180 350 290 446 450 416 C 610 388 710 330 820 380"/>
  </g>
  <g stroke="#E07B39" stroke-width="2" stroke-dasharray="2 9" stroke-linecap="round" fill="none">
    <path d="M120 470 C 240 360 360 420 470 300 C 560 200 640 220 700 120"/>
  </g>
  <circle cx="120" cy="470" r="5" fill="#E07B39"/>
  <circle cx="700" cy="120" r="6" fill="#0E6A58"/>
</svg>
"""

_HEADER_HTML = f"""
<div class="intake-wrap">
  {_TOPO_SVG}
  <div class="intake-inner">
    <div class="intake-logo" aria-hidden="true">
      <svg width="64" height="64" viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="15.5" fill="#0E6A58"/><circle cx="16" cy="16" r="15.5" stroke="#0A5042"/><path d="M16 7l7 6.5V25h-4.6v-6.2h-4.8V25H9V13.5L16 7z" fill="#fff"/><circle cx="16" cy="13.6" r="1.7" fill="#E07B39"/></svg>
    </div>
    <h1 class="intake-h1">Refuge</h1>
    <p class="intake-tagline">Safe guidance for people on the move</p>
    <p class="intake-lbl">Choose your language</p>
  </div>
</div>
"""

_TRUST_HTML = """
<div style="text-align:center;"><span class="intake-trust">
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>
  This conversation is private. Nothing is stored without your consent.
</span></div>
"""


# --------------------------------------------------------------------------
# Pure logic (unit-tested, no Gradio)
# --------------------------------------------------------------------------

def select_language(session: SessionState, native_label: str | None) -> None:
    """Set (or clear) the session's chosen language from a pill label.

    Single-select: setting a new language replaces the previous one. Passing
    ``None`` clears the selection (click-to-deselect).
    """
    if native_label is None:
        session.language = None
        return
    session.language = _NATIVE_TO_ENGLISH.get(native_label, native_label)


def begin_interview(session: SessionState) -> State:
    """Transition LANGUAGE_SELECT -> INTAKE; require a language first."""
    if not session.language:
        raise ValueError("Select a language before beginning the interview.")
    return session.transition_to(State.INTAKE)


def toggle_selection(native_label: str, current: str | None) -> str | None:
    """Single-select with click-to-deselect: returns the new selection."""
    return None if current == native_label else native_label


def begin_label(selected: str | None) -> tuple[str, bool]:
    """Begin button (label, interactive) for the current selection (SC-019)."""
    if selected:
        return f"Begin in {selected}", True
    return "Begin", False


# --------------------------------------------------------------------------
# UI assembly
# --------------------------------------------------------------------------

@dataclass
class IntakeUI:
    column: gr.Column
    selected_lang: gr.State  # native label of the chosen pill, or None
    begin: gr.Button


def build(visible: bool = True) -> IntakeUI:
    """Build the intake screen inside the current gr.Blocks context."""
    selected_lang = gr.State(None)

    with gr.Column(visible=visible) as column:
        with gr.Column(elem_id="intake-screen"):
            gr.HTML(_HEADER_HTML)
            with gr.Row(elem_id="intake-langs"):
                pills = [
                    gr.Button(native, elem_classes=["lang"], scale=0)
                    for native, _english in LANGUAGES
                ]
            with gr.Row(elem_classes=["intake-cta"]):
                begin = gr.Button("Begin", elem_id="intake-begin", interactive=False)
            gr.HTML(_TRUST_HTML)

    def _on_pill(clicked: str, current: str | None):
        new_selected = toggle_selection(clicked, current)
        pill_updates = [
            gr.update(
                elem_classes=["lang", "lang--selected"] if native == new_selected else ["lang"]
            )
            for native, _ in LANGUAGES
        ]
        label, interactive = begin_label(new_selected)
        return [*pill_updates, gr.update(value=label, interactive=interactive), new_selected]

    pill_outputs = [*pills, begin, selected_lang]
    for native, _english in LANGUAGES:
        pills[LANGUAGES.index((native, _english))].click(
            lambda cur, nat=native: _on_pill(nat, cur),
            inputs=[selected_lang],
            outputs=pill_outputs,
        )

    return IntakeUI(column=column, selected_lang=selected_lang, begin=begin)


__all__ = [
    "build",
    "IntakeUI",
    "INTAKE_CSS",
    "LANGUAGES",
    "select_language",
    "begin_interview",
]
