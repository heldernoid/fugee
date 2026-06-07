"""Shared pytest fixtures / setup.

Loads the repo `.env` (OLLAMA_HOST, MODEL_ID, …) so tests that hit the real
model use the same configuration as the running app.
"""

from app.config import load_env

load_env()
