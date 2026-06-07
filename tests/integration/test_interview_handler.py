"""tests/integration/test_interview_handler.py — the real Gradio handler streams.

Exercises the exact ``start_fn`` closure the app wires to ``demo.load`` (built
inside a gr.Blocks context) against the real model. Proves the UI handler emits
progressive chat updates (SC-009/SC-010: not buffered) and ends by switching the
structured responder to a concrete mode (SC-011) while advancing state (SC-014).
"""

from __future__ import annotations

import os
import urllib.request

import gradio as gr
import pytest

from app.phases.interview import build
from app.responder import ResponderSpec
from app.state.session import State


def _host_reachable() -> bool:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    try:
        urllib.request.urlopen(host + "/api/tags", timeout=3)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _host_reachable(), reason="Ollama host not reachable; needs a real model"
)


@pytest.mark.asyncio
async def test_start_handler_streams_progressively():
    with gr.Blocks():
        iv = build()

    chat_lengths: list[int] = []
    last_tuple = None
    session = None
    async for out in iv.start_fn(None, None):
        last_tuple = out
        chat_html = out[0]
        # The chat HTML is the first output; track its visible size growth.
        if isinstance(chat_html, str):
            chat_lengths.append(len(chat_html))
        # session is the 7th output (index 6)
        session = out[6]

    # Progressive streaming: the chat HTML grew across multiple yields rather
    # than appearing in a single buffered update.
    growth_steps = sum(1 for a, b in zip(chat_lengths, chat_lengths[1:]) if b > a)
    assert len(chat_lengths) >= 3, f"expected multiple streamed updates, got {len(chat_lengths)}"
    assert growth_steps >= 2, "chat did not grow progressively (looks buffered)"

    # State advanced into the interview proper.
    assert session is not None
    assert State.SITUATION <= session.state <= State.REVIEW

    # Final responder spec is a concrete, valid mode (mode switching works).
    spec = last_tuple[8]
    assert isinstance(spec, ResponderSpec)
    assert spec.mode in {"choice", "country", "text"}
