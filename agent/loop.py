"""agent/loop.py — pure-Python agent loop.

Ported from the structural patterns of pi-agent-core (the while-loop, typed
event stream, tool lifecycle, steering queue) but implemented entirely in
Python. No Node.js, no subprocess, no NDJSON bridge.

LLM calls go to a local Ollama instance via ``ollama.AsyncClient`` (or, when
``MODEL_PROVIDER`` is not ``"ollama"``, to ``litellm.acompletion``). The model
is a parameter, read from the ``MODEL_ID`` env var (default ``qwen2.5:7b``).

Contract (see specs/ARCHITECTURE.md §1):
    async def run(prompt, session, system_prompt, tools, thinking_level)
        -> AsyncGenerator[AgentEvent, None]

Guarantees:
  * yields ``AgentStartEvent`` first, before any network call
  * never buffers — each event is yielded as produced
  * never raises through the generator — failures become ``ErrorEvent``
  * supports mid-run steering via ``steer()`` and graceful ``abort()``
  * each Gradio session should use its own loop instance (no shared state)
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
from dataclasses import dataclass
from typing import AsyncGenerator, Callable, Iterable, Optional

from agent.events import (
    AgentEndEvent,
    AgentEvent,
    AgentStartEvent,
    ErrorEvent,
    TextDeltaEvent,
    ToolEndEvent,
    ToolStartEvent,
    TurnEndEvent,
    TurnStartEvent,
)
from agent.tools.base import AgentTool

DEFAULT_MODEL_ID = "qwen2.5:7b"
# Safety bound on tool/LLM turns so a confused model cannot loop forever.
MAX_TURNS = 12


@dataclass
class LoopHooks:
    """Agent-loop control hooks — a Python port of pi's AgentLoopConfig hooks.

    Each is optional and may be sync or async. They give the harness real agency
    over the loop without the model deciding control flow:

    * ``transform_context(history)`` -> history  — shape context before the call
    * ``before_tool_call(name, args)`` -> {"block": bool, "reason": str} | None
    * ``after_tool_call(name, args, result)`` -> replacement result dict | None
    * ``should_stop_after_turn(assistant_message, history)`` -> bool — graceful stop
    * ``prepare_next_turn(assistant_message, history)`` -> {"thinking_level": ...} | None
    """

    transform_context: Optional[Callable] = None
    before_tool_call: Optional[Callable] = None
    after_tool_call: Optional[Callable] = None
    should_stop_after_turn: Optional[Callable] = None
    prepare_next_turn: Optional[Callable] = None


async def _maybe_await(fn, *args):
    if fn is None:
        return None
    result = fn(*args)
    if inspect.isawaitable(result):
        return await result
    return result


class AgentLoop:
    """A stateless-per-session driver around the LLM + tools.

    Construct one instance per Gradio session (T019). The instance holds the
    steering queue and abort flag for that session's in-flight run.
    """

    def __init__(
        self,
        tools: Optional[Iterable[AgentTool]] = None,
        model_id: Optional[str] = None,
        host: Optional[str] = None,
    ) -> None:
        self.tools: list[AgentTool] = list(tools or [])
        self.model_id = model_id or os.getenv("MODEL_ID", DEFAULT_MODEL_ID)
        self.provider = os.getenv("MODEL_PROVIDER", "ollama")
        self._host = host or os.getenv("OLLAMA_HOST")
        self._client = None  # lazily created so import never needs a server
        # Not all models accept the `think` parameter (e.g. qwen2.5:7b). We
        # optimistically try it, then disable it for this session on first
        # rejection so later turns don't keep 400-ing.
        self._supports_thinking = True
        self.steering_queue: "asyncio.Queue[str]" = asyncio.Queue()
        self.abort_event = asyncio.Event()

    # -- public controls -------------------------------------------------

    def steer(self, message: str) -> None:
        """Inject a user message to be picked up at the next turn boundary."""
        self.steering_queue.put_nowait(message)

    def abort(self) -> None:
        """Request the loop stop gracefully at the next safe point."""
        self.abort_event.set()

    def reset(self) -> None:
        """Clear the abort flag and drain any pending steering messages."""
        self.abort_event = asyncio.Event()
        while not self.steering_queue.empty():
            self.steering_queue.get_nowait()

    # -- internals -------------------------------------------------------

    def _client_lazy(self):
        if self._client is None:
            import ollama

            from agent.ollama_auth import ollama_headers

            self._client = ollama.AsyncClient(host=self._host, headers=ollama_headers() or None)
        return self._client

    def _tool_map(self, tools: list[AgentTool]) -> dict[str, AgentTool]:
        return {t.name: t for t in tools}

    async def _iter_chat(self, client, messages, tool_schemas, think_arg):
        """Stream chat chunks, gracefully degrading if the model rejects the
        `think` parameter (non-thinking models like qwen2.5:7b).

        The rejection is a 400 raised when the stream begins iterating, before
        any chunk is produced, so it is safe to retry once without `think`. If
        chunks have already been yielded, any error propagates unchanged.
        """
        want_think = think_arg if self._supports_thinking else None
        attempts = [want_think] + ([None] if want_think is not None else [])

        for attempt_think in attempts:
            produced = False
            try:
                stream = await client.chat(
                    model=self.model_id,
                    messages=messages,
                    tools=tool_schemas,
                    stream=True,
                    think=attempt_think,
                )
                async for chunk in stream:
                    produced = True
                    yield chunk
                return
            except Exception as exc:  # noqa: BLE001
                unsupported = attempt_think is not None and "thinking" in str(exc).lower()
                if unsupported and not produced:
                    self._supports_thinking = False
                    continue  # retry this turn without `think`
                raise

    async def _execute_tool(self, name: str, args: dict, tool_map: dict) -> dict:
        tool = tool_map.get(name)
        if tool is None:
            return {"error": "unknown_tool", "name": name}
        return await tool.execute(args or {})

    # -- the loop --------------------------------------------------------

    async def run(
        self,
        prompt: str,
        session=None,
        system_prompt: str = "",
        tools: Optional[Iterable[AgentTool]] = None,
        thinking_level: str = "low",
        hooks: Optional[LoopHooks] = None,
    ) -> AsyncGenerator[AgentEvent, None]:
        # AgentStartEvent is yielded before any network call (SC-004).
        yield AgentStartEvent()

        hooks = hooks or LoopHooks()
        active_tools = list(tools) if tools is not None else self.tools
        tool_map = self._tool_map(active_tools)
        tool_schemas = [t.to_ollama_schema() for t in active_tools] or None
        think_level = thinking_level

        # Conversation history excludes the system prompt (supplied fresh each call).
        history: list[dict] = list(getattr(session, "messages", None) or [])
        if prompt:
            history.append({"role": "user", "content": prompt})

        def api_messages(ctx: list[dict]) -> list[dict]:
            sys = [{"role": "system", "content": system_prompt}] if system_prompt else []
            return sys + ctx

        try:
            client = self._client_lazy()

            for _turn in range(MAX_TURNS):
                if self.abort_event.is_set():
                    break

                yield TurnStartEvent()

                # transform_context hook (pi: transformContext) — shape context.
                ctx = await _maybe_await(hooks.transform_context, history) or history

                assistant_text = ""
                tool_calls: list = []
                think_arg = think_level if think_level in ("low", "medium", "high") else None

                async for chunk in self._iter_chat(client, api_messages(ctx), tool_schemas, think_arg):
                    if self.abort_event.is_set():
                        break
                    msg = getattr(chunk, "message", None)
                    if msg is None:
                        continue
                    if getattr(msg, "content", None):
                        assistant_text += msg.content
                        yield TextDeltaEvent(delta=msg.content)
                    if getattr(msg, "tool_calls", None):
                        tool_calls.extend(msg.tool_calls)

                assistant_message: dict = {"role": "assistant", "content": assistant_text}

                if tool_calls:
                    serialised_calls = []
                    for call in tool_calls:
                        fn = call.function
                        args = fn.arguments
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except (ValueError, TypeError):
                                args = {}
                        serialised_calls.append({"function": {"name": fn.name, "arguments": args}})
                    assistant_message["tool_calls"] = serialised_calls
                    history.append(assistant_message)

                    terminate_flags = []
                    for call in serialised_calls:
                        name = call["function"]["name"]
                        args = call["function"]["arguments"]
                        yield ToolStartEvent(name=name, args=args)

                        # before_tool_call hook (pi: beforeToolCall) — guard/block.
                        guard = await _maybe_await(hooks.before_tool_call, name, args)
                        if guard and guard.get("block"):
                            result = {"error": "blocked", "reason": guard.get("reason", "blocked")}
                        else:
                            result = await self._execute_tool(name, args, tool_map)
                        # after_tool_call hook (pi: afterToolCall) — transform result.
                        replaced = await _maybe_await(hooks.after_tool_call, name, args, result)
                        if replaced is not None:
                            result = replaced

                        terminate_flags.append(bool(isinstance(result, dict) and result.get("terminate")))
                        yield ToolEndEvent(name=name, result=result)
                        history.append({
                            "role": "tool", "name": name,
                            "content": json.dumps(result, ensure_ascii=False),
                        })

                    yield TurnEndEvent(message=assistant_message)

                    # tool `terminate`: stop when every tool in the batch asked to.
                    if terminate_flags and all(terminate_flags):
                        break
                    if await _maybe_await(hooks.should_stop_after_turn, assistant_message, history):
                        break
                    upd = await _maybe_await(hooks.prepare_next_turn, assistant_message, history)
                    if upd and upd.get("thinking_level"):
                        think_level = upd["thinking_level"]
                    continue

                # No tool calls: final answer for this turn.
                history.append(assistant_message)
                yield TurnEndEvent(message=assistant_message)

                if await _maybe_await(hooks.should_stop_after_turn, assistant_message, history):
                    break
                if not self.steering_queue.empty():
                    history.append({"role": "user", "content": await self.steering_queue.get()})
                    continue
                break

            yield AgentEndEvent(messages=history)

        except Exception as exc:  # noqa: BLE001 — surfaced to UI, never raised through
            yield ErrorEvent(message=f"{type(exc).__name__}: {exc}")


def create_loop(
    tools: Optional[Iterable[AgentTool]] = None,
    model_id: Optional[str] = None,
    host: Optional[str] = None,
) -> AgentLoop:
    """Factory: a fresh, isolated AgentLoop for one Gradio session (T019).

    Each session must call this to get its own loop instance — the steering
    queue and abort flag are per-instance, so concurrent sessions never share
    mutable state.
    """
    return AgentLoop(tools=tools, model_id=model_id, host=host)


__all__ = ["AgentLoop", "AgentTool", "LoopHooks", "DEFAULT_MODEL_ID", "create_loop"]
