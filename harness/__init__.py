"""Kestrel Desk: a hand-built agent harness, one component per stage.

Public API: `Agent(...)` (one keyword per component) and `@tool`. `harness.stages.build_agent`
composes the five talk stages.
"""
from __future__ import annotations

from .events import Event, RunContext
from .loop import Agent
from .tooling import Tool, ToolError, ToolRegistry, tool

__all__ = ["Agent", "Event", "RunContext", "Tool", "ToolError", "ToolRegistry", "tool"]
