"""app/app.py — Fugee Gradio entrypoint.

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

import os
import sys
from pathlib import Path

# Allow ``python app/app.py`` (script run) as well as ``python -m app.app``.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gradio as gr  # noqa: E402

from agent.loop import create_loop  # noqa: E402
from app.config import load_env  # noqa: E402
from app.design_tokens import root_css  # noqa: E402
from app.phases import assessment as assessment_phase  # noqa: E402
from app.phases import documents as documents_phase  # noqa: E402
from app.phases import intake as intake_phase  # noqa: E402
from app.phases import interview as interview_phase  # noqa: E402
from app.phases import recommendations as reco_phase  # noqa: E402
from app.state.session import SessionState, State  # noqa: E402

# Load .env (OLLAMA_HOST, MODEL_ID, …) before anything reads the environment.
load_env()

# One model for the whole flow (hackathon: single LLM, no fallback). Read from
# MODEL_ID via the loop factory.

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
/* Always reserve the scrollbar gutter so a tall screen (with a scrollbar) and a
   short one (without) keep the SAME viewport width — otherwise the centered
   container, and the nav inside it, jump sideways on every screen transition. */
html { scrollbar-gutter: stable; overflow-y: scroll; }
body, .gradio-container { background: var(--bg) !important; color: var(--text);
  font-family: var(--font-ui); }
/* Wide shell like the mockup (main = 1180px); narrow screens cap themselves.
   width:100% pins the shell to the full available width so it never shrink-wraps
   to the current phase's content — that shrink-wrap is what made the nav (which
   spans this container) change size and re-center between screens. */
.gradio-container { width: 100% !important; max-width: 1180px !important; margin: 0 auto !important;
  padding: 0 clamp(16px,4vw,32px) var(--s-xxl) !important; }
.gradio-container button, .gradio-container input,
.gradio-container textarea, .gradio-container select { font-family: var(--font-ui); }

/* neutralise Gradio's default boxes so our custom screens read cleanly */
.gradio-container .block { background: transparent !important; border: none !important;
  box-shadow: none !important; }
.gradio-container .form { background: transparent !important; border: none !important;
  box-shadow: none !important; }
.gradio-container .gap { gap: var(--s-sm); }

/* Every phase wrapper fills the shell so all five screens render at the SAME
   width. Without this, the Gradio column shrink-wraps to its content and each
   card collapses to a different width (intake ~680, interview ~560, etc.). */
.screen-wrap { width: 100% !important; align-self: stretch !important; }
.screen-wrap > .block, .screen-wrap > div { width: 100% !important; }
.gradio-container :focus-visible { outline: 3px solid var(--accent) !important;
  outline-offset: 2px; border-radius: var(--r-sm); }

/* Site bar (mockup chrome) */
#site-bar { position:sticky; top:0; z-index:50; background:rgba(247,245,240,.86);
  backdrop-filter:saturate(140%) blur(10px); border-bottom:1px solid var(--line);
  margin:0 calc(-1 * clamp(16px,4vw,32px)) var(--s-xl); padding:14px clamp(16px,4vw,32px); }
#site-bar .inner { display:flex; align-items:center; gap:12px; max-width:1180px; margin:0 auto; }
#site-bar .name { font-family:var(--font-display); font-weight:600; font-size:21px;
  letter-spacing:-.01em; color:var(--primary-deep); }
#site-bar .tag { font-size:12px; color:var(--text-muted); letter-spacing:.04em;
  text-transform:uppercase; padding-left:10px; margin-left:2px; border-left:1px solid var(--line-strong); }
#site-bar .nav { margin-left:auto; display:flex; gap:2px; }
#site-bar .nav span { font-size:13px; font-weight:500; color:var(--text-secondary);
  padding:7px 12px; border-radius:var(--r-full); white-space:nowrap; }
@media(max-width:860px){ #site-bar .nav, #site-bar .tag { display:none; } }

/* Per-phase header (tag + description), like the mockup */
.phase-head { display:flex; align-items:baseline; gap:14px; flex-wrap:wrap; margin-bottom:var(--s-lg); }
.phase-head .ptag { font-size:11.5px; font-weight:600; letter-spacing:.13em; text-transform:uppercase;
  color:var(--primary); background:var(--primary-tint); padding:5px 11px; border-radius:var(--r-full); white-space:nowrap; }
.phase-head .pdesc { font-size:14px; color:var(--text-muted); max-width:52ch; }
"""

APP_CSS = (
    FONT_IMPORT + "\n"
    + root_css() + "\n"
    + GLOBAL_CSS + "\n"
    + intake_phase.INTAKE_CSS + "\n"
    + interview_phase.INTERVIEW_CSS + "\n"
    + assessment_phase.ASSESSMENT_CSS + "\n"
    + reco_phase.RECO_CSS + "\n"
    + documents_phase.DOCUMENTS_CSS
)


_LOGO_SVG = (
    '<svg width="28" height="28" viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="15" fill="#0E6A58"/>'
    '<path d="M16 7l7 6.5V25h-4.6v-6.2h-4.8V25H9V13.5L16 7z" fill="#fff"/>'
    '<circle cx="16" cy="13.6" r="1.7" fill="#E07B39"/></svg>'
)
SITE_BAR_HTML = f"""
<header id="site-bar"><div class="inner">
  {_LOGO_SVG}
  <span class="name">Fugee</span>
  <span class="tag">Safe guidance for people on the move</span>
</div></header>
"""


def phase_header(tag: str, desc: str) -> str:
    """The 'PHASE N — TITLE' tag + description shown above a phase screen."""
    return f'<div class="phase-head"><span class="ptag">{tag}</span><span class="pdesc">{desc}</span></div>'


def _ready_for_assessment(session) -> bool:
    """The interview advances state to ASSESSMENT once the review is confirmed."""
    return (
        session is not None
        and session.state == State.ASSESSMENT
        and not session.assessment.recommended_countries
    )


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Fugee", analytics_enabled=False) as demo:
        gr.HTML(SITE_BAR_HTML)
        # Session + loop state shared across phases so each screen sees the same
        # session object.
        session_st = gr.State(None)
        loop_st = gr.State(None)

        intake_ui = intake_phase.build(visible=True)
        interview_ui = interview_phase.build(visible=False, session_st=session_st, loop_st=loop_st)
        assess_ui = assessment_phase.build(visible=False, session_st=session_st, loop_st=loop_st)
        reco_ui = reco_phase.build(visible=False, session_st=session_st)
        docs_ui = documents_phase.build(visible=False, session_st=session_st)

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

        # Two round-trips: stream the first question (controls hidden), then
        # reveal its control on its own so the CheckboxGroup isn't fighting the
        # chat re-render for its paint (see interview.py).
        intake_ui.begin.click(
            begin,
            inputs=[intake_ui.selected_lang, interview_ui.session, interview_ui.loop],
            outputs=[intake_ui.column, interview_ui.column, *interview_ui.stream_outputs],
            show_progress="hidden",
        ).then(
            interview_ui.reveal_fn,
            inputs=interview_ui.reveal_inputs,
            outputs=interview_ui.reveal_outputs,
            show_progress="hidden",
        )

        async def maybe_assess(session, loop):
            # Triggered after each interview turn; runs only once the review is
            # confirmed (interview set state -> ASSESSMENT), then streams the assessment.
            if not _ready_for_assessment(session):
                return
            # Fresh loop for the assessment turn (same model, its own steering/abort).
            assess_loop = create_loop()
            async for facts_html, reason_html, progress_html, proceed_u, sess in assess_ui.start_fn(session, assess_loop):
                yield (gr.update(visible=False), gr.update(visible=True),
                       facts_html, reason_html, progress_html, proceed_u, sess)

        # After each interview turn completes, check whether the review was
        # confirmed and, if so, hand off to the assessment screen.
        interview_ui.continue_event.then(
            maybe_assess,
            inputs=[session_st, loop_st],
            outputs=[interview_ui.column, assess_ui.column, *assess_ui.outputs],
        )

        reco_outputs = [assess_ui.column, reco_ui.column, *reco_ui.render_outputs, session_st]

        def show_recommendations(session):
            # Reveal the recommendations only when the person clicks "See your
            # recommendations" — so they can read the assessment first.
            ready = (
                session is not None
                and session.state >= State.RECOMMENDATIONS
                and session.assessment.recommended_countries
            )
            if not ready:
                return [gr.update()] * len(reco_outputs)
            updates = reco_ui.populate(session)
            return [gr.update(visible=False), gr.update(visible=True), *updates, session]

        # The person reads the assessment, then clicks to see recommendations.
        assess_ui.proceed.click(show_recommendations, inputs=[session_st], outputs=reco_outputs)

        # Recommendations -> Documents: generate the package for the chosen country.
        docs_outputs = [reco_ui.column, docs_ui.column, *docs_ui.render_outputs]

        _docs_loading = (
            '<article class="doc" style="text-align:center;padding:44px 20px;">'
            '<div style="font-size:15px;font-weight:700;color:var(--primary-deep)">'
            'Preparing your document package…</div>'
            '<p style="margin-top:8px;color:var(--text-secondary)">Fugee is drafting your '
            'personal statement and building your Word&nbsp;+&nbsp;PDF files. This takes a few moments.</p>'
            '</article>'
        )

        async def show_documents(session):
            # Generator: reveal the documents screen with a status message FIRST,
            # then run the LLM draft + file generation, so the click never looks
            # like nothing is happening.
            if session is None or not session.selected_country:
                yield [gr.update()] * len(docs_outputs)
                return
            if session.state < State.DOCUMENTS:
                from app.phases.interview import advance_to
                advance_to(session, State.DOCUMENTS)
            # 1) switch to the docs screen immediately, showing a "preparing…" note
            yield [gr.update(visible=False), gr.update(visible=True),
                   gr.update(value=_docs_loading), gr.update(), gr.update(), gr.update()]
            # 2) draft (LLM) + generate Word/PDF, then render the finished package
            updates = await docs_ui.populate(session)
            yield [gr.update(visible=False), gr.update(visible=True), *updates]

        reco_ui.proceed.click(show_documents, inputs=[session_st], outputs=docs_outputs,
                              show_progress="hidden")

        # Start over: return to the intake screen for a fresh session.
        def start_over():
            return (
                gr.update(visible=True), gr.update(visible=False),
                gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=False), None, None,
            )

        docs_ui.start_over.click(
            start_over,
            inputs=[],
            outputs=[intake_ui.column, interview_ui.column, assess_ui.column,
                     reco_ui.column, docs_ui.column, session_st, loop_st],
        )

    return demo


def main() -> None:
    import tempfile

    demo = build_app()
    # allowed_paths lets Gradio serve the generated PDFs (written to the system
    # temp dir) for download.
    demo.launch(
        server_name="0.0.0.0", css=APP_CSS, theme=gr.themes.Base(),
        allowed_paths=[tempfile.gettempdir()],
    )


if __name__ == "__main__":
    main()
