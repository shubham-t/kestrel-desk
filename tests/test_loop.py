from __future__ import annotations

import asyncio
import json

import pytest
from conftest import collect

from harness import config
from harness.approvals import AutoApprove, AutoReject, FutureApprover
from harness.llm import FakeLLM, LLMError, ToolCall
from harness.loop import Agent
from harness.middleware import AuditLog, CallLimit, Compactor, RoleGate, ROLE_TOOLS
from harness.subagents import PROPOSAL_REVIEWER
from harness.tools import COMPANY_TOOLS, lookup_customer, send_proposal


def kinds(events) -> list[str]:
    return [e.kind for e in events]


def assert_in_order(events, expected: list[str]) -> None:
    """`expected` appears as a subsequence of the event kinds."""
    seq = iter(kinds(events))
    for kind in expected:
        assert any(k == kind for k in seq), f"{kind} missing or out of order in {kinds(events)}"


def history_is_well_formed(messages: list[dict]) -> bool:
    calls = [c["id"] for m in messages if m.get("tool_calls") for c in m["tool_calls"]]
    results = [m["tool_call_id"] for m in messages if m["role"] == "tool"]
    return sorted(calls) == sorted(results)


@pytest.mark.asyncio
async def test_tool_then_answer_event_order():
    llm = FakeLLM([[ToolCall("c1", "lookup_customer", {"name": "Acme Robotics"})], "Acme is on Growth."])
    agent = Agent(model=llm, tools=[lookup_customer])
    events = await collect(agent, "Who is Acme?")
    assert_in_order(events, ["run_start", "tool_call", "decision", "tool_result", "text_delta", "usage",
                             "text_done", "run_end"])
    decision = next(e for e in events if e.kind == "decision")
    assert decision.data["action"] == "allow" and decision.data["silent"] is True
    assert events[-1].data["model_calls"] == 2 and events[-1].data["tool_calls"] == 1
    assert events[-1].data["error"] is False
    assert "".join(e.data["text"] for e in events if e.kind == "text_delta") == "Acme is on Growth."
    # history shape: user, assistant(tool_calls), tool, assistant
    assert [m["role"] for m in agent.messages] == ["user", "assistant", "tool", "assistant"]
    assert agent.messages[1]["tool_calls"][0]["id"] == agent.messages[2]["tool_call_id"] == "c1"
    # the second model call saw the tool result
    assert llm.calls[1]["messages"][-1]["role"] == "tool"
    assert all(json.dumps(e.to_json()) for e in events)


@pytest.mark.asyncio
async def test_event_to_json_shape():
    agent = Agent(model=FakeLLM(["hi"]))
    events = await collect(agent, "hello")
    assert set(events[0].to_json()) == {"kind", "data", "component", "subagent", "ts"}
    assert agent.system_prompt == "You are a helpful assistant."
    assert len(agent.tools) == 0


@pytest.mark.asyncio
async def test_denied_call_is_blocked_and_explained():
    llm = FakeLLM([[ToolCall("c1", "send_proposal", {"customer_id": "cust_acme"})], "I can't send that."])
    agent = Agent(model=llm, tools=COMPANY_TOOLS, permissions=ROLE_TOOLS, role="engineering")
    events = await collect(agent, "send it")
    deny = next(e for e in events if e.kind == "decision")
    assert deny.data["action"] == "deny" and deny.component == "boundaries" and not deny.data["silent"]
    tool_msg = next(m for m in agent.messages if m["role"] == "tool")
    assert tool_msg["content"].startswith("Blocked by harness")
    assert "role=engineering" in agent.system_prompt


@pytest.mark.asyncio
async def test_rejected_approval(tmp_state):
    args = {"customer_id": "cust_acme", "to_email": "procurement@acme-robotics.example",
            "subject": "s", "body_markdown": "b"}
    llm = FakeLLM([[ToolCall("c1", "send_proposal", args)], "OK, not sent."])
    agent = Agent(model=llm, tools=[send_proposal], approve={"send_proposal"}, audit=True,
                  approvals=AutoReject())
    events = await collect(agent, "send it")
    assert_in_order(events, ["approval_request", "approval_result", "tool_result", "audit"])
    result = next(e for e in events if e.kind == "approval_result")
    assert result.data["approved"] is False
    assert agent.messages[2]["content"] == "User rejected the action."
    assert not config.OUTBOX_DIR.exists()
    audit = json.loads(config.AUDIT_LOG.read_text(encoding="utf-8").splitlines()[-1])
    assert audit["decision"] == "rejected"


@pytest.mark.asyncio
async def test_approved_call_runs(tmp_state):
    args = {"customer_id": "cust_acme", "to_email": "procurement@acme-robotics.example",
            "subject": "s", "body_markdown": "b"}
    agent = Agent(model=FakeLLM([[ToolCall("c1", "send_proposal", args)], "Queued."]),
                  tools=[send_proposal], approve={"send_proposal"}, approvals=AutoApprove())
    events = await collect(agent, "send it")
    result = next(e for e in events if e.kind == "tool_result")
    assert result.data["ok"] and result.data["outcome"] == "approved"
    assert len(list(config.OUTBOX_DIR.iterdir())) == 1


@pytest.mark.asyncio
async def test_future_approver_resolves():
    approver = FutureApprover(timeout=5)
    args = {"customer_id": "cust_acme", "to_email": "ceo@acme-robotics.example", "subject": "s",
            "body_markdown": "b"}
    agent = Agent(model=FakeLLM([[ToolCall("c1", "send_proposal", args)], "Done."]), tools=[send_proposal],
                  approve={"send_proposal"}, approvals=approver)
    events = []
    async for event in agent.run("send"):
        events.append(event)
        if event.kind == "approval_request":
            assert approver.resolve(event.data["request_id"], True)
    result = next(e for e in events if e.kind == "tool_result")
    assert result.data["ok"] is False and "Unverified address" in result.data["preview"]


@pytest.mark.asyncio
async def test_exhausted_llm_emits_error_then_run_end():
    agent = Agent(model=FakeLLM([[ToolCall("c1", "lookup_customer", {"name": "Acme"})]]),
                  tools=[lookup_customer])
    events = await collect(agent, "hi")
    assert kinds(events)[-2:] == ["error", "run_end"]
    assert events[-1].data["error"] is True
    assert history_is_well_formed(agent.messages)


@pytest.mark.asyncio
async def test_llm_error_mid_tool_batch_closes_dangling_calls():
    async def boom(args, ctx):
        raise LLMError("endpoint down", 503)

    from harness.tooling import Tool
    flaky = Tool("flaky", "fails", {"type": "object", "properties": {}, "required": []}, boom)
    calls = [ToolCall("a", "flaky", {}), ToolCall("b", "lookup_customer", {"name": "Acme"})]
    agent = Agent(model=FakeLLM([calls, LLMError("down", 500)]), tools=[flaky, lookup_customer])
    events = await collect(agent, "go")
    assert "error" in kinds(events)
    assert history_is_well_formed(agent.messages)


@pytest.mark.asyncio
async def test_unknown_tool_and_bad_json_are_reported_to_model():
    bad = ToolCall("c2", "lookup_customer", {}, raw_arguments="{not json")
    agent = Agent(model=FakeLLM([[ToolCall("c1", "nope", {}), bad], "ok"]), tools=[lookup_customer])
    await collect(agent, "go")
    tool_msgs = [m["content"] for m in agent.messages if m["role"] == "tool"]
    assert tool_msgs[0].startswith("Tool error: unknown tool 'nope'")
    assert "not valid JSON" in tool_msgs[1]


@pytest.mark.asyncio
async def test_call_limit_stops_runaway_loop():
    looping = [[ToolCall(f"c{i}", "lookup_customer", {"name": "Acme"})] for i in range(10)]
    agent = Agent(model=FakeLLM(looping), tools=[lookup_customer], middleware=[CallLimit(3, 20)])
    events = await collect(agent, "loop forever")
    end = events[-1]
    assert end.kind == "run_end" and end.data["stopped"] and end.data["model_calls"] == 3
    assert any(e.kind == "decision" and "Model call limit" in e.data["reason"] for e in events)
    assert history_is_well_formed(agent.messages) and agent.messages[-1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_subagent_events_are_nested():
    review_task = {"name": "proposal-reviewer", "task": "Review this draft for Acme Robotics"}
    llm = FakeLLM([
        [ToolCall("p1", "run_subagent", review_task)],                       # parent delegates
        [ToolCall("s1", "lookup_customer", {"name": "Acme Robotics"})],      # child looks up
        "Supported: 40 seats. Unsupported: discount.",                       # child answers
        "Reviewed. Here is the draft.",                                       # parent answers
    ])
    agent = Agent(model=llm, tools=[lookup_customer], subagents=[PROPOSAL_REVIEWER])
    events = await collect(agent, "draft and review")
    nested = [e for e in events if e.subagent == "proposal-reviewer"]
    assert any(e.kind == "tool_call" and e.data["name"] == "lookup_customer" for e in nested)
    assert_in_order(events, ["subagent_start", "subagent_end", "text_done", "run_end"])
    tool_msg = next(m for m in agent.messages if m["role"] == "tool")
    assert tool_msg["content"].startswith("Supported: 40 seats")
    assert len(agent.messages) == 4  # the child's work stays out of the parent's history
    assert llm.calls[1]["messages"][0]["content"].startswith(PROPOSAL_REVIEWER.system_prompt)


@pytest.mark.asyncio
async def test_compaction_inside_run(tmp_state):
    # Turn 3 crosses the threshold: the summary call comes before the model's answer "a3".
    llm = FakeLLM(["a1", "a2", "- summary of q1 and q2", "a3"], prompt_tokens=10_000)
    agent = Agent(model=llm, compaction=Compactor(at_tokens=5000, keep_last=2))
    for q in ("q1", "q2"):
        await collect(agent, q)
    events = await collect(agent, "q3")
    compaction = next(e for e in events if e.kind == "compaction")
    assert compaction.component == "persistence" and compaction.data["before"] == 5
    assert agent.messages[0]["content"] == "[Conversation summary]\n- summary of q1 and q2"
    assert [m["content"] for m in agent.messages[1:]] == ["a2", "q3", "a3"]
    assert "Earlier turns may appear" in agent.system_prompt


@pytest.mark.asyncio
async def test_role_gate_wired_by_permissions_keyword():
    agent = Agent(model=FakeLLM([]), tools=COMPANY_TOOLS, permissions=ROLE_TOOLS, audit=True)
    assert [type(m).__name__ for m in agent.middlewares] == ["RoleGate", "AuditLog"]
    assert isinstance(agent.middlewares[0], RoleGate) and isinstance(agent.middlewares[1], AuditLog)


@pytest.mark.asyncio
async def test_cancelling_a_run_leaves_history_valid():
    gate = asyncio.Event()

    async def slow(args, ctx):
        await gate.wait()
        return "never"

    from harness.tooling import Tool
    slow_tool = Tool("slow", "waits", {"type": "object", "properties": {}, "required": []}, slow)
    agent = Agent(model=FakeLLM([[ToolCall("c1", "slow", {})]]), tools=[slow_tool])
    stream = agent.run("go")
    async for event in stream:
        if event.kind == "tool_call":
            break
    await stream.aclose()
    assert history_is_well_formed(agent.messages)
