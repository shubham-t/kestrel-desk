"""The agent loop: model -> tool calls -> results -> model, until the model answers in text.

Everything else in the harness hooks into this loop: middleware around each model and
tool call, a human when a decision says "ask", a checkpoint after every message.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import AsyncIterator

from .approvals import ApprovalBroker, ApprovalRequest, AutoReject
from .compaction import Compactor
from .context import DEFAULT_INSTRUCTIONS
from .events import Event, RunContext
from .llm import LLM, ToolCall, Usage, make_llm
from .middleware_base import Decision, Middleware, StopRun
from .persistence import SessionStore
from .subagents import SubagentDef
from .tooling import Tool, ToolError
from .wiring import assemble

__all__ = ["Agent", "Event", "RunContext", "assistant_message", "tool_message"]


def assistant_message(text: str, calls: list[ToolCall]) -> dict:
    message: dict = {"role": "assistant", "content": text or None}
    if calls:
        message["tool_calls"] = [{"id": c.id, "type": "function",
                                  "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                                 for c in calls]
    elif not text:
        message["content"] = "(no reply)"
    return message


def tool_message(call_id: str, content: str) -> dict:
    return {"role": "tool", "tool_call_id": call_id, "content": content}


class Agent:
    """One constructor, one keyword per harness component. `run()` streams Events."""

    def __init__(self, *, model: LLM | str | None = None, instructions: str | Path = DEFAULT_INSTRUCTIONS,
                 skills: Path | None = None, tools: list[Tool] = (), middleware: list[Middleware] = (),
                 subagents: list[SubagentDef] = (), permissions: dict[str, set[str]] | None = None,
                 approve: set[str] | None = None, audit: bool = False, checkpointer: SessionStore | None = None,
                 workspace: Path | None = None, compaction: Compactor | None = None,
                 role: str = "sales", session_id: str | None = None,
                 approvals: ApprovalBroker | None = None, stage: int = 0):
        self.llm: LLM = make_llm(model) if model is None or isinstance(model, str) else model
        harness = assemble(llm=self.llm, role=role, instructions=instructions, skills=skills,
                           tools=list(tools), middleware=list(middleware), subagents=list(subagents),
                           permissions=permissions, approve=approve, audit=audit, workspace=workspace, compaction=compaction)
        self.system_prompt = harness.system_prompt
        self.tools = harness.tools
        self.middlewares = harness.middlewares
        self.approvals = approvals or AutoReject()  # nobody to ask -> fail closed
        self.store = checkpointer
        self.role, self.stage = role, stage
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self.ctx = RunContext(role=role, stage=stage, session_id=self.session_id)
        self._totals = Usage(0, 0)  # token counts for the current turn
        self.messages, self.resumed = self._open_session()

    def _open_session(self) -> tuple[list[dict], bool]:
        """With a checkpointer, an existing session id means: pick up where we left off."""
        if self.store is None:
            return [], False  # memory only: a restart forgets everything
        if self.store.exists(self.session_id):
            return self.store.load(self.session_id), True
        self.store.create(self.session_id, self.stage, self.role)
        return [], False

    # ------------------------------------------------------------------ the loop

    async def run(self, user_text: str) -> AsyncIterator[Event]:
        """Run one user turn and stream its Events. Closing or cancelling the stream cancels the run."""
        queue: asyncio.Queue[Event | None] = asyncio.Queue()
        self.ctx.emit = queue.put_nowait  # tools, middleware and subagents emit into the same stream
        task = asyncio.create_task(self._run(user_text))
        task.add_done_callback(lambda _: queue.put_nowait(None))
        try:
            while (event := await queue.get()) is not None:
                yield event
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def _run(self, user_text: str) -> None:
        """One turn, with every way it can end turned into events (never an exception)."""
        self.ctx.state["calls"] = {"model": 0, "tool": 0}
        self._totals = Usage(0, 0)
        self.ctx.emit(Event("run_start", {"session_id": self.session_id, "stage": self.stage,
                                          "role": self.role, "text": user_text}))
        self._close_dangling_calls("aborted")  # a crashed earlier turn must not poison this one
        self._append({"role": "user", "content": user_text})
        try:
            await self._loop()
            self._end()
        except StopRun as stop:  # a budget ran out: end the turn cleanly and say why
            self.ctx.emit(Event("decision", {"tool": None, "action": "deny", "reason": stop.reason,
                                             "silent": False}, component=stop.component))
            note = f"Stopped by harness: {stop.reason}"
            self._append({"role": "assistant", "content": note})
            self.ctx.emit(Event("text_done", {"text": note}, component="model"))
            self._end(stopped=True)
        except asyncio.CancelledError:
            self._close_dangling_calls("cancelled")
            raise
        except Exception as exc:  # model/endpoint errors become events, never a crash
            self._close_dangling_calls("aborted")
            self.ctx.emit(Event("error", {"message": str(exc), "type": type(exc).__name__,
                                          "status": getattr(exc, "status", None)}))
            self._end(error=True)

    async def _loop(self) -> None:
        """The agent loop. Every other harness component hooks into one of these lines."""
        while True:
            messages = await self._before_model()
            text, calls, usage = await self._call_model(messages)
            reply = assistant_message(text, calls)
            self._append(reply)  # the tool_calls message goes in before any tool result
            for mw in self.middlewares:
                await mw.after_model(reply, usage, self.ctx)
            if not calls:  # no tool calls: the model has answered, the turn is over
                self.ctx.emit(Event("text_done", {"text": text}, component="model"))
                return
            for call in calls:
                await self._handle_tool_call(call)
            # ...and back to the model with the results.

    async def _before_model(self) -> list[dict]:
        messages = [{"role": "system", "content": self.system_prompt}, *self.messages]
        for mw in self.middlewares:
            messages = await mw.before_model(messages, self.ctx)
        if self.ctx.state.pop("history_rewritten", False):  # compaction rewrites history for good
            self._replace_history(messages[1:])
        return messages

    async def _call_model(self, messages: list[dict]) -> tuple[str, list[ToolCall], Usage | None]:
        self.ctx.state["calls"]["model"] += 1
        text: list[str] = []
        calls: list[ToolCall] = []
        usage: Usage | None = None
        async for chunk in self.llm.stream(messages, self.tools.specs() or None):
            if chunk.text:
                text.append(chunk.text)
                self.ctx.emit(Event("text_delta", {"text": chunk.text}, component="model"))
            calls = chunk.tool_calls or calls
            usage = chunk.usage or usage
        if usage:
            self._totals.prompt_tokens += usage.prompt_tokens
            self._totals.completion_tokens += usage.completion_tokens
            self.ctx.emit(Event("usage", {"model": self.llm.model, "prompt_tokens": usage.prompt_tokens,
                                          "completion_tokens": usage.completion_tokens}, component="model"))
        return "".join(text), calls, usage

    async def _handle_tool_call(self, call: ToolCall) -> None:
        ctx, tool = self.ctx, self.tools.get(call.name)
        ctx.state["calls"]["tool"] += 1
        component = tool.component if tool else "actions"
        ctx.emit(Event("tool_call", {"id": call.id, "name": call.name, "arguments": call.arguments},
                       component=component))
        result, ok, outcome = await self._gate_and_run(call, tool)
        ctx.emit(Event("tool_result", {"id": call.id, "name": call.name, "ok": ok, "outcome": outcome,
                                       "preview": result[:400]}, component=component))
        if tool is not None:
            ctx.state["last_decision"] = outcome  # AuditLog records what was decided, not just what ran
            for mw in self.middlewares:
                await mw.after_tool(call, tool, result, ok, ctx)
        self._append(tool_message(call.id, result))  # the model sees the denial reason and can adapt

    async def _gate_and_run(self, call: ToolCall, tool: Tool | None) -> tuple[str, bool, str]:
        """Ask the middleware chain first; run the tool only if nothing said no. -> (result, ok, outcome)"""
        if tool is None:
            return (f"Tool error: unknown tool '{call.name}'. "
                    f"Available: {', '.join(self.tools.names())}"), False, "unknown"
        decision = await self._decide(call, tool)
        # Permissions are enforced here, in code, not in the prompt: a denied call never runs.
        if decision.action == "deny":
            return f"Blocked by harness: {decision.reason}", False, "deny"
        if decision.action == "ask" and not await self._ask_human(call, tool, decision):
            return "User rejected the action.", False, "rejected"
        result, ok = await self._execute(call, tool)
        return result, ok, "approved" if decision.action == "ask" else "allow"

    async def _decide(self, call: ToolCall, tool: Tool) -> Decision:
        """Run the middleware chain: the first deny wins; an ask beats allow."""
        verdict = Decision("allow", component=tool.component)
        for mw in self.middlewares:
            decision = await mw.before_tool(call, tool, self.ctx)
            if decision.action == "deny":
                verdict = decision
                break
            if decision.action == "ask":
                verdict = decision
        self.ctx.emit(Event("decision", {"id": call.id, "tool": tool.name, "action": verdict.action,
                                         "reason": verdict.reason, "silent": verdict.action == "allow"},
                            component=verdict.component))
        return verdict

    async def _ask_human(self, call: ToolCall, tool: Tool, decision: Decision) -> bool:
        """The run pauses here until a human answers (or the broker times out)."""
        req = ApprovalRequest(id=uuid.uuid4().hex[:12], tool=tool.name, arguments=call.arguments,
                              session_id=self.session_id)
        self.ctx.emit(Event("approval_request", {"request_id": req.id, "call_id": call.id, "tool": tool.name,
                                                 "arguments": call.arguments, "reason": decision.reason},
                            component="boundaries"))
        try:
            approved = bool(await self.approvals.ask(req))
        except Exception:
            approved = False  # a broken approver fails closed
        self.ctx.emit(Event("approval_result", {"request_id": req.id, "tool": tool.name, "approved": approved},
                            component="boundaries"))
        return approved

    async def _execute(self, call: ToolCall, tool: Tool) -> tuple[str, bool]:
        if call.raw_arguments is not None:
            return "Tool error: arguments were not valid JSON. Send a JSON object.", False
        try:
            return await tool.handler(call.arguments, self.ctx), True
        except ToolError as exc:
            return f"Tool error: {exc}", False
        except Exception as exc:  # a broken tool is reported to the model; it does not end the run
            return f"Tool error: {type(exc).__name__}: {exc}", False

    # ------------------------------------------------------------------ history + checkpoints

    def _append(self, message: dict) -> None:
        self.messages.append(message)
        if self.store is not None:  # checkpoint after every message, so a crash loses nothing
            self.store.append(self.session_id, message)
            self._checkpointed()

    def _replace_history(self, messages: list[dict]) -> None:
        self.messages = list(messages)
        if self.store is not None:
            self.store.replace_all(self.session_id, self.messages)
            self._checkpointed()

    def _checkpointed(self) -> None:
        self.ctx.emit(Event("checkpoint", {"session_id": self.session_id, "messages": len(self.messages)},
                            component="persistence"))

    def _close_dangling_calls(self, reason: str) -> None:
        """Every assistant tool call needs a result message, or the next model call is rejected."""
        for i in range(len(self.messages) - 1, -1, -1):
            message = self.messages[i]
            if message["role"] == "user":
                return
            if message["role"] == "assistant":
                answered = {m.get("tool_call_id") for m in self.messages[i + 1:] if m["role"] == "tool"}
                for call in message.get("tool_calls") or []:
                    if call["id"] not in answered:
                        self._append(tool_message(call["id"], f"Tool call {reason}: it did not run."))
                return

    def _end(self, *, error: bool = False, stopped: bool = False) -> None:
        calls, totals = self.ctx.state["calls"], self._totals
        self.ctx.emit(Event("run_end", {"session_id": self.session_id, "model_calls": calls["model"],
                                        "tool_calls": calls["tool"], "prompt_tokens": totals.prompt_tokens,
                                        "completion_tokens": totals.completion_tokens,
                                        "error": error, "stopped": stopped}))

    async def compact_now(self) -> list[Event]:
        """Force one compaction (the web demo's "Compact now" button). Returns the events it produced.
        Do not call while a run is in flight."""
        compactor = next((m for m in self.middlewares if isinstance(m, Compactor)), None)
        if compactor is None:
            return []
        events: list[Event] = []
        self.ctx.emit = events.append
        compacted = await compactor.compact([{"role": "system", "content": self.system_prompt},
                                             *self.messages], self.ctx)
        if self.ctx.state.pop("history_rewritten", False):
            self._replace_history(compacted[1:])
        return events
