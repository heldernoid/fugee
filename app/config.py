"""app/config.py — minimal, dependency-free environment loading.

Reads a ``.env`` file at the repo root into ``os.environ`` (without overriding
values already set in the real environment). Avoids adding python-dotenv just to
read a handful of keys.

Recognised keys (see ``.env.example``):
  * ``OLLAMA_HOST``    — base URL of the Ollama server (e.g. http://host:11434)
  * ``MODEL_ID``       — model name to use (default ``qwen2.5:7b``)
  * ``MODEL_PROVIDER`` — ``ollama`` (default) or a litellm provider
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"


def load_env(env_file: Path | None = None) -> None:
    """Load KEY=VALUE lines from ``.env`` into os.environ (non-overriding)."""
    path = env_file or ENV_FILE
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


__all__ = ["load_env", "ENV_FILE", "REPO_ROOT"]
