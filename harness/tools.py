"""All tools in one import: the plumbing, the company tools, the workspace tools, and planning."""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict

from .context import make_load_skill_tool
from .tooling import Tool, ToolError, ToolRegistry, schema_for, tool
from .tools_company import COMPANY_TOOLS, get_revenue, lookup_customer, lookup_issue, send_proposal
from .tools_workspace import (WORKSPACE_TOOLS, list_workspace_files, read_workspace_file,
                              workspace_target, write_workspace_file)

if TYPE_CHECKING:
    from .events import RunContext


class TodoItem(TypedDict):
    text: str
    status: Literal["pending", "in_progress", "done"]


TODO_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string"},
                   "status": {"type": "string", "enum": ["pending", "in_progress", "done"]}},
    "required": ["text", "status"],
}


@tool(component="actions")
async def update_todos(items: list[dict], ctx: RunContext) -> str:
    """Write your plan as a todo list for multi-step work. Send the whole list every time,
    marking items pending, in_progress or done as you go."""
    clean = []
    for item in items:
        if not isinstance(item, dict) or "text" not in item:
            raise ToolError("Each todo needs a 'text' and a 'status' (pending | in_progress | done).")
        status = item.get("status", "pending")
        clean.append({"text": str(item["text"]), "status": status if status in
                      ("pending", "in_progress", "done") else "pending"})
    ctx.state["todos"] = clean
    return f"ok ({len(clean)} items)"


update_todos.parameters["properties"]["items"]["items"] = TODO_SCHEMA

__all__ = [
    "Tool", "ToolError", "ToolRegistry", "tool", "schema_for", "TodoItem",
    "COMPANY_TOOLS", "WORKSPACE_TOOLS", "lookup_customer", "lookup_issue", "get_revenue",
    "send_proposal", "write_workspace_file", "read_workspace_file", "list_workspace_files",
    "workspace_target", "make_load_skill_tool", "update_todos",
]
