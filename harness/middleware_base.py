"""Middleware base types: the Decision a middleware returns and the hook interface."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .llm import ToolCall, Usage
from .tooling import Tool

if TYPE_CHECKING:
    from .events import RunContext


@dataclass
class Decision:
    action: Literal["allow", "deny", "ask"]
    reason: str = ""
    component: str = "boundaries"


ALLOW = Decision("allow")


class StopRun(Exception):
    """Raised by a middleware to end the run cleanly (e.g. a hard call limit)."""

    def __init__(self, reason: str, component: str = "actions"):
        super().__init__(reason)
        self.reason = reason
        self.component = component


class Middleware:
    """Base class: every hook is a no-op / allow. Subclasses override what they need."""

    name = "Middleware"
    component = "actions"

    async def before_model(self, messages: list[dict], ctx: RunContext) -> list[dict]:
        return messages

    async def after_model(self, assistant_msg: dict, usage: Usage | None, ctx: RunContext) -> None:
        return None

    async def before_tool(self, call: ToolCall, tool: Tool, ctx: RunContext) -> Decision:
        return ALLOW

    async def after_tool(self, call: ToolCall, tool: Tool, result: str, ok: bool, ctx: RunContext) -> None:
        return None

    def tools(self) -> list[Tool]:
        return []
