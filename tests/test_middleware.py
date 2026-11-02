from __future__ import annotations

import json

import pytest

from harness import config
from harness.llm import FakeLLM, ToolCall, Usage
from harness.middleware import (ApprovalGate, AuditLog, CallLimit, Compactor, ProtectedPaths, RoleGate,
                                TodoTracker)
from harness.tools import (get_revenue, lookup_customer, lookup_issue, read_workspace_file, send_proposal,
                           update_todos, write_workspace_file)


def call(name: str, **args) -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=args)


@pytest.mark.asyncio
@pytest.mark.parametrize("role,tool,expected", [
    ("sales", send_proposal, "allow"), ("sales", get_revenue, "deny"), ("sales", lookup_issue, "deny"),
    ("engineering", lookup_issue, "allow"), ("engineering", get_revenue, "deny"),
    ("engineering", send_proposal, "deny"), ("finance", get_revenue, "allow"),
    ("finance", send_proposal, "deny"), ("finance", lookup_customer, "allow"),
])
async def test_role_gate(ctx, role, tool, expected):
    ctx.role = role
    decision = await RoleGate().before_tool(call(tool.name), tool, ctx)
    assert decision.action == expected
    if expected == "deny":
        assert decision.reason.startswith(f"Role '{role}' is not allowed to use {tool.name}")


@pytest.mark.asyncio
async def test_role_gate_ignores_non_company_tools(ctx):
    ctx.role = "engineering"
    assert (await RoleGate().before_tool(call("update_todos"), update_todos, ctx)).action == "allow"


@pytest.mark.asyncio
@pytest.mark.parametrize("path,expected", [
    ("acme-proposal.md", "allow"), ("workspace/acme-proposal.md", "allow"),
    ("company/AGENTS.md", "deny"), ("../company/AGENTS.md", "deny"), ("skills/x/SKILL.md", "deny"),
    ("harness/loop.py", "deny"), ("../outside.md", "deny"),
])
async def test_protected_paths(ctx, tmp_state, path, expected):
    decision = await ProtectedPaths().before_tool(call("write_workspace_file", path=path, content="x"),
                                                  write_workspace_file, ctx)
    assert decision.action == expected, decision.reason


@pytest.mark.asyncio
async def test_protected_paths_skips_read_only_tools(ctx, tmp_state):
    decision = await ProtectedPaths().before_tool(call("read_workspace_file", path="../x"),
                                                  read_workspace_file, ctx)
    assert decision.action == "allow"


@pytest.mark.asyncio
async def test_call_limit(ctx):
    limit = CallLimit(max_model_calls=2, max_tool_calls=2)
    ctx.state["calls"] = {"model": 0, "tool": 2}
    assert (await limit.before_tool(call("lookup_customer"), lookup_customer, ctx)).action == "allow"
    ctx.state["calls"]["tool"] = 3
    denied = await limit.before_tool(call("lookup_customer"), lookup_customer, ctx)
    assert denied.action == "deny" and "Tool call limit reached (2" in denied.reason
    ctx.state["calls"]["model"] = 2
    from harness.middleware import StopRun
    with pytest.raises(StopRun, match="Model call limit reached"):
        await limit.before_model([], ctx)


@pytest.mark.asyncio
async def test_approval_gate_asks_for_flagged_tools(ctx):
    gate = ApprovalGate()
    assert (await gate.before_tool(call("send_proposal"), send_proposal, ctx)).action == "ask"
    assert (await gate.before_tool(call("lookup_customer"), lookup_customer, ctx)).action == "allow"
    named = ApprovalGate({"lookup_customer"})
    assert (await named.before_tool(call("lookup_customer"), lookup_customer, ctx)).action == "ask"


@pytest.mark.asyncio
async def test_todo_tracker_installs_tool_and_emits(ctx):
    tracker = TodoTracker()
    assert [t.name for t in tracker.tools()] == ["update_todos"]
    items = [{"text": "a", "status": "pending"}]
    await update_todos.handler({"items": items}, ctx)
    await tracker.after_tool(call("update_todos", items=items), update_todos, "ok (1 items)", True, ctx)
    assert ctx.state["todos"] == items
    assert ctx.events[-1].kind == "todo_update" and ctx.events[-1].data["items"] == items


@pytest.mark.asyncio
async def test_audit_log_appends_line(ctx, tmp_state):
    ctx.state["last_decision"] = "deny"
    await AuditLog().after_tool(call("get_revenue", period="FY2026"), get_revenue, "Blocked", False, ctx)
    line = json.loads(config.AUDIT_LOG.read_text(encoding="utf-8").splitlines()[-1])
    assert line["tool"] == "get_revenue" and line["decision"] == "deny" and line["ok"] is False
    assert ctx.events[-1].kind == "audit"


def _history(n_turns: int) -> list[dict]:
    """system + n turns of user / assistant(tool_call) / tool / assistant."""
    msgs = [{"role": "system", "content": "sys"}]
    for i in range(n_turns):
        msgs += [{"role": "user", "content": f"q{i}"},
                 {"role": "assistant", "content": None, "tool_calls": [
                     {"id": f"t{i}", "type": "function",
                      "function": {"name": "lookup_customer", "arguments": "{}"}}]},
                 {"role": "tool", "tool_call_id": f"t{i}", "content": f"r{i}"},
                 {"role": "assistant", "content": f"a{i}"}]
    return msgs


@pytest.mark.asyncio
async def test_compactor_replaces_middle_keeps_tail(ctx):
    llm = FakeLLM(["- Acme wants 40 Enterprise seats"])
    compactor = Compactor(llm, at_tokens=100, keep_last=4)
    messages = _history(4)  # 17 messages
    await compactor.after_model({}, Usage(prompt_tokens=500, completion_tokens=1), ctx)
    out = await compactor.before_model(messages, ctx)
    assert out[0] == messages[0]
    assert out[1]["role"] == "user" and out[1]["content"].startswith("[Conversation summary]\n- Acme")
    assert out[2:] == messages[-4:]
    assert ctx.state["history_rewritten"] is True
    assert ctx.events[-1].kind == "compaction" and ctx.events[-1].data["after"] == 5
    assert llm.calls[0]["tools"] == []  # the summary call is plain text, no tools


@pytest.mark.asyncio
async def test_compactor_never_orphans_tool_results(ctx):
    compactor = Compactor(FakeLLM(["summary"]), at_tokens=0, keep_last=6)
    messages = _history(4)  # with keep_last=6 the naive cut lands on a tool message
    assert messages[len(messages) - 6]["role"] == "tool"
    ctx.state["last_prompt_tokens"] = 10
    out = await compactor.before_model(messages, ctx)
    tail = out[2:]
    assert tail[0]["role"] == "assistant" and tail[0]["tool_calls"]
    call_ids = {c["id"] for m in out if m.get("tool_calls") for c in m["tool_calls"]}
    result_ids = {m["tool_call_id"] for m in out if m["role"] == "tool"}
    assert call_ids == result_ids


@pytest.mark.asyncio
async def test_compactor_waits_for_threshold(ctx):
    compactor = Compactor(FakeLLM([]), at_tokens=1000, keep_last=4)
    messages = _history(4)
    ctx.state["last_prompt_tokens"] = 999
    assert await compactor.before_model(messages, ctx) is messages
