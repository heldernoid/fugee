"""deploy/modal_app.py — serve Ollama (LLM + embeddings) on a Modal GPU.

Runs ``ollama serve`` on a Modal GPU container and exposes its HTTP API as an
HTTPS endpoint protected by Modal **proxy auth**. The Fugee Gradio app (e.g. on a
free Hugging Face Space) points ``OLLAMA_HOST`` at this endpoint and sends the
``Modal-Key`` / ``Modal-Secret`` headers (see agent/ollama_auth.py), so the same
Ollama code path and the same models (lfm2.5:8b + nomic-embed-text) work unchanged
— now on a rented GPU instead of a local box.

Usage
-----
1. Authenticate the CLI once:        modal token set --token-id … --token-secret …
2. Pull the models into the cache:   modal run deploy/modal_app.py::download_models
3. Deploy the endpoint:              modal deploy deploy/modal_app.py
   -> prints a URL like  https://<workspace>--fugee-ollama-serve.modal.run
4. Create a Proxy Auth Token in the Modal dashboard (Tokens -> Proxy Auth Tokens)
   and give its id/secret to the Space as MODAL_KEY / MODAL_SECRET.

Cost: scales to zero when idle (``scaledown_window``). Keep one warm only during a
live demo by redeploying with MODAL_MIN_CONTAINERS=1.
"""

from __future__ import annotations

import os
import subprocess
import time
import urllib.request

import modal

# Models (override via env at deploy time if needed). These must match the app's
# MODEL_ID / EMBED_MODEL.
LLM_MODEL = os.environ.get("MODEL_ID", "lfm2.5:8b")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
MODELS = [LLM_MODEL, EMBED_MODEL]

GPU = os.environ.get("MODAL_GPU", "L4")                 # L4 (cheapest) | A10G | A100
MIN_CONTAINERS = int(os.environ.get("MODAL_MIN_CONTAINERS", "0"))  # 1 = keep warm
# Context window. Ollama's default (~4096) truncates our assessment prompt; load
# the model at this size so it (and the app's per-request num_ctx) match -> no
# reload on the first request. Must match the app's NUM_CTX.
NUM_CTX = os.environ.get("NUM_CTX", "16384")
OLLAMA_DIR = "/root/.ollama"                            # model cache (Volume mount)
PORT = 11434

app = modal.App("fugee-ollama")

# Ollama installed via its official script; models live in a persistent Volume so
# cold starts don't re-download multi-GB weights.
image = (
    modal.Image.debian_slim()
    .apt_install("curl", "zstd")  # ollama's installer needs zstd to extract
    .run_commands("curl -fsSL https://ollama.com/install.sh | sh")
)
models_volume = modal.Volume.from_name("fugee-ollama-models", create_if_missing=True)


def _start_ollama(bind: str = "0.0.0.0", keep_alive: str | None = None) -> None:
    """Start ``ollama serve`` (bound so Modal can reach it) and wait until ready.

    ``keep_alive="-1"`` tells Ollama never to unload the model from GPU while the
    container is warm, so a kept-warm endpoint answers in ~1s with no reload."""
    env = {**os.environ, "OLLAMA_HOST": f"{bind}:{PORT}", "OLLAMA_CONTEXT_LENGTH": NUM_CTX}
    if keep_alive is not None:
        env["OLLAMA_KEEP_ALIVE"] = keep_alive
    subprocess.Popen(["ollama", "serve"], env=env)
    for _ in range(180):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/version", timeout=2)
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("ollama serve did not become ready in time")


@app.function(image=image, volumes={OLLAMA_DIR: models_volume}, timeout=3600)
def download_models():
    """One-off: pull the models into the cached Volume (no GPU needed)."""
    _start_ollama()
    for m in MODELS:
        print(f"pulling {m} …", flush=True)
        subprocess.run(
            ["ollama", "pull", m],
            env={**os.environ, "OLLAMA_HOST": f"127.0.0.1:{PORT}"},
            check=True,
        )
    models_volume.commit()
    print("cached models:", MODELS, flush=True)


@app.function(
    image=image,
    gpu=GPU,
    volumes={OLLAMA_DIR: models_volume},
    scaledown_window=300,        # stay warm 5 min after the last request, then -> 0
    timeout=3600,
    min_containers=MIN_CONTAINERS,
)
@modal.web_server(port=PORT, startup_timeout=300, requires_proxy_auth=True)
def serve():
    """GPU-backed Ollama HTTP endpoint, protected by Modal proxy auth."""
    models_volume.reload()                 # pick up models pulled by download_models
    _start_ollama(keep_alive="-1")         # never unload while the container is warm
    # Preload the LLM into GPU so the very first user request is instant (no 40s
    # load). Best paired with MODAL_MIN_CONTAINERS=1 to keep one container warm.
    try:
        subprocess.run(
            ["ollama", "run", LLM_MODEL, "ok"],
            env={**os.environ, "OLLAMA_HOST": f"127.0.0.1:{PORT}"},
            timeout=180,
            check=False,
        )
    except Exception:
        pass
