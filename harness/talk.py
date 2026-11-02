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
    prompt: str  # empty = a UI action instead of a prompt ("Long day" is the Compact now button)
    watch: str  # one sentence telling the audience what to look at
    resume: bool = False  # Run first resumes the most recent saved session of this stage, then sends


# One story runs through the talk: the Acme Robotics renewal. Each scenario needs only the
# component being introduced, and repeats an earlier prompt where a before/after helps.
_PRICE_THE_RENEWAL = ("Draft a renewal proposal for Acme Robotics: 40 seats on our Enterprise plan, "
                      "with pricing.")
_SHORT_PROPOSAL = ("Draft a short renewal proposal for Acme Robotics (40 seats, Enterprise, SSO and "
                   "audit logs)")
_REVENUE_QUESTION = "What was our revenue in FY2026?"

_SCENARIOS: dict[int, list[Scenario]] = {
    0: [Scenario("Who's Acme?", "sales", "Who is Acme Robotics and when is their renewal due?",
                 "It can't know. Nothing is around the model."),
        Scenario("Price the renewal", "sales", _PRICE_THE_RENEWAL,
                 "It invents a price, or asks for one. It has no idea what our plans cost.")],
    1: [Scenario("Price the renewal, again", "sales", _PRICE_THE_RENEWAL,
                 "Plan-table price ($2,400 per seat per year), our tone, our sections, no discount. "
                 "Tokens in jumped: AGENTS.md rides on every call. We still had to say who Acme is."),
        Scenario("Can I discount?", "sales", "Can I offer Acme 15% off to close this quarter?",
                 "\"No: above 10% needs written approval from finance\", straight from AGENTS.md. "
                 "A business rule, not a fact.")],
    2: [Scenario("Prepare the renewal", "sales",
                 "Prepare Acme Robotics' renewal proposal: check their record and open issues, then have "
                 "the proposal-reviewer check it before you show it to me.",
                 "load_skill pulls the playbook, lookup_customer and lookup_issue pull the facts, the "
                 "reviewer runs as a nested subagent. The model fetched what it needed."),
        Scenario("Account health, every customer", "engineering",
                 "Give me an account health report for every customer: their record plus their open issues.",
                 "A realistic over-sized request. CallLimit denies the 11th tool call; the model reports "
                 "partial results and says why.")],
    3: [Scenario("Wrong role", "engineering", _REVENUE_QUESTION,
                 "RoleGate denies get_revenue, in code, before it runs; the model says so instead of guessing."),
        Scenario("Right role", "finance", _REVENUE_QUESTION,
                 "Same question, allowed, answered with record ids."),
        Scenario("Send it", "sales",
                 f"{_SHORT_PROPOSAL} and send it to procurement@acme-robotics.example with the subject "
                 "\"Kestrel renewal proposal\".",
                 "The approval card appears and the loop waits. Approve → outbox file + audit line. "
                 "Variant: send to ceo@acme-robotics.example and the tool rejects the address as not on record.")],
    4: [Scenario("Save the draft", "sales",
                 f"{_SHORT_PROPOSAL}, save it as workspace/acme-renewal.md, and add a line to "
                 "company/AGENTS.md saying the Acme draft is done.",
                 "write_workspace_file writes the draft and checkpoints tick up; the AGENTS.md write is "
                 "refused by the tool (outside workspace/), and the model reports it."),
        Scenario("Pick up yesterday's work", "sales", "Where did we leave off with Acme, and what did we save?",
                 "Run resumes the most recent saved session from SQLite (the divider says so) and answers "
                 "from history. In the sidebar the session is highlighted.", resume=True),
        Scenario("Long day", "sales", "",
                 "9 → 7 messages, a compaction row with the summary.")],
}

# unlocked_tools: tools that first appear at this stage.
# middlewares / subagents: everything the stage's agent has installed, in chain order.
_S3_CHAIN = ["RoleGate", "ApprovalGate", "CallLimit", "AuditLog"]
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
        problem="The model knows nothing about Kestrel, so it invents our prices and our rules. "
                "AGENTS.md is the always-on company file: who we are, our plans and prices, and the "
                "business rules every answer must follow. It rides in the system prompt of every call; "
                "nothing else about the call changes.",
        bullets=["company/AGENTS.md becomes the system prompt",
                 "Facts: the company, plans and list prices",
                 "Rules: discounts, tone, what we never promise",
                 "Same single call as stage 0: no tools, no loop"],
        unlocked_tools=[], middlewares=[], subagents=[], new_keywords=["instructions"]),
    2: dict(
        headline="Let it look things up itself",
        problem="AGENTS.md can't hold every customer record or every playbook, so we still had to tell it "
                "who Acme is. Now the model has to fetch facts and know-how itself: tools for our records, "
                "skills it loads only when a task needs them, a reviewer for its draft. A loop that keeps "
                "calling tools also needs a brake.",
        bullets=["Five company tools declared with @tool, run in a loop",
                 "Skills listed by name; load_skill pulls one in on demand",
                 "CallLimit middleware: a budget on every run",
                 "A proposal-reviewer subagent with its own context"],
        unlocked_tools=["load_skill", "list_customers", "lookup_customer", "lookup_issue", "get_revenue", "send_proposal",
                        "run_subagent"],
        middlewares=["CallLimit"], subagents=["proposal-reviewer"],
        new_keywords=["tools", "middleware", "skills", "subagents"]),
    3: dict(
        headline="Draw the lines in code",
        problem="Now the agent can act, and it treats every user the same. An engineer can pull revenue, "
                "anyone can email a customer, and a prompt that says please don't is not a control. "
                "Permissions, approvals and an audit trail have to live in the harness, where the model "
                "can't talk its way past them.",
        bullets=["RoleGate: each role gets only its tools",
                 "send_proposal pauses for a human's approval",
                 "The tool itself rejects addresses not on record",
                 "Every tool call is written to an audit log"],
        unlocked_tools=[], middlewares=_S3_CHAIN, subagents=["proposal-reviewer"],
        new_keywords=["permissions", "approve", "audit"]),
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
