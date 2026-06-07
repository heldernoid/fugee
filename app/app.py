"""app/app.py — Refuge Gradio entrypoint.

Run locally with::

    python app/app.py

Phase 0 renders the bare skeleton: the Refuge wordmark and tagline on the warm
off-white canvas (DESIGN.md colors.background = #F7F5F0), with the full DESIGN.md
token set injected as a ``:root`` CSS block. Later phases mount onto this shell.

All colours, fonts, radii, and spacing come from DESIGN.md via
``app.design_tokens`` — never hardcoded here (CLAUDE.md Design Rule 7).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow ``python app/app.py`` (script run) as well as ``python -m app.app``.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gradio as gr  # noqa: E402

from app.config import load_env  # noqa: E402
from app.design_tokens import root_css  # noqa: E402
from app.phases import interview as interview_phase  # noqa: E402

# Load .env (OLLAMA_HOST, MODEL_ID, …) before anything reads the environment.
load_env()

# Web fonts: Fraunces (display serif) + Inter (UI sans) per DESIGN.md §3.
FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Fraunces:opsz,wght@9..144,500;9..144,600&"
    "family=Inter:wght@400;450;600;700&display=swap');"
)

# Component CSS — every value references a DESIGN.md token via var(--…); no
# literal hex/px design values live here.
COMPONENT_CSS = """
body, .gradio-container {
  background: var(--bg) !important;
  color: var(--text);
  font-family: var(--font-ui);
}
.gradio-container { max-width: var(--maxw) !important; margin: 0 auto !important; }

#refuge-hero {
  text-align: center;
  padding: var(--s-xxl) var(--s-lg);
}
#refuge-wordmark {
  font-family: var(--font-display);
  font-weight: 600;
  font-size: clamp(38px, 6vw, 58px);
  line-height: 1.15;
  letter-spacing: -0.02em;
  color: var(--primary);
  margin: 0 0 var(--s-md) 0;
  text-wrap: balance;
}
#refuge-tagline {
  font-family: var(--font-ui);
  font-size: 18px;
  line-height: 1.6;
  color: var(--text-secondary);
  margin: 0 0 var(--s-xl) 0;
}
#refuge-trust {
  display: inline-flex;
  align-items: center;
  gap: var(--s-sm);
  padding: var(--s-sm) var(--s-md);
  border-radius: var(--r-full);
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--text-muted);
  font-size: 13.5px;
  box-shadow: var(--shadow-sm);
}
#refuge-trust .lock { color: var(--primary); }
#refuge-footer {
  margin-top: var(--s-xxl);
  padding-top: var(--s-lg);
  border-top: 1px solid var(--line);
  color: var(--text-muted);
  font-size: 12px;
  text-align: center;
}
"""

APP_CSS = (
    FONT_IMPORT + "\n" + root_css() + "\n" + COMPONENT_CSS
    + "\n" + interview_phase.INTERVIEW_CSS
)

HERO_HTML = """
<main id="refuge-hero">
  <h1 id="refuge-wordmark">Refuge</h1>
  <p id="refuge-tagline">Safe guidance for people on the move</p>
  <span id="refuge-trust"><span class="lock">&#128274;</span>
    This conversation is private. Nothing is stored without your consent.</span>
</main>
"""


def build_app() -> gr.Blocks:
    # Gradio 6: `css` is passed to launch(), not the Blocks constructor.
    with gr.Blocks(title="Refuge", analytics_enabled=False) as demo:
        gr.HTML(HERO_HTML)
        iv = interview_phase.build()
        # Auto-start the interview: stream the agent's first question on load.
        demo.load(iv.start_fn, inputs=iv.start_inputs, outputs=iv.stream_outputs)
    return demo


def main() -> None:
    demo = build_app()
    demo.launch(server_name="0.0.0.0", css=APP_CSS)


if __name__ == "__main__":
    main()
