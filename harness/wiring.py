"""Turns Agent(...) keywords into the three things the loop runs on: a prompt, tools, middleware.

This is why each stage can be one constructor call: every keyword installs its component here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .compaction import Compactor
from .context import DEFAULT_INSTRUCTIONS, compose_prompt, discover_skills, make_load_skill_tool
from .llm import LLM
from .middleware import ApprovalGate, AuditLog, CallLimit, ProtectedPaths, RoleGate
from .middleware_base import Middleware
from .subagents import SubagentDef, make_run_subagent_tool
from .tooling import Tool, ToolRegistry
from .tools_workspace import WORKSPACE_TOOLS


@dataclass
class Harness:
    system_prompt: str
    tools: ToolRegistry
    middlewares: list[Middleware]


def _model_switcher(llm: LLM):
    """Subagents may use another model on the same endpoint, if the LLM supports that."""
    return lambda model: llm.for_model(model) if hasattr(llm, "for_model") else llm


def assemble(*, llm: LLM, role: str, instructions: str | Path, skills: Path | None,
             tools: list[Tool], middleware: list[Middleware], subagents: list[SubagentDef],
             permissions: dict[str, set[str]] | None, approve: set[str] | None,
             protected_paths: list[Path] | None, audit: bool, workspace: Path | None,
             compaction: Compactor | None) -> Harness:
    text = instructions.read_text(encoding="utf-8") if isinstance(instructions, Path) else instructions
    skill_list = discover_skills(skills) if skills else []

    registry = ToolRegistry()
    if skill_list:
        registry.add(make_load_skill_tool(skill_list))
    for t in [*tools, *(WORKSPACE_TOOLS if workspace else [])]:
        registry.add(t)

    # Order matters: boundaries first, then the user's middleware, then audit and compaction.
    chain: list[Middleware] = []
    if permissions is not None:
        chain.append(RoleGate(permissions))
    if protected_paths is not None:
        chain.append(ProtectedPaths(protected_paths))
    if approve:
        chain.append(ApprovalGate(approve))
    chain += list(middleware)
    if audit:
        chain.append(AuditLog())
    if compaction is not None:
        compaction.llm = compaction.llm or llm  # the summary is written by the agent's own model
        chain.append(compaction)
    for mw in chain:
        for t in mw.tools():
            registry.add(t)

    if subagents:
        registry.add(make_run_subagent_tool(subagents, registry, _model_switcher(llm),
                                            child_middleware=lambda: [CallLimit(6, 8)]))

    show_role = text != DEFAULT_INSTRUCTIONS or permissions is not None  # a bare chatbot has no "user"
    prompt = compose_prompt(text, role=role if show_role else None, skills=skill_list,
                            boundaries=permissions is not None, workspace=workspace is not None,
                            summaries=compaction is not None)
    return Harness(prompt, registry, chain)
