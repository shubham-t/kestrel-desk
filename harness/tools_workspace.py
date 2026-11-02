"""Workspace tools: the one folder the agent may write into.

The tools enforce the boundary themselves (defense in depth); the ProtectedPaths
middleware enforces it again before the tool ever runs.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from . import config
from .tooling import ToolError, tool

if TYPE_CHECKING:
    from .events import RunContext


def workspace_target(raw: str) -> Path:
    """Where a model-supplied path lands: relative to workspace/ (a leading 'workspace/' is accepted)."""
    rel = Path(raw.strip().replace("\\", "/"))
    if rel.parts[:1] == ("workspace",):
        rel = Path(*rel.parts[1:]) if len(rel.parts) > 1 else Path(".")
    return (config.WORKSPACE_DIR / rel).resolve()


def _inside_workspace(raw: str) -> Path:
    target = workspace_target(raw)
    root = config.WORKSPACE_DIR.resolve()
    if not target.is_relative_to(root):
        raise ToolError(f"Path '{raw}' is outside workspace/. Only workspace/ is writable.")
    return target


def _display(path: Path) -> str:
    return "workspace/" + path.relative_to(config.WORKSPACE_DIR.resolve()).as_posix()


# [stage:4] Writes are confined to workspace/
@tool(component="persistence", read_only=False)
async def write_workspace_file(path: str, content: str, ctx: RunContext) -> str:
    """Save a text file under workspace/ (e.g. "acme-proposal.md"). Overwrites if it exists."""
    target = _inside_workspace(path)  # resolve() + is_relative_to: "../" tricks end here
    if target == config.WORKSPACE_DIR.resolve():
        raise ToolError("Give a file name, not the workspace folder itself.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Saved {len(content)} characters to {_display(target)}"
# [/stage:4]


@tool(component="persistence")
async def read_workspace_file(path: str, ctx: RunContext) -> str:
    """Read a text file from workspace/."""
    target = _inside_workspace(path)
    if not target.is_file():
        raise ToolError(f"No file at {path}. Use list_workspace_files to see what exists.")
    return target.read_text(encoding="utf-8")


@tool(component="persistence")
async def list_workspace_files(ctx: RunContext) -> str:
    """List the files saved under workspace/."""
    root = config.WORKSPACE_DIR.resolve()
    files = sorted(_display(p) for p in root.rglob("*") if p.is_file() and p.name != ".gitkeep")
    return "\n".join(files) if files else "(workspace is empty)"


WORKSPACE_TOOLS = [write_workspace_file, read_workspace_file, list_workspace_files]
