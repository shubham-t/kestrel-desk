"""Subagents: a fresh agent with its own short context, a narrow toolset and a cheaper model.

The parent delegates a task and gets back one answer. The child's work never enters the
parent's history (only its final text does), which keeps the parent's context small.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from .config import settings
from .events import Event
from .middleware_base import Middleware
from .tooling import Tool, ToolError, ToolRegistry, tool

if TYPE_CHECKING:
    from .events import RunContext
    from .llm import LLM


@dataclass
class SubagentDef:
    name: str
    description: str
    system_prompt: str
    tools: list[str]
    model: str | None = None  # None -> settings.subagent_model


# [stage:2] A subagent: its own prompt, a subset of tools, a cheaper model
PROPOSAL_REVIEWER = SubagentDef(
    name="proposal-reviewer",
    description="Checks a drafted proposal against the customer record and flags commitments "
                "the record does not support. Use after drafting any proposal.",
    system_prompt="You are a read-only proposal reviewer at Kestrel Software. If the task names a "
                  "saved draft and you have read_workspace_file, read it. Call lookup_customer for "
                  "the customer in the draft, then return a terse checklist with three headings: "
                  "Supported, Unsupported, Missing. Cite the customer id. Do not rewrite the proposal.",
    tools=["lookup_customer", "read_workspace_file"],  # only those the parent has are given
)
# [/stage:2]


def make_run_subagent_tool(defs: list[SubagentDef], registry: ToolRegistry,
                           llm_factory: Callable[[str], "LLM"],
                           child_middleware: Callable[[], list[Middleware]] | None = None) -> Tool:
    """Build the `run_subagent` tool for these definitions, drawing child tools from `registry`."""
    by_name = {d.name: d for d in defs}
    catalog = "; ".join(f"{d.name}: {d.description}" for d in defs)

    @tool(component="actions")
    async def run_subagent(name: str, task: str, ctx: RunContext) -> str:
        """Delegate a self-contained task to a subagent and get its answer back."""
        from .loop import Agent  # late import: the loop builds subagents, subagents build loops

        sub = by_name.get(name)
        if sub is None:
            raise ToolError(f"Unknown subagent '{name}'. Available: {', '.join(by_name)}")
        child = Agent(model=llm_factory(sub.model or settings.subagent_model),
                      instructions=sub.system_prompt,
                      # Only tools the parent actually has: no workspace before stage 4, silently.
                      tools=[registry.get(t) for t in sub.tools if t in registry],
                      middleware=child_middleware() if child_middleware else [],
                      role=ctx.role, stage=ctx.stage, session_id=f"{ctx.session_id}:{name}")
        ctx.emit(Event("subagent_start", {"name": name, "task": task}, component="actions"))
        final, failed = "", False
        async for event in child.run(task):
            event.subagent = event.subagent or name  # the UI nests these under the subagent card
            ctx.emit(event)
            if event.kind == "text_done":
                final = event.data.get("text", "")
            if event.kind == "run_end" and event.data.get("error"):
                failed = True
        ctx.emit(Event("subagent_end", {"name": name, "ok": not failed, "preview": final[:400]},
                       component="actions"))
        if failed and not final:
            raise ToolError(f"Subagent '{name}' failed before answering.")
        return final

    run_subagent.description += f" Available subagents — {catalog}"
    return run_subagent
