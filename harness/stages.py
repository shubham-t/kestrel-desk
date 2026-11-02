"""The five stages. Each one is a single Agent(...) call: one keyword per harness component.

Read this file top to bottom during the talk. Stage N keeps everything stage N-1 had and
adds the keywords for one more component; everything else is plumbing.
"""
from __future__ import annotations

import uuid

from .approvals import ApprovalBroker
from .compaction import Compactor
from .config import COMPANY_DIR, ROLES, SKILLS_DIR, STAGES, WORKSPACE_DIR, settings
from .llm import LLM, make_llm
from .loop import Agent
from .middleware import ROLE_TOOLS, CallLimit
from .persistence import SessionStore
from .subagents import PROPOSAL_REVIEWER
from .talk import Scenario, describe_stage, scenarios, stage_snippet
from .tools import COMPANY_TOOLS

__all__ = ["build_agent", "Scenario", "describe_stage", "scenarios", "stage_snippet"]


def build_agent(stage: int, role: str, *, session_id: str | None = None,
                approvals: ApprovalBroker | None = None, llm: LLM | None = None,
                store: SessionStore | None = None) -> Agent:
    if stage not in range(len(STAGES)) or role not in ROLES:
        raise ValueError(f"stage must be 0-{len(STAGES) - 1} and role one of {ROLES}")
    llm = llm or make_llm()
    common = dict(role=role, stage=stage, session_id=session_id or uuid.uuid4().hex[:12],
                  approvals=approvals)
    if stage == 0:
        # [stage:0] A chatbot: a model and a prompt
        return Agent(model=llm, **common)
        # [/stage:0]
    if stage == 1:
        # [stage:1] Context: the company file, always on
        return Agent(model=llm, instructions=COMPANY_DIR / "AGENTS.md", **common)
        # [/stage:1]
    if stage == 2:
        # [stage:2] Actions: tools, a loop with middleware, skills on demand, a subagent
        return Agent(model=llm, instructions=COMPANY_DIR / "AGENTS.md",
                     tools=COMPANY_TOOLS, middleware=[CallLimit()],
                     skills=SKILLS_DIR, subagents=[PROPOSAL_REVIEWER], **common)
        # [/stage:2]
    if stage == 3:
        # [stage:3] Boundaries: roles, human approval, audit
        return Agent(model=llm, instructions=COMPANY_DIR / "AGENTS.md",
                     tools=COMPANY_TOOLS, middleware=[CallLimit()],
                     skills=SKILLS_DIR, subagents=[PROPOSAL_REVIEWER],
                     permissions=ROLE_TOOLS, approve={"send_proposal"}, audit=True, **common)
        # [/stage:3]
    # [stage:4] Persistence: checkpoints, a workspace, compaction
    return Agent(model=llm, instructions=COMPANY_DIR / "AGENTS.md",
                 tools=COMPANY_TOOLS, middleware=[CallLimit()],
                 skills=SKILLS_DIR, subagents=[PROPOSAL_REVIEWER],
                 permissions=ROLE_TOOLS, approve={"send_proposal"}, audit=True,
                 checkpointer=store or SessionStore(), workspace=WORKSPACE_DIR,
                 compaction=Compactor(at_tokens=settings.compact_at_tokens), **common)
    # [/stage:4]
