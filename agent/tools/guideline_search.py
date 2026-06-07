"""agent/tools/guideline_search.py — RAG over the UNHCR guidelines.

Semantic search over the indexed UNHCR Handbook + Guidelines
(specs/data/guidelines_index.json, built by data/scripts/build_guidelines_index.py).
The assessment agent calls this to ground its legal reasoning in the *actual*
guidance and cite it — so it does not invent or misstate the law.

Pure Python (cosine over the cached vectors); embeddings via the local Ollama
embedding model. Returns real excerpts or a structured error — never fabricated.
"""

from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from pathlib import Path

from agent.tools.base import AgentTool

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INDEX = REPO_ROOT / "specs" / "data" / "guidelines_index.json"
EMBED_MODEL_DEFAULT = "nomic-embed-text"


@lru_cache(maxsize=1)
def _index() -> dict:
    if not INDEX.exists():
        return {"model": None, "chunks": []}
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    for c in data.get("chunks", []):
        vec = c["embedding"]
        c["_norm"] = math.sqrt(sum(v * v for v in vec)) or 1.0
    return data


def _embed(query: str) -> list[float]:
    import ollama
    model = (_index().get("model")) or os.getenv("EMBED_MODEL", EMBED_MODEL_DEFAULT)
    client = ollama.Client(host=os.getenv("OLLAMA_HOST"))
    return client.embed(model=model, input=query)["embeddings"][0]


def search(query: str, k: int = 4) -> dict:
    """Return the top-k most relevant guideline excerpts for ``query``."""
    data = _index()
    chunks = data.get("chunks", [])
    if not chunks:
        return {"error": "index_missing",
                "detail": "Run data/scripts/build_guidelines_index.py to build the guideline index."}
    if not query or not query.strip():
        return {"error": "empty_query"}

    q = _embed(query)
    qnorm = math.sqrt(sum(v * v for v in q)) or 1.0
    scored = []
    for c in chunks:
        dot = sum(a * b for a, b in zip(q, c["embedding"]))
        scored.append((dot / (qnorm * c["_norm"]), c))
    scored.sort(key=lambda s: s[0], reverse=True)

    results = [
        {"guideline": c["guideline"], "excerpt": " ".join(c["text"].split())[:600],
         "score": round(float(score), 3)}
        for score, c in scored[:k]
    ]
    return {"query": query, "results": results}


async def _execute(args: dict) -> dict:
    args = args or {}
    try:
        return search(args.get("query", ""), int(args.get("k", 4)))
    except Exception as exc:  # noqa: BLE001
        return {"error": "search_failed", "detail": f"{type(exc).__name__}: {exc}"}


guideline_search_tool = AgentTool(
    name="guideline_search",
    description=(
        "Search the official UNHCR Handbook and Guidelines on International "
        "Protection for guidance relevant to this case (e.g. a persecution "
        "ground, internal flight, sur place, exclusion). Use it to ground and "
        "cite your legal reasoning instead of relying on memory."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What guidance to look up"},
            "k": {"type": "integer", "description": "How many excerpts (default 4)"},
        },
        "required": ["query"],
    },
    execute=_execute,
)


__all__ = ["guideline_search_tool", "search"]
