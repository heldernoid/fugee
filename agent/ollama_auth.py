"""agent/ollama_auth.py — auth headers for a remote (e.g. Modal-hosted) Ollama.

Locally, Ollama needs no auth and these return ``{}`` — nothing changes. When the
LLM + embeddings run on a protected remote endpoint (the demo deploys Ollama on a
Modal GPU and the Hugging Face Space calls it), set the matching env vars so every
Ollama request carries the right header:

  * Modal proxy auth:   MODAL_KEY + MODAL_SECRET   -> ``Modal-Key`` / ``Modal-Secret``
  * Generic bearer:     OLLAMA_AUTH_TOKEN          -> ``Authorization: Bearer …``

The endpoint URL itself comes from ``OLLAMA_HOST`` (already used everywhere).
"""

from __future__ import annotations

import os


def ollama_headers() -> dict[str, str]:
    """Auth headers for the configured Ollama endpoint (empty for local use)."""
    headers: dict[str, str] = {}
    key, secret = os.getenv("MODAL_KEY"), os.getenv("MODAL_SECRET")
    if key and secret:
        headers["Modal-Key"] = key
        headers["Modal-Secret"] = secret
    token = os.getenv("OLLAMA_AUTH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


__all__ = ["ollama_headers"]
