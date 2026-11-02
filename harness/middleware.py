"""Middleware: code that runs around every model call and every tool call.

The loop asks each middleware in order. The first `deny` wins; an `ask` beats `allow`.
This is where a harness enforces policy, so the prompt never has to.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from . import config
from .events import Event
from .compaction import COMPACTION_PROMPT, Compactor
from .middleware_base import ALLOW, Decision, Middleware, StopRun
from .tools import update_todos

if TYPE_CHECKING:
    from .events import RunContext


class CallLimit(Middleware):
    """Budgets per run. A runaway loop is stopped by a counter, not by asking the model nicely."""

    name, component = "CallLimit", "actions"

    def __init__(self, max_model_calls: int = 8, max_tool_calls: int = 10):
        self.max_model_calls = max_model_calls
        self.max_tool_calls = max_tool_calls

    async def before_model(self, messages, ctx):
        if ctx.state["calls"]["model"] >= self.max_model_calls:
            raise StopRun(f"Model call limit reached ({self.max_model_calls} per run).", self.component)
        return messages

    async def before_tool(self, call, tool, ctx):
        if ctx.state["calls"]["tool"] > self.max_tool_calls:
            return Decision("deny", f"Tool call limit reached ({self.max_tool_calls} per run). "
                                    "Stop calling tools and answer with what you have.", self.component)
        return ALLOW


class TodoTracker(Middleware):
    """Gives the model a planning tool and shows the plan to the user as it changes."""

    name, component = "TodoTracker", "actions"

    def tools(self):
        return [update_todos]

    async def after_tool(self, call, tool, result, ok, ctx):
        if tool.name == "update_todos" and ok:
            ctx.emit(Event("todo_update", {"items": ctx.state.get("todos", [])}, component=self.component))


# [stage:3] Who may use which tool
ROLE_TOOLS: dict[str, set[str]] = {
    "sales":       {"list_customers", "lookup_customer", "send_proposal"},
    "engineering": {"list_customers", "lookup_customer", "lookup_issue"},
    "finance":     {"list_customers", "lookup_customer", "get_revenue"},
}
# [/stage:3]


class RoleGate(Middleware):
    """Role-based tool permissions for the company tools."""

    name, component = "RoleGate", "boundaries"

    def __init__(self, permissions: dict[str, set[str]] | None = None):
        self.permissions = permissions or ROLE_TOOLS
        self.governed = set().union(*self.permissions.values())  # tools no role gets by default

    async def before_tool(self, call, tool, ctx):
        allowed = self.permissions.get(ctx.role, set())
        if tool.component == "actions" and tool.name in self.governed and tool.name not in allowed:
            # Permissions are enforced here, in code, not in the prompt.
            return Decision("deny", f"Role '{ctx.role}' is not allowed to use {tool.name}. "
                                    f"Allowed: {', '.join(sorted(allowed)) or 'none'}.")
        return ALLOW


class ApprovalGate(Middleware):
    """Side effects that matter wait for a human."""

    name, component = "ApprovalGate", "boundaries"

    def __init__(self, names: set[str] | None = None):
        self.names = set(names or ())

    async def before_tool(self, call, tool, ctx):
        if tool.requires_approval or tool.name in self.names:
            return Decision("ask", f"{tool.name} needs a human's approval.")
        return ALLOW


class AuditLog(Middleware):
    """An append-only record of every tool call and what the harness decided."""

    name, component = "AuditLog", "boundaries"

    def __init__(self, path: Path | None = None):
        self.path = path

    async def after_tool(self, call, tool, result, ok, ctx):
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "session_id": ctx.session_id,
            "role": ctx.role,
            "tool": tool.name,
            "args": json.dumps(call.arguments, ensure_ascii=False)[:300],
            "ok": ok,
            "decision": ctx.state.get("last_decision", "allow"),
        }
        path = self.path or config.AUDIT_LOG
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        ctx.emit(Event("audit", record, component=self.component))


__all__ = ["Decision", "StopRun", "Middleware", "CallLimit", "TodoTracker", "RoleGate",
           "ApprovalGate", "AuditLog", "Compactor", "COMPACTION_PROMPT", "ROLE_TOOLS"]
