"""app/app.py — Refuge Gradio entrypoint.

Run locally with::

    python app/app.py

Mounts the phase screens onto a single Gradio shell themed entirely from
DESIGN.md tokens (via ``app.design_tokens``) and mockup.html. The intake screen
(Phase 1) shows first; choosing a language and pressing "Begin" hides it and
streams the interview (Phase 2).

All colours, fonts, radii, and spacing come from DESIGN.md — never hardcoded
here (CLAUDE.md Design Rule 7).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow ``python app/app.py`` (script run) as well as ``python -m app.app``.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gradio as gr  # noqa: E402

from agent.loop import create_loop  # noqa: E402
from app.config import load_env  # noqa: E402
from app.design_tokens import root_css  # noqa: E402
from app.phases import assessment as assessment_phase  # noqa: E402
from app.phases import intake as intake_phase  # noqa: E402
from app.phases import interview as interview_phase  # noqa: E402
from app.state.session import SessionState, State  # noqa: E402

# Load .env (OLLAMA_HOST, MODEL_ID, …) before anything reads the environment.
load_env()

# Web fonts: Fraunces (display serif) + Inter (UI sans) per DESIGN.md §3.
FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Fraunces:opsz,wght@9..144,500;9..144,600&"
    "family=Inter:wght@400;450;600;700&display=swap');"
)

# Global shell + chrome overrides so Gradio's default theme doesn't bleed
# through. Flatten default component chrome; our phase screens (#intake-screen,
# #iv-screen) re-assert their own surface/border with higher specificity.
GLOBAL_CSS = """
footer { display: none !important; }
body, .gradio-container { background: var(--bg) !important; color: var(--text);
  font-family: var(--font-ui); }
.gradio-container { max-width: var(--maxw) !important; margin: 0 auto !important;
  padding-top: var(--s-xl); padding-bottom: var(--s-xl); }
.gradio-container button, .gradio-container input,
.gradio-container textarea, .gradio-container select { font-family: var(--font-ui); }

/* neutralise Gradio's default boxes so our custom screens read cleanly */
.gradio-container .block { background: transparent !important; border: none !important;
  box-shadow: none !important; }
.gradio-container .form { background: transparent !important; border: none !important;
  box-shadow: none !important; }
.gradio-container .gap { gap: var(--s-sm); }

/* visible focus ring on every control (DESIGN.md accessibility) */
.gradio-container :focus-visible { outline: 3px solid var(--accent) !important;
  outline-offset: 2px; border-radius: var(--r-sm); }
"""

APP_CSS = (
    FONT_IMPORT + "\n"
    + root_css() + "\n"
    + GLOBAL_CSS + "\n"
    + intake_phase.INTAKE_CSS + "\n"
    + interview_phase.INTERVIEW_CSS + "\n"
    + assessment_phase.ASSESSMENT_CSS
)


def _confirmed_review(session) -> bool:
    """True when the person has just confirmed the review summary."""
    if session is None or session.state != State.REVIEW:
        return False
    users = [m for m in session.messages if m.get("role") == "user"]
    if not users:
        return False
    return users[-1].get("content", "").strip().lower().startswith("yes")


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Refuge", analytics_enabled=False) as demo:
        # Session + loop state shared across phases so each screen sees the same
        # session object.
        session_st = gr.State(None)
        loop_st = gr.State(None)

        intake_ui = intake_phase.build(visible=True)
        interview_ui = interview_phase.build(visible=False, session_st=session_st, loop_st=loop_st)
        assess_ui = assessment_phase.build(visible=False, session_st=session_st, loop_st=loop_st)

        async def begin(lang, session, loop):
            if not lang:
                return  # Begin is disabled until a language is chosen
            session = SessionState()
            intake_phase.select_language(session, lang)
            intake_phase.begin_interview(session)  # LANGUAGE_SELECT -> INTAKE
            loop = create_loop()
            # Hide intake, reveal + stream the interview's first question.
            async for out in interview_ui.start_fn(session, loop):
                yield (gr.update(visible=False), gr.update(visible=True), *out)

        intake_ui.begin.click(
            begin,
            inputs=[intake_ui.selected_lang, interview_ui.session, interview_ui.loop],
            outputs=[intake_ui.column, interview_ui.column, *interview_ui.stream_outputs],
        )

        async def maybe_assess(session, loop):
            # Triggered after each interview turn; runs only once the review is
            # confirmed, then hands off to the assessment screen.
            if not _confirmed_review(session):
                return
            async for facts_html, reason_html, progress_html, sess in assess_ui.start_fn(session, loop):
                yield (gr.update(visible=False), gr.update(visible=True),
                       facts_html, reason_html, progress_html, sess)

        # After each interview turn completes, check whether the review was
        # confirmed and, if so, hand off to the assessment screen.
        interview_ui.continue_event.then(
            maybe_assess,
            inputs=[session_st, loop_st],
            outputs=[interview_ui.column, assess_ui.column, *assess_ui.outputs],
        )

    return demo


def main() -> None:
    demo = build_app()
    demo.launch(server_name="0.0.0.0", css=APP_CSS, theme=gr.themes.Base())


if __name__ == "__main__":
    main()
