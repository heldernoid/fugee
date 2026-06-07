"""agent/tools/web_search.py — real web search for asylum policy/safety (T035).

Backed by the Tavily Search API (https://tavily.com). Returns real results with
real URLs. If the API key is missing or the request fails, the tool raises /
returns a structured error — it never returns fabricated results (CLAUDE.md
Critical Rule 1; PLAN §Testing Philosophy).

Privacy (ARCHITECTURE.md §Security): queries are scoped to asylum / UNHCR /
country-safety / process information. The agent is instructed never to put the
person's private personal details into a search query.
"""

from __future__ import annotations

import os

import httpx

from agent.tools.base import AgentTool

TAVILY_URL = "https://api.tavily.com/search"
DEFAULT_TIMEOUT = 20.0

# A light focus hint appended to the query to keep results on-topic.
_FOCUS_HINT = {
    "asylum": "asylum policy",
    "safety": "country safety situation",
    "process": "asylum application process",
    "contacts": "UNHCR office legal aid contacts",
}


async def search(query: str, focus: str | None = None, max_results: int = 5) -> dict:
    """Run a real Tavily search. Raises on misconfiguration / API failure."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError(
            "TAVILY_API_KEY is not set — web_search cannot return real results. "
            "Set it in .env (see .env.example)."
        )
    if not query or not query.strip():
        raise ValueError("web_search requires a non-empty query")

    full_query = query.strip()
    hint = _FOCUS_HINT.get(focus or "")
    if hint:
        full_query = f"{full_query} ({hint})"

    payload = {
        "api_key": api_key,
        "query": full_query,
        "max_results": max_results,
        "search_depth": "basic",
    }

    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.post(TAVILY_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

    results = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", ""),
        }
        for r in data.get("results", [])
    ]
    return {"query": full_query, "results": results}


async def _execute(args: dict) -> dict:
    args = args or {}
    try:
        return await search(args.get("query", ""), args.get("focus"))
    except Exception as exc:  # noqa: BLE001 — surface as a tool error, no fake data
        return {"error": "search_failed", "detail": f"{type(exc).__name__}: {exc}"}


web_search_tool = AgentTool(
    name="web_search",
    description=(
        "Search the web for current asylum policies, UNHCR data, country safety, "
        "and process information. Use for time-sensitive facts. Do NOT include the "
        "person's private personal details in the query."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "focus": {
                "type": "string",
                "enum": ["asylum", "safety", "process", "contacts"],
            },
        },
        "required": ["query"],
    },
    execute=_execute,
)


__all__ = ["web_search_tool", "search"]
