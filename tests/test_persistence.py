from __future__ import annotations

import pytest
from conftest import collect

from harness.llm import FakeLLM, ToolCall
from harness.persistence import SessionStore
from harness.stages import build_agent


def test_round_trip(tmp_state):
    store = SessionStore()
    store.create("s1", stage=4, role="sales")
    store.append("s1", {"role": "user", "content": "Draft a proposal for Acme Robotics please"})
    store.append("s1", {"role": "assistant", "content": "Done."})
    assert [m["content"] for m in store.load("s1")] == ["Draft a proposal for Acme Robotics please", "Done."]
    row = store.list_sessions()[0]
    assert row["session_id"] == "s1" and row["message_count"] == 2 and row["stage"] == 4
    assert row["title"] == "Draft a proposal for Acme Robotics please"
    assert store.exists("s1") and not store.exists("nope")


def test_replace_all_and_delete(tmp_state):
    store = SessionStore()
    store.create("s1", 4, "sales")
    for i in range(5):
        store.append("s1", {"role": "user", "content": str(i)})
    store.replace_all("s1", [{"role": "user", "content": "[Conversation summary]\nx"}])
    assert len(store.load("s1")) == 1
    store.append("s1", {"role": "assistant", "content": "y"})
    assert [m["content"] for m in store.load("s1")][-1] == "y"
    store.delete("s1")
    assert store.load("s1") == [] and store.list_sessions() == []


def test_list_sessions_newest_first(tmp_state):
    store = SessionStore()
    for sid in ("old", "mid", "new"):
        store.create(sid, 4, "sales")
    assert [s["session_id"] for s in store.list_sessions()] == ["new", "mid", "old"]


def test_title_truncated(tmp_state):
    store = SessionStore()
    store.create("s", 4, "sales")
    store.append("s", {"role": "user", "content": "x" * 100})
    store.set_title("s", "y" * 100)
    assert store.list_sessions()[0]["title"] == "y" * 60


@pytest.mark.asyncio
async def test_stage4_checkpoints_and_resumes(tmp_state):
    store = SessionStore()
    first = build_agent(4, "sales", llm=FakeLLM(
        [[ToolCall("c1", "write_workspace_file", {"path": "acme-proposal.md", "content": "# Acme"})],
         "Saved to workspace/acme-proposal.md"]), store=store)
    events = await collect(first, "Save the Acme proposal as workspace/acme-proposal.md")
    assert sum(e.kind == "checkpoint" for e in events) == 4  # user, assistant, tool, assistant
    assert not first.resumed

    later = build_agent(4, "sales", session_id=first.session_id, llm=FakeLLM(["We saved acme-proposal.md."]),
                        store=store)
    assert later.resumed and later.messages == first.messages
    await collect(later, "What did we save earlier?")
    assert len(store.load(first.session_id)) == 6


@pytest.mark.asyncio
async def test_stage4_blocks_write_to_company(tmp_state):
    agent = build_agent(4, "sales", llm=FakeLLM(
        [[ToolCall("c1", "write_workspace_file", {"path": "company/AGENTS.md", "content": "pwned"})],
         "That path is protected."]), store=SessionStore())
    events = await collect(agent, "overwrite AGENTS.md")
    deny = next(e for e in events if e.kind == "decision" and e.data["action"] == "deny")
    assert "protected path company/" in deny.data["reason"]
