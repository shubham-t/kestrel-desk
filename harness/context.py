"""Context: what the model knows before it does anything.

AGENTS.md is always in the prompt. Skills are listed by name and description only; their
bodies are loaded on demand with `load_skill`, so the prompt stays small.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from . import config
from .tooling import Tool, ToolError, tool

if TYPE_CHECKING:
    from .events import RunContext

DEFAULT_INSTRUCTIONS = "You are a helpful assistant."
ROLE_RULE = ("Use your tools for whatever the user asks. If the harness blocks a call, tell the user "
             "plainly what was blocked and which role could do it; do not guess the answer instead.")
WORKSPACE_RULE = "You can save files under workspace/. When you save something, tell the user the path."
SUMMARY_RULE = "Earlier turns may appear as a '[Conversation summary]' message."


def load_agents_md() -> str:
    return (config.COMPANY_DIR / "AGENTS.md").read_text(encoding="utf-8")


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path


def _parse_skill(path: Path) -> Skill:
    """Parse the `--- name: / description: ---` frontmatter; the rest is the body."""
    text = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = text
    if text.startswith("---"):
        _, front, body = text.split("---", 2)
        for line in front.strip().splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return Skill(name=meta.get("name") or path.parent.name, description=meta.get("description", ""),
                 body=body.strip(), path=path)


def discover_skills(skills_dir: Path | None = None) -> list[Skill]:
    """Every `<dir>/*/SKILL.md`, sorted by name."""
    root = skills_dir or config.SKILLS_DIR
    return sorted((_parse_skill(p) for p in root.glob("*/SKILL.md")), key=lambda s: s.name)


def skills_index_text(skills: list[Skill]) -> str:
    lines = ["Available skills (load with load_skill):"]
    lines += [f"- {s.name}: {s.description}" for s in skills]
    return "\n".join(lines)


def compose_prompt(instructions: str, *, role: str | None = None, skills: list[Skill] | None = None,
                   boundaries: bool = False, workspace: bool = False, summaries: bool = False) -> str:
    """Assemble the system prompt from the parts each Agent keyword contributes."""
    parts = [instructions.strip()]
    if role:
        parts.append(f"Current user: role={role}.")
    if skills:
        parts.append(skills_index_text(skills))
    if boundaries:
        parts.append(ROLE_RULE)
    extra = " ".join(rule for rule, on in ((WORKSPACE_RULE, workspace), (SUMMARY_RULE, summaries)) if on)
    if extra:
        parts.append(extra)
    return "\n\n".join(parts)


def build_system_prompt(stage: int, role: str, skills: list[Skill]) -> str:
    """The prompt a given stage ends up with (Agent builds the same text from its keywords)."""
    if stage == 0:
        return DEFAULT_INSTRUCTIONS
    return compose_prompt(load_agents_md(), role=role, skills=skills,
                          boundaries=stage >= 3, workspace=stage >= 4, summaries=stage >= 4)


def make_load_skill_tool(skills: list[Skill]) -> Tool:
    """Progressive disclosure: the prompt lists skills; the body arrives only when asked for."""
    by_name = {s.name: s for s in skills}

    # [stage:1] Skills load on demand
    @tool(component="context")
    async def load_skill(name: str, ctx: RunContext) -> str:
        """Load the full instructions of a skill listed in the system prompt.
        Call it before doing the kind of task the skill covers."""
        if name not in by_name:
            raise ToolError(f"Unknown skill '{name}'. Valid names: {', '.join(by_name)}")
        return by_name[name].body
    # [/stage:1]

    return load_skill
