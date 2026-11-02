from __future__ import annotations

import json

import pytest

from harness import config
from harness.context import discover_skills, make_load_skill_tool
from harness.tools import (ToolError, get_revenue, list_customers, list_workspace_files, lookup_customer,
                           lookup_issue,
                           read_workspace_file, send_proposal, tool, update_todos, write_workspace_file)


def test_tool_decorator_infers_schema():
    @tool(component="actions")
    async def demo(name: str, count: int, tags: list[str], flag: bool = False, ctx=None) -> str:
        """Do a demo thing.

        Args:
            name: who to greet
        """
        return name

    assert demo.name == "demo"
    assert demo.description == "Do a demo thing."
    props = demo.parameters["properties"]
    assert props["name"] == {"type": "string", "description": "who to greet"}
    assert props["count"] == {"type": "integer"}
    assert props["tags"] == {"type": "array", "items": {"type": "string"}}
    assert props["flag"] == {"type": "boolean"}
    assert "ctx" not in props
    assert demo.parameters["required"] == ["name", "count", "tags"]


def test_company_tool_schemas_hide_ctx():
    assert send_proposal.parameters["required"] == ["customer_id", "to_email", "subject", "body_markdown"]
    assert send_proposal.requires_approval and not send_proposal.read_only
    assert lookup_customer.read_only and lookup_customer.component == "actions"


@pytest.mark.asyncio
async def test_list_customers_is_short(ctx):
    lines = (await list_customers.handler({}, ctx)).splitlines()
    assert len(lines) == 7 and lines[0] == "cust_acme: Acme Robotics (Growth)"
    assert list_customers.read_only and list_customers.component == "actions"


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["acme", "Acme Robotics", "cust_acme", "CUST_ACME"])
async def test_lookup_customer_by_name_or_id(ctx, query):
    record = json.loads(await lookup_customer.handler({"name": query}, ctx))
    assert record["id"] == "cust_acme"
    assert record["contact_email"] == "procurement@acme-robotics.example"


@pytest.mark.asyncio
async def test_lookup_customer_never_dumps_every_record(ctx):
    """A broad query returns a pick-list of ids and names, not full records."""
    text = await lookup_customer.handler({"name": "cust"}, ctx)
    assert "be more specific" in text and "cust_acme: Acme Robotics" in text
    assert "contact_email" not in text and "arr_usd" not in text
    with pytest.raises(ToolError, match="at least 2"):
        await lookup_customer.handler({"name": "a"}, ctx)
    with pytest.raises(ToolError, match="list_customers"):
        await lookup_customer.handler({"name": "Globex"}, ctx)


@pytest.mark.asyncio
async def test_lookup_issue_by_id_customer_and_title(ctx):
    by_id = json.loads(await lookup_issue.handler({"query": "ISS-1043"}, ctx))
    assert [i["id"] for i in by_id] == ["ISS-1043"]
    for q in ("northwind", "cust_northwind", "Northwind Freight"):
        by_customer = json.loads(await lookup_issue.handler({"query": q}, ctx))
        assert {i["id"] for i in by_customer} == {"ISS-1041", "ISS-1042"}, q
    by_title = json.loads(await lookup_issue.handler({"query": "audit log export"}, ctx))
    assert [i["id"] for i in by_title] == ["ISS-1043"]
    with pytest.raises(ToolError):
        await lookup_issue.handler({"query": "  "}, ctx)
    with pytest.raises(ToolError):  # no "list everything" shortcut
        await lookup_issue.handler({"query": "open"}, ctx)


@pytest.mark.asyncio
async def test_get_revenue_slices(ctx):
    fy = json.loads(await get_revenue.handler({"period": "FY2026"}, ctx))
    assert [r["id"] for r in fy["records"]] == [f"rev-FY2026-Q{i}" for i in range(1, 5)]
    assert fy["source"]
    q2 = json.loads(await get_revenue.handler({"period": "fy2026-q2"}, ctx))
    assert len(q2["records"]) == 1
    arr = json.loads(await get_revenue.handler({"period": "ARR"}, ctx))
    assert arr["records"]["id"].startswith("arr-")
    with pytest.raises(ToolError):
        await get_revenue.handler({"period": "FY1999"}, ctx)


@pytest.mark.asyncio
async def test_send_proposal_rejects_unverified_address(ctx, tmp_state):
    args = {"customer_id": "cust_acme", "to_email": "ceo@acme-robotics.example", "subject": "s",
            "body_markdown": "b"}
    with pytest.raises(ToolError, match="Unverified address"):
        await send_proposal.handler(args, ctx)
    assert not config.OUTBOX_DIR.exists() or not any(config.OUTBOX_DIR.iterdir())


@pytest.mark.asyncio
async def test_send_proposal_writes_outbox(ctx, tmp_state):
    args = {"customer_id": "cust_acme", "to_email": "procurement@acme-robotics.example",
            "subject": "Kestrel Enterprise proposal", "body_markdown": "# Proposal"}
    result = await send_proposal.handler(args, ctx)
    assert result.startswith("Queued to outbox: ")
    files = list(config.OUTBOX_DIR.iterdir())
    assert len(files) == 1 and files[0].name.endswith("_cust_acme.md")
    text = files[0].read_text(encoding="utf-8")
    assert "To: procurement@acme-robotics.example" in text and "# Proposal" in text


@pytest.mark.asyncio
async def test_workspace_round_trip(ctx, tmp_state):
    saved = await write_workspace_file.handler({"path": "workspace/notes/acme.md", "content": "hi"}, ctx)
    assert "workspace/notes/acme.md" in saved
    assert (config.WORKSPACE_DIR / "notes" / "acme.md").read_text(encoding="utf-8") == "hi"
    assert await read_workspace_file.handler({"path": "notes/acme.md"}, ctx) == "hi"
    assert "workspace/notes/acme.md" in await list_workspace_files.handler({}, ctx)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["../escape.md", "../../etc/passwd", "notes/../../x.md"])
async def test_workspace_path_escape_blocked(ctx, tmp_state, bad):
    with pytest.raises(ToolError, match="outside workspace"):
        await write_workspace_file.handler({"path": bad, "content": "x"}, ctx)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["company/AGENTS.md", "../company/AGENTS.md", "skills/x/SKILL.md",
                                 "harness/loop.py"])
async def test_workspace_refuses_company_and_code_paths(ctx, tmp_state, bad):
    """The stage-4 'Save the draft' scenario: the AGENTS.md write is refused by the tool itself.
    A repo path is never quietly redirected into a look-alike copy under workspace/."""
    with pytest.raises(ToolError, match="outside workspace"):
        await write_workspace_file.handler({"path": bad, "content": "x"}, ctx)
    assert not (config.WORKSPACE_DIR / "company").exists()


@pytest.mark.asyncio
async def test_workspace_absolute_path_blocked(ctx, tmp_state):
    outside = str(tmp_state / "elsewhere.md")
    with pytest.raises(ToolError):
        await write_workspace_file.handler({"path": outside, "content": "x"}, ctx)


@pytest.mark.asyncio
async def test_load_skill(ctx):
    skills = discover_skills()
    assert {s.name for s in skills} == {"proposal-writing", "issue-triage", "revenue-brief"}
    load_skill = make_load_skill_tool(skills)
    assert "Required sections" in await load_skill.handler({"name": "proposal-writing"}, ctx)
    with pytest.raises(ToolError, match="Valid names"):
        await load_skill.handler({"name": "nope"}, ctx)


@pytest.mark.asyncio
async def test_update_todos_stores_state(ctx):
    items = [{"text": "look up Acme", "status": "done"}, {"text": "draft", "status": "in_progress"}]
    assert await update_todos.handler({"items": items}, ctx) == "ok (2 items)"
    assert ctx.state["todos"] == items


@pytest.mark.asyncio
async def test_missing_argument_is_a_tool_error(ctx):
    with pytest.raises(ToolError, match="Missing required"):
        await lookup_customer.handler({}, ctx)
