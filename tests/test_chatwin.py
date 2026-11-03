"""The plain chat window server (chatwin/), offline: FakeLLM, temp state, fastapi TestClient."""
from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from chatwin import server
from chatwin.fake import NotebookFakeLLM
from harness import config
from harness.llm import FakeLLM, ToolCall, fake_call
from harness.stages import build_agent


def builder_for(stage: int, make_llm):
    def build(role="sales", session_id=None, approvals=None):
        return build_agent(stage, role, session_id=session_id, approvals=approvals, llm=make_llm())
    return build


@pytest.fixture
def client(tmp_state):
    server.CHATS.clear()
    with TestClient(server.app) as c:
        yield c
    server.CHATS.clear()


def events_until_end(client, key) -> list[dict]:
    r = client.get(f"/api/events/{key}", params={"until_end": 1})
    assert r.status_code == 200
    return [json.loads(line[6:]) for line in r.text.splitlines() if line.startswith("data: ")]


def open_chat(client, role="sales", resume=None) -> dict:
    r = client.post("/api/session", json={"role": role, "resume": resume})
    assert r.status_code == 200, r.text
    return r.json()


def test_state_follows_set_builder(client):
    server.set_builder(builder_for(2, lambda: FakeLLM([])), 2, mock=True)
    first = client.get("/api/state").json()
    assert (first["stage"], first["stage_name"], first["mock"]) == (2, "Actions", True)
    server.set_builder(builder_for(3, lambda: FakeLLM([])), 3, mock=False)
    second = client.get("/api/state").json()
    assert second["stage"] == 3 and second["version"] == first["version"] + 1 and second["model"]
    assert client.get("/").status_code == 200
    assert client.get("/static/chat.js").status_code == 200


def test_send_streams_events_to_run_end(client):
    lookup = ToolCall(id="call_1", name="lookup_customer", arguments={"name": "Acme Robotics"})
    script = lambda: FakeLLM([[lookup], "Acme renews in March."])  # noqa: E731
    server.set_builder(builder_for(2, script), 2)
    chat = open_chat(client)
    assert chat["stage"] == 2 and chat["history"] == []
    assert client.post("/api/send", json={"key": chat["key"], "text": "Who is Acme?"}).json() == {"ok": True}
    events = events_until_end(client, chat["key"])
    kinds = [e["kind"] for e in events]
    assert kinds[0] == "run_start" and kinds[-1] == "run_end"
    call = next(e for e in events if e["kind"] == "tool_call")
    assert call["data"]["name"] == "lookup_customer"
    assert next(e for e in events if e["kind"] == "tool_result")["data"]["ok"] is True
    assert next(e for e in events if e["kind"] == "text_done")["data"]["text"] == "Acme renews in March."


def test_role_denial_reaches_the_window(client):
    script = lambda: FakeLLM([[fake_call("get_revenue", period="FY2026")], "Not allowed."])  # noqa: E731
    server.set_builder(builder_for(3, script), 3)
    chat = open_chat(client, role="engineering")
    client.post("/api/send", json={"key": chat["key"], "text": "What was our revenue in FY2026?"})
    result = next(e for e in events_until_end(client, chat["key"]) if e["kind"] == "tool_result")
    assert result["data"]["outcome"] == "deny" and "not allowed" in result["data"]["preview"]


@pytest.mark.parametrize("approved", [True, False])
def test_approval_round_trip(client, approved):
    send = fake_call("send_proposal", customer_id="cust_acme", to_email="procurement@acme-robotics.example",
                     subject="Kestrel renewal proposal", body_markdown="# Renewal")
    server.set_builder(builder_for(3, lambda: FakeLLM([[send], "Done."])), 3)
    chat = open_chat(client)
    client.post("/api/send", json={"key": chat["key"], "text": "Send it"})
    deadline = time.time() + 10
    while not server.DESK.approver.pending and time.time() < deadline:
        time.sleep(0.02)  # the run is paused on the approval card
    (request_id,) = list(server.DESK.approver.pending)
    assert client.post("/api/approve", json={"request_id": request_id, "approved": approved}).json() == {"ok": True}
    events = events_until_end(client, chat["key"])
    asked = next(e for e in events if e["kind"] == "approval_request")
    assert asked["data"]["request_id"] == request_id and asked["data"]["tool"] == "send_proposal"
    assert next(e for e in events if e["kind"] == "approval_result")["data"]["approved"] is approved
    result = next(e for e in events if e["kind"] == "tool_result")
    assert result["data"]["ok"] is approved
    outbox = list(config.OUTBOX_DIR.glob("*.md")) if config.OUTBOX_DIR.exists() else []
    assert len(outbox) == (1 if approved else 0)
    assert client.post("/api/approve", json={"request_id": request_id, "approved": True}).json() == {"ok": False}


def test_stop_ends_the_run(client):
    send = fake_call("send_proposal", customer_id="cust_acme", to_email="procurement@acme-robotics.example",
                     subject="s", body_markdown="b")
    server.set_builder(builder_for(3, lambda: FakeLLM([[send], "Done."])), 3)
    chat = open_chat(client)
    client.post("/api/send", json={"key": chat["key"], "text": "Send it"})
    deadline = time.time() + 10
    while not server.DESK.approver.pending and time.time() < deadline:
        time.sleep(0.02)
    assert client.post(f"/api/stop/{chat['key']}").json() == {"stopped": True}
    end = events_until_end(client, chat["key"])[-1]
    assert end["kind"] == "run_end" and end["data"]["stopped"] is True


def test_stage4_sessions_resume_and_compact(client):
    server.set_builder(builder_for(4, NotebookFakeLLM), 4, mock=True)
    chat = open_chat(client)
    for text in ("Check Acme Robotics' record", "Check their record again", "And the record once more"):
        client.post("/api/send", json={"key": chat["key"], "text": text})
        assert events_until_end(client, chat["key"])[-1]["kind"] == "run_end"

    rows = client.get("/api/sessions").json()
    assert [r["session_id"] for r in rows] == [chat["session_id"]]
    assert rows[0]["message_count"] == 12 and rows[0]["role"] == "sales"
    assert rows[0]["title"].startswith("Check Acme Robotics")

    resumed = open_chat(client, resume=chat["session_id"])
    assert resumed["resumed"] is True and len(resumed["history"]) == 12

    r = client.post(f"/api/compact/{resumed['key']}").json()
    assert r["compacted"] is True and r["after"] < r["before"] == 12
    queue = server.CHATS[resumed["key"]].queue
    kinds = [queue.get_nowait()["kind"] for _ in range(queue.qsize())]
    assert "compaction" in kinds
    assert client.get("/api/sessions").json()[0]["message_count"] == r["after"]


def test_sessions_empty_below_stage_4(client):
    server.set_builder(builder_for(3, lambda: FakeLLM([])), 3)
    assert client.get("/api/sessions").json() == []
    assert client.post("/api/session", json={"role": "nobody"}).status_code == 400
