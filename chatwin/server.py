"""The plain chat window's server: FastAPI on 127.0.0.1:8777, one stage builder at a time.

A builder is any callable `builder(role=..., session_id=..., approvals=...) -> Agent`, such as
the notebook's `build_stage_N`. `set_builder()` swaps it without a restart; the browser picks
up the new stage on its next refresh (GET /api/state). Each chat runs `agent.run(text)` as an
asyncio task and forwards every `Event.to_json()` over SSE, like `app/server.py`.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from harness.approvals import FutureApprover
from harness.config import ROLES, STAGES, settings
from harness.persistence import SessionStore

STATIC_DIR = Path(__file__).resolve().parent / "static"
HOST, DEFAULT_PORT = "127.0.0.1", 8777
BOOT_ID = uuid.uuid4().hex[:8]


@dataclass
class Desk:
    """What the window is currently showing: one stage, served by one builder."""
    builder: Callable[..., Any] | None = None
    stage: int | None = None
    model: str = settings.model
    mock: bool = False
    version: int = 0  # bumps on every set_builder, so a page can tell it is stale
    approver: FutureApprover = field(default_factory=FutureApprover)


@dataclass
class Chat:
    key: str
    stage: int
    role: str
    agent: Any
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    task: asyncio.Task | None = None
    subscriber: int = 0


DESK = Desk()
CHATS: dict[str, Chat] = {}


def set_builder(builder: Callable[..., Any], stage: int, *, model: str | None = None,
                mock: bool | None = None) -> None:
    """Point the window at a new builder. Open chats keep their old agent until the page reloads."""
    from .fake import fake_enabled
    DESK.builder, DESK.stage = builder, int(stage)
    DESK.mock = fake_enabled() if mock is None else mock
    DESK.model = model or ("fake-model" if DESK.mock else settings.model)
    DESK.version += 1


app = FastAPI(title="Kestrel Desk chat window")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def _no_stale_static(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


def _note(kind: str, data: dict) -> dict:
    return {"kind": kind, "data": data, "component": None, "subagent": None, "ts": time.time()}


def _chat(key: str) -> Chat:
    chat = CHATS.get(key)
    if chat is None:
        raise HTTPException(404, f"Unknown chat {key!r}: reload the page.")
    return chat


async def _pump(chat: Chat, text: str) -> None:
    put, run = chat.queue.put_nowait, chat.agent.run(text)
    try:
        async for event in run:
            put(event.to_json())
    except asyncio.CancelledError:  # Stop: the loop closes dangling tool calls itself
        put(_note("run_end", {"session_id": chat.agent.session_id, "error": False, "stopped": True,
                              "by_user": True}))
    except Exception as exc:  # the loop turns its own errors into events; this is a last resort
        put(_note("error", {"message": f"{type(exc).__name__}: {exc}"}))
        put(_note("run_end", {"session_id": chat.agent.session_id, "error": True}))
    finally:
        chat.task = None
        try:
            await run.aclose()
        except Exception:
            pass


class SessionIn(BaseModel):
    role: str = "sales"
    resume: str | None = None


class SendIn(BaseModel):
    key: str
    text: str


class ApproveIn(BaseModel):
    request_id: str
    approved: bool


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/state")
async def state() -> dict:
    info = STAGES[DESK.stage] if DESK.stage is not None else None
    return {"stage": DESK.stage, "stage_name": info.name if info else None,
            "tagline": info.tagline if info else None, "role": "sales", "roles": list(ROLES),
            "model": DESK.model, "mock": DESK.mock, "version": DESK.version, "boot_id": BOOT_ID}


@app.post("/api/session")
async def create_session(body: SessionIn) -> dict:
    if DESK.builder is None:
        raise HTTPException(409, "Nothing served yet: run a serve(...) cell in the notebook.")
    if body.role not in ROLES:
        raise HTTPException(400, f"Unknown role {body.role!r}")
    agent = DESK.builder(role=body.role, session_id=body.resume, approvals=DESK.approver)
    key = uuid.uuid4().hex
    CHATS[key] = Chat(key, DESK.stage, body.role, agent)
    return {"key": key, "session_id": agent.session_id, "stage": DESK.stage, "role": body.role,
            "resumed": bool(getattr(agent, "resumed", False)),
            "history": json.loads(json.dumps(agent.messages, default=str))}


@app.post("/api/send")
async def send(body: SendIn) -> dict:
    chat = _chat(body.key)
    if chat.task is not None and not chat.task.done():
        raise HTTPException(409, "Still answering the last message.")
    chat.task = asyncio.create_task(_pump(chat, body.text))
    return {"ok": True}


@app.post("/api/stop/{key}")
async def stop(key: str) -> dict:
    chat = _chat(key)
    if chat.task is None or chat.task.done():
        return {"stopped": False}
    chat.task.cancel()
    return {"stopped": True}


@app.get("/api/events/{key}")
async def events(key: str, request: Request, until_end: bool = False) -> StreamingResponse:
    """SSE. `until_end=1` closes the stream after the next run_end (used by tests)."""
    chat = _chat(key)
    chat.subscriber += 1
    me = chat.subscriber  # a reconnecting page replaces its old stream

    async def stream():
        yield f"retry: 2000\n: connected {BOOT_ID}\n\n"
        idle = 0.0
        while chat.subscriber == me and key in CHATS:
            if not until_end and await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(chat.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                idle += 1.0
                if idle >= 15:
                    idle = 0.0
                    yield ": ping\n\n"
                continue
            idle = 0.0
            yield f"data: {json.dumps(event, default=str)}\n\n"
            if until_end and event["kind"] == "run_end" and not event.get("subagent"):
                break

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/approve")
async def approve(body: ApproveIn) -> dict:
    return {"ok": DESK.approver.resolve(body.request_id, body.approved)}


@app.get("/api/sessions")
async def sessions() -> list[dict]:
    """Past stage-4 sessions that have messages, newest first (empty below stage 4)."""
    if DESK.stage is None or DESK.stage < 4:
        return []
    return [s for s in SessionStore().list_sessions() if s["stage"] == 4 and s["message_count"]]


@app.post("/api/compact/{key}")
async def compact(key: str) -> dict:
    chat = _chat(key)
    if chat.task is not None and not chat.task.done():
        raise HTTPException(409, "Wait for the answer to finish.")
    before = len(chat.agent.messages)
    produced = await chat.agent.compact_now()  # [] below stage 4: no Compactor installed
    for event in produced:
        chat.queue.put_nowait(event.to_json())
    after = len(chat.agent.messages)
    return {"compacted": after < before, "before": before, "after": after,
            **({} if after < before else {"reason": "Not enough history to compact yet."})}


# ------------------------------------------------------------------ running it

_SERVER: dict[str, Any] = {}


def start_in_thread(port: int | None = None, timeout: float = 15.0) -> str:
    """Start uvicorn in a daemon thread with its own event loop (idempotent). Returns the URL."""
    import uvicorn

    port = int(port or os.environ.get("KESTREL_CHAT_PORT") or DEFAULT_PORT)
    url = f"http://{HOST}:{port}"
    server, thread = _SERVER.get("server"), _SERVER.get("thread")
    if server is not None and thread.is_alive():
        return _SERVER["url"]
    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, name="kestrel-chatwin", daemon=True)
    thread.start()
    deadline = time.time() + timeout
    while not server.started:
        if not thread.is_alive() or time.time() > deadline:
            raise RuntimeError(f"The chat window could not start on {url} (is the port already in use?)")
        time.sleep(0.05)
    _SERVER.update(server=server, thread=thread, url=url)
    return url


def stop_thread() -> None:
    server, thread = _SERVER.pop("server", None), _SERVER.pop("thread", None)
    _SERVER.pop("url", None)
    if server is not None:
        server.should_exit = True
        thread.join(timeout=10)
