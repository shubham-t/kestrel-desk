from __future__ import annotations

import re

import pytest
from conftest import collect

from harness.config import ROLES, STAGES
from harness.context import build_system_prompt, discover_skills
from harness.llm import FakeLLM, ToolCall
from harness.persistence import SessionStore
from harness.stages import build_agent, describe_stage, scenarios, stage_snippet

ALL_STAGES = range(len(STAGES))


def make(stage: int, role: str, script=()):
    return build_agent(stage, role, llm=FakeLLM(list(script)), store=SessionStore() if stage == 4 else None)


@pytest.mark.parametrize("stage", ALL_STAGES)
@pytest.mark.parametrize("role", ROLES)
def test_every_stage_and_role_builds(tmp_state, stage, role):
    agent = make(stage, role)
    assert agent.system_prompt == build_system_prompt(stage, role, discover_skills())
    info = describe_stage(stage)
    assert [type(m).__name__ for m in agent.middlewares] == info["middlewares"]


def test_stage0_has_no_tools(tmp_state):
    assert len(make(0, "sales").tools) == 0


def test_stage1_is_stage0_plus_a_system_prompt(tmp_state):
    """Stage 1 adds only context: no tools, no loop, no skills index, no middleware."""
    s0, s1 = make(0, "sales"), make(1, "sales")
    assert len(s1.tools) == 0 and s1.middlewares == [] == s0.middlewares
    assert "Kestrel" in s1.system_prompt and s1.system_prompt != s0.system_prompt
    assert "Available skills (load with load_skill)" not in s1.system_prompt
    assert "load_skill" not in s1.system_prompt and "- proposal-writing:" not in s1.system_prompt
    assert "Acme" not in s1.system_prompt  # it still has to be told who Acme is


@pytest.mark.asyncio
async def test_stage1_request_matches_stage0_except_the_system_prompt(tmp_state):
    calls = []
    for stage in (0, 1):
        llm = FakeLLM(["hi"])
        await collect(build_agent(stage, "sales", llm=llm), "Who is Acme Robotics?")
        calls.append(llm.calls)
    (c0,), (c1,) = calls
    assert c0["messages"][1:] == c1["messages"][1:]
    assert c0["messages"][0]["role"] == c1["messages"][0]["role"] == "system"
    assert not c0["tools"] and not c1["tools"]


def test_stage2_adds_tools_skills_and_subagent(tmp_state):
    agent = make(2, "sales")
    names = set(agent.tools.names())
    assert {"load_skill", "list_customers", "lookup_customer", "lookup_issue", "get_revenue",
            "send_proposal", "run_subagent"} == names
    assert "Available skills (load with load_skill)" in agent.system_prompt
    assert "- proposal-writing:" in agent.system_prompt
    assert [type(m).__name__ for m in agent.middlewares] == ["CallLimit"]


def test_stage3_middleware_chain(tmp_state):
    assert [type(m).__name__ for m in make(3, "sales").middlewares] == [
        "RoleGate", "ApprovalGate", "CallLimit", "AuditLog"]


def test_stage4_scenarios_include_resume_and_compact():
    scs = scenarios(4)
    assert [sc.resume for sc in scs].count(True) == 1
    assert [sc.prompt for sc in scs].count("") == 1
    assert all(not sc.resume for s in range(4) for sc in scenarios(s))


def test_tools_unlock_cumulatively(tmp_state):
    seen: set[str] = set()
    for stage in ALL_STAGES:
        names = set(make(stage, "sales").tools.names())
        assert names - seen == set(describe_stage(stage)["unlocked_tools"]), stage
        assert seen <= names
        seen = names


@pytest.mark.asyncio
async def test_stage3_send_proposal_registered_but_blocked_for_engineering(tmp_state):
    args = {"customer_id": "cust_acme", "to_email": "procurement@acme-robotics.example", "subject": "s",
            "body_markdown": "b"}
    agent = make(3, "engineering", [[ToolCall("c1", "send_proposal", args)], "I can't send proposals."])
    assert "send_proposal" in agent.tools
    events = await collect(agent, "send it")
    deny = next(e for e in events if e.kind == "decision")
    assert deny.data["action"] == "deny" and "Role 'engineering'" in deny.data["reason"]


@pytest.mark.parametrize("stage", ALL_STAGES)
def test_snippets(stage):
    snippets = stage_snippet(stage)
    assert 1 <= len(snippets) <= 3
    first = snippets[0]
    assert first["file"] == "harness/stages.py" and "Agent(" in first["code"]
    assert len(first["code"].splitlines()) <= 8
    for s in snippets:
        assert set(s) == {"file", "title", "code"} and s["title"]
        assert 0 < len(s["code"].splitlines()) <= 20
        assert "# [stage:" not in s["code"] and "# [/stage:" not in s["code"]
        assert s["code"] == s["code"].lstrip()  # dedented


@pytest.mark.parametrize("stage", ALL_STAGES)
def test_new_keywords_appear_in_snippet(stage):
    code = stage_snippet(stage)[0]["code"]
    for kw in describe_stage(stage)["new_keywords"]:
        assert f"{kw}=" in code


@pytest.mark.parametrize("stage", ALL_STAGES)
def test_scenarios_and_description(stage):
    assert scenarios(stage)
    for sc in scenarios(stage):
        assert sc.role in ROLES and sc.title and sc.watch
        assert sc.prompt or stage == 4  # only the "Long day" button has no prompt
    info = describe_stage(stage)
    assert set(info) == {"id", "name", "component", "tagline", "headline", "problem", "bullets",
                         "unlocked_tools", "middlewares", "subagents", "new_keywords"}
    assert 3 <= len(info["bullets"]) <= 4 and info["id"] == stage


@pytest.mark.parametrize("stage", ALL_STAGES)
def test_headline_and_problem(stage):
    info = describe_stage(stage)
    headline, problem = info["headline"], info["problem"]
    assert 1 <= len(headline.split()) <= 6 and headline[-1].isalnum()  # the UI adds the full stop
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", problem.strip()) if s]
    assert 2 <= len(sentences) <= 3 and problem.strip()[-1] in ".!?"


@pytest.mark.parametrize("stage", ALL_STAGES)
def test_subagents_match_the_agent(tmp_state, stage):
    agent = make(stage, "sales")
    assert bool(describe_stage(stage)["subagents"]) == ("run_subagent" in agent.tools)
    if "run_subagent" in agent.tools:
        for name in describe_stage(stage)["subagents"]:
            assert name in agent.tools.get("run_subagent").description


def test_build_agent_rejects_bad_input():
    with pytest.raises(ValueError):
        build_agent(9, "sales", llm=FakeLLM([]))
    with pytest.raises(ValueError):
        build_agent(1, "ceo", llm=FakeLLM([]))
