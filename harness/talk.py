"""What the audience sees about each stage: headline, problem, scenarios, and the code itself.

None of this changes how an agent behaves. The snippets are cut from the running source by
`# [stage:N] Title` / `# [/stage:N]` markers, so the slides can never drift from the code.
"""
from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from pathlib import Path

from .config import REPO_ROOT, STAGES


@dataclass
class Scenario:
    title: str
    role: str
    prompt: str
    watch: str  # one sentence telling the audience what to look at


_SCENARIOS: dict[int, list[Scenario]] = {
    0: [Scenario("Does it know us?", "sales",
                 "What do you know about Kestrel Software and our proposal process?",
                 "The model guesses or admits it doesn't know. Nothing lights up but the model.")],
    1: [Scenario("Skill-guided draft", "sales",
                 "Use the proposal-writing skill to draft a proposal for Acme Robotics: Enterprise plan, "
                 "40 seats, they care about SSO and audit logs.",
                 "load_skill fires (Context node), and the draft follows the skill's sections. "
                 "We still had to explain who Acme is.")],
    2: [Scenario("Look it up yourself", "sales",
                 "Draft a proposal for Acme Robotics and have the proposal-reviewer check it before you "
                 "show it to me.",
                 "lookup_customer, a todo list, then the subagent's nested review."),
        Scenario("Runaway loop", "engineering",
                 "For every open issue, look up its customer, then look up every other issue for that "
                 "customer, and keep going until you have checked everything twice.",
                 "CallLimit stops it.")],
    3: [Scenario("Wrong role", "engineering", "What was our revenue in FY2026?",
                 "RoleGate denies get_revenue; the model says so instead of guessing."),
        Scenario("Right role", "finance", "What was our revenue in FY2026?",
                 "Same question, allowed, answered with record ids."),
        Scenario("Needs a human", "sales",
                 "Draft a short Enterprise proposal for Acme Robotics (40 seats, SSO and audit logs) and "
                 'send it to procurement@acme-robotics.example with the subject '
                 '"Kestrel Enterprise proposal".',
                 "The approval card appears and the loop waits. Approve -> an outbox file and an audit "
                 "line. Try the same with ceo@acme-robotics.example: the tool rejects the unverified "
                 "address.")],
    4: [Scenario("Save it", "sales",
                 "Draft a short Enterprise proposal for Acme Robotics (40 seats, SSO and audit logs) and "
                 "save it as workspace/acme-proposal.md. Give me the path.",
                 "write_workspace_file (Persistence node); checkpoint events. Also show a write to "
                 "company/AGENTS.md being blocked."),
        Scenario("Come back tomorrow", "sales", "What did we save earlier, and what was in it?",
                 "Resume the previous session first: resumed history answers without re-reading. Then "
                 "trigger compaction on a long session and show the summary marker.")],
}

# unlocked_tools: tools that first appear at this stage.
# middlewares / subagents: everything the stage's agent has installed, in chain order.
_S3_CHAIN = ["RoleGate", "ProtectedPaths", "ApprovalGate", "CallLimit", "TodoTracker", "AuditLog"]
_DETAILS: dict[int, dict] = {
    0: dict(
        headline="Just a model and a prompt",
        problem="This is where most teams start: a system prompt, a message list and one model call. "
                "The model is capable, but it has never heard of Kestrel, our customers or how we write "
                "proposals. Let's see what it does with nothing around it.",
        bullets=["One system prompt: \"You are a helpful assistant.\"",
                 "A message list kept in memory", "One model call per turn, streamed",
                 "No tools, no company knowledge, no memory across restarts"],
        unlocked_tools=[], middlewares=[], subagents=[], new_keywords=["model"]),
    1: dict(
        headline="Tell it who we are",
        problem="The model knows nothing about Kestrel, so every answer about us is a guess. "
                "Pasting every playbook into every prompt would bloat it and go stale. "
                "It needs standing instructions, plus know-how it pulls in only when a task calls for it.",
        bullets=["company/AGENTS.md is the always-on system prompt",
                 "Skills are listed by name and description only",
                 "load_skill pulls a skill's full text on demand"],
        unlocked_tools=["load_skill"], middlewares=[], subagents=[],
        new_keywords=["instructions", "skills"]),
    2: dict(
        headline="Let it look things up itself",
        problem="With context alone, the model still can't see our records, so we had to tell it who Acme is. "
                "It needs tools to fetch facts, a loop that keeps going until the job is done, and a second "
                "pair of eyes on its draft. A loop also needs a brake, or one bad request runs forever.",
        bullets=["Four company tools declared with @tool",
                 "The agent loop: model -> tools -> results -> model",
                 "Middleware: CallLimit budgets, TodoTracker plans",
                 "A proposal-reviewer subagent with its own context"],
        unlocked_tools=["lookup_customer", "lookup_issue", "get_revenue", "send_proposal",
                        "update_todos", "run_subagent"],
        middlewares=["CallLimit", "TodoTracker"], subagents=["proposal-reviewer"],
        new_keywords=["tools", "middleware", "subagents"]),
    3: dict(
        headline="Draw the lines in code",
        problem="Now the agent can act, and it treats every user the same. An engineer can pull revenue, "
                "anyone can email a customer, and a prompt that says please don't is not a control. "
                "Permissions, approvals and an audit trail have to live in the harness, where the model "
                "can't talk its way past them.",
        bullets=["RoleGate: each role gets only its tools",
                 "ProtectedPaths: company files and code are never writable",
                 "send_proposal pauses for a human's approval",
                 "Every tool call is written to an audit log"],
        unlocked_tools=[], middlewares=_S3_CHAIN, subagents=["proposal-reviewer"],
        new_keywords=["permissions", "approve", "protected_paths", "audit"]),
    4: dict(
        headline="Remember, save, and keep going",
        problem="Everything so far lives in memory: restart the server and the conversation is gone, and "
                "nothing the agent writes survives. Long sessions also keep growing until the prompt is "
                "too big and too slow. We need checkpoints to resume, one safe folder to write in, and a way "
                "to shrink old turns.",
        bullets=["Every message checkpointed to SQLite; sessions resume",
                 "A writable workspace/ with file tools",
                 "Compactor summarizes old turns when the prompt grows"],
        unlocked_tools=["write_workspace_file", "read_workspace_file", "list_workspace_files"],
        middlewares=[*_S3_CHAIN, "Compactor"], subagents=["proposal-reviewer"],
        new_keywords=["checkpointer", "workspace", "compaction"]),
}


def scenarios(stage: int) -> list[Scenario]:
    return list(_SCENARIOS.get(stage, []))


def describe_stage(stage: int) -> dict:
    """Everything Screen A shows for a stage (the web app and the deck read this)."""
    info, details = STAGES[stage], _DETAILS[stage]
    return {"id": info.id, "name": info.name, "component": info.component, "tagline": info.tagline,
            **{k: v if isinstance(v, str) else list(v) for k, v in details.items()}}


# The stage's Agent(...) call always comes first, then its supporting definitions.
_SNIPPET_ORDER = ["stages.py", "middleware.py", "tools_company.py", "tools_workspace.py", "context.py",
                  "subagents.py", "compaction.py"]
_OPEN = re.compile(r"^\s*# \[stage:(\d+)\] (.+?)\s*$")
_CLOSE = re.compile(r"^\s*# \[/stage:(\d+)\]\s*$")


def _marked_blocks(path: Path) -> list[tuple[int, str, str]]:
    """(stage, title, dedented code) for every marked block in a file."""
    blocks, current = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        if current is None and (m := _OPEN.match(line)):
            current = (int(m.group(1)), m.group(2), [])
        elif current is not None and (m := _CLOSE.match(line)) and int(m.group(1)) == current[0]:
            blocks.append((current[0], current[1], textwrap.dedent("\n".join(current[2])).strip("\n")))
            current = None
        elif current is not None:
            current[2].append(line)
    return blocks


def stage_snippet(stage: int) -> list[dict]:
    """[{file, title, code}]: the real code for a stage's slide, cut from the package."""
    package = REPO_ROOT / "harness"
    rank = {name: i for i, name in enumerate(_SNIPPET_ORDER)}
    files = sorted(package.glob("*.py"), key=lambda p: (rank.get(p.name, len(rank)), p.name))
    return [{"file": f"harness/{p.name}", "title": title, "code": code}
            for p in files for n, title, code in _marked_blocks(p) if n == stage]
