"""Kestrel Desk web server: a thin FastAPI shell around `harness.Agent`.

The server owns no agent logic. It builds an agent per browser session, runs `agent.run(text)`
as an asyncio task, and forwards every `Event.to_json()` to the browser over SSE.

    uvicorn app.server:app --port 8765                 # real harness
    KESTREL_MOCK=1 uvicorn app.server:app --port 8765  # rehearsal: scripted events, no harness, no network
"""
from __future__ import annotations

import asyncio
import dataclasses
import inspect
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

STATIC_DIR = Path(__file__).resolve().parent / "static"
MOCK = os.environ.get("KESTREL_MOCK", "").strip().lower() in {"1", "true", "yes", "on"}
BOOT_ID = uuid.uuid4().hex[:8]  # lets the browser notice a server restart


def _jsonable(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    return obj


def _with_fallbacks(stage: dict) -> dict:
    """describe_stage() grew `headline`/`problem`/`subagents` late; fill gaps from the canned copy."""
    from app.mock_data import HARNESS_STAGES
    canned = next((s for s in HARNESS_STAGES if s.get("id") == stage.get("id")), {})
    for key in ("headline", "problem", "subagents", "bullets", "unlocked_tools", "middlewares", "new_keywords"):
        if key not in stage and key in canned:
            stage[key] = canned[key]
    return stage


def _attr(obj: Any, *names: str, default: Any = None) -> Any:
    for n in names:
        if getattr(obj, n, None) is not None:
            return getattr(obj, n)
    return default


class RealBackend:
    """Adapter over the `harness` package (names exactly as in SPEC.md)."""
    mock = False

    def __init__(self) -> None:
        from harness import config
        from harness.approvals import FutureApprover
        from harness.config import ROLES, STAGES, settings
        from harness.persistence import SessionStore
        from harness.stages import build_agent, describe_stage, scenarios, stage_snippet

        self.config, self.settings, self.STAGES, self.ROLES = config, settings, STAGES, ROLES
        self.build_agent, self.describe_stage = build_agent, describe_stage
        self.stage_snippet, self.scenarios, self.SessionStore = stage_snippet, scenarios, SessionStore
        self.approver = FutureApprover()  # one shared broker; /api/approve resolves it
        self.roles = list(ROLES)
        self._store = None

    def store(self):
        if self._store is None:
            self._store = self.SessionStore()
        return self._store

    def stage_ids(self) -> list[int]:
        return [int(_attr(s, "id", default=i)) for i, s in enumerate(self.STAGES)]

    def meta(self) -> dict:
        s = self.settings
        base_url = _attr(s, "base_url", "llm_base_url", default="")
        ids = self.stage_ids()
        return {
            "model": _attr(s, "model", "llm_model", default="?"),
            "base_url_host": urlparse(str(base_url)).hostname or str(base_url),
            "mock": False,
            "stages": [_with_fallbacks(_jsonable(self.describe_stage(i))) for i in ids],
            "roles": list(self.ROLES),
            "scenarios": {i: [_jsonable(sc) for sc in self.scenarios(i)] for i in ids},
            "snippets": {i: [_jsonable(sn) for sn in self.stage_snippet(i)] for i in ids},
        }

    def new_agent(self, stage: int, role: str, session_id: str, resume: bool):
        store = self.store() if stage >= 4 else None
        agent = self.build_agent(stage, role, session_id=session_id, approvals=self.approver, store=store)
        history = list(getattr(agent, "messages", []) or [])
        return agent, history, bool(resume and getattr(agent, "resumed", bool(history)))

    def list_sessions(self) -> list[dict]:
        return self.store().list_sessions()

    def _path(self, name: str, attr: str) -> Path | None:
        p = getattr(self.config, name, None) or getattr(self.settings, attr, None)
        return Path(p) if p else None

    def audit(self, limit: int) -> list[dict]:
        path = self._path("AUDIT_LOG", "audit_log")
        if not path or not path.exists():
            return []
        out = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                out.append({"raw": line})
        return out

    def outbox(self) -> list[dict]:
        folder = self._path("OUTBOX_DIR", "outbox_dir")
        if not folder or not folder.exists():
            return []
        files = sorted(folder.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [{"name": f.name, "path": str(f), "size": f.stat().st_size, "modified": f.stat().st_mtime,
                 "preview": "\n".join(f.read_text(encoding="utf-8", errors="replace").splitlines()[:6])}
                for f in files[:50]]

    async def compact(self, agent, put) -> dict:
        """Force the Compactor once. Prefers an Agent method if the core exposes one; otherwise runs
        the Compactor middleware's before_model with the token threshold forced past its limit."""
        for name in ("compact_now", "force_compaction", "compact"):
            fn = getattr(agent, name, None)
            if callable(fn):
                res = fn()
                res = await res if inspect.isawaitable(res) else res
                if isinstance(res, list):  # Agent.compact_now() returns the events it produced
                    for ev in res:
                        put(ev.to_json() if hasattr(ev, "to_json") else _jsonable(ev))
                    done = any(getattr(ev, "kind", None) == "compaction" for ev in res)
                    return {"compacted": done, "events": len(res),
                            **({} if done else {"reason": "Not enough history to compact yet."})}
                return {"compacted": True, "result": _jsonable(res)}
        mws = _attr(agent, "middlewares", "middleware", default=[]) or []
        comp = next((m for m in mws if type(m).__name__ == "Compactor"), None)
        ctx = _attr(agent, "ctx", "context")
        if comp is None or ctx is None:
            return {"compacted": False, "reason": "No Compactor on this agent (stage 4 only)."}
        old_emit = ctx.emit
        ctx.emit = lambda ev: put(ev.to_json())  # route compaction events to this session's stream
        try:
            ctx.state["last_prompt_tokens"] = 10**9
            system = {"role": "system", "content": _attr(agent, "system_prompt", default="")}
            msgs = await comp.before_model([system, *agent.messages], ctx)
            ctx.state["last_prompt_tokens"] = 0
        finally:
            ctx.emit = old_emit
        before, after = len(agent.messages), len(msgs) - 1
        if after < before:
            agent.messages[:] = msgs[1:]
            store = _attr(agent, "store", "checkpointer")
            if store is not None:
                store.replace_all(ctx.session_id, agent.messages)
        return {"compacted": after < before, "before": before, "after": after}


if MOCK:
    from app.mock import MockBackend
    backend: Any = MockBackend()
else:
    try:
        backend = RealBackend()
    except ImportError as exc:  # make the fallback obvious instead of a bare traceback
        raise RuntimeError(f"Cannot import the harness package ({exc}). Set KESTREL_MOCK=1 for rehearsal mode.") from exc


@dataclasses.dataclass
class Session:
    key: str
    session_id: str
    stage: int
    role: str
    agent: Any
    queue: asyncio.Queue = dataclasses.field(default_factory=asyncio.Queue)
    task: asyncio.Task | None = None
    subscriber: int = 0
    closed: bool = False


SESSIONS: dict[str, Session] = {}
app = FastAPI(title="Kestrel Desk")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def _revalidate_static(request: Request, call_next):
    """Edits to app/static show up on a plain reload (ETag revalidation, no stale cache on talk day)."""
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


def _sys_event(kind: str, data: dict) -> dict:
    return {"kind": kind, "data": data, "component": None, "subagent": None, "ts": time.time()}


def _get(key: str) -> Session:
    sess = SESSIONS.get(key)
    if sess is None:
        raise HTTPException(404, f"Unknown session_key {key!r}")
    return sess


def _repair_history(agent: Any) -> None:
    """After a Stop, never leave an assistant tool call without its tool message."""
    msgs = getattr(agent, "messages", None)
    if not isinstance(msgs, list):
        return
    last = next((i for i in range(len(msgs) - 1, -1, -1)
                 if isinstance(msgs[i], dict) and msgs[i].get("role") == "assistant"), None)
    if last is None:
        return
    answered = {m.get("tool_call_id") for m in msgs[last + 1:] if isinstance(m, dict)}
    for call in msgs[last].get("tool_calls") or []:
        cid = call.get("id") if isinstance(call, dict) else getattr(call, "id", None)
        if cid and cid not in answered:
            msgs.append({"role": "tool", "tool_call_id": cid, "content": "aborted (stopped by user)"})


async def _pump(sess: Session, text: str) -> None:
    put = sess.queue.put_nowait
    run = sess.agent.run(text)
    try:
        async for ev in run:
            put(ev.to_json() if hasattr(ev, "to_json") else _jsonable(ev))
    except asyncio.CancelledError:  # POST /api/stop: end cleanly, never leave a dangling tool call
        _repair_history(sess.agent)
        put(_sys_event("run_end", {"session_id": sess.session_id, "error": False, "stopped": True, "by_user": True}))
    except Exception as exc:  # the loop should catch its own errors; this is the last line of defence
        put(_sys_event("error", {"message": f"{type(exc).__name__}: {exc}"}))
        put(_sys_event("run_end", {"session_id": sess.session_id, "error": True}))
    finally:
        sess.task = None
        try:
            await run.aclose()
        except Exception:
            pass


class SessionIn(BaseModel):
    stage: int
    role: str
    resume_session_id: str | None = None


class SendIn(BaseModel):
    session_key: str
    text: str


class ApproveIn(BaseModel):
    request_id: str
    approved: bool


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/health")
async def health(session_key: str | None = None) -> dict:
    return {"ok": True, "boot_id": BOOT_ID, "mock": MOCK, "session": bool(session_key and session_key in SESSIONS)}


@app.get("/api/meta")
async def meta() -> dict:
    return {**backend.meta(), "boot_id": BOOT_ID}


@app.post("/api/session")
async def create_session(body: SessionIn) -> dict:
    if body.role not in backend.roles:
        raise HTTPException(400, f"Unknown role {body.role!r}")
    session_id = body.resume_session_id or uuid.uuid4().hex[:12]
    try:
        agent, history, resumed = backend.new_agent(body.stage, body.role, session_id, bool(body.resume_session_id))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    key = uuid.uuid4().hex
    SESSIONS[key] = Session(key, session_id, body.stage, body.role, agent)
    return {"session_key": key, "session_id": session_id, "resumed": resumed,
            "history": json.loads(json.dumps(history, default=str))}


@app.post("/api/send")
async def send(body: SendIn) -> dict:
    sess = _get(body.session_key)
    if sess.task is not None and not sess.task.done():
        raise HTTPException(409, "A run is already in flight for this session.")
    run_id = uuid.uuid4().hex[:8]
    sess.task = asyncio.create_task(_pump(sess, body.text))
    return {"run_id": run_id}


@app.post("/api/stop/{session_key}")
async def stop(session_key: str) -> dict:
    sess = _get(session_key)
    if sess.task is None or sess.task.done():
        return {"stopped": False}
    sess.task.cancel()
    return {"stopped": True}


@app.get("/api/events/{session_key}")
async def events(session_key: str, request: Request) -> StreamingResponse:
    sess = _get(session_key)
    sess.subscriber += 1
    me = sess.subscriber  # a reconnecting browser replaces the old stream instead of racing it

    async def stream():
        yield f"retry: 2000\n: connected boot={BOOT_ID}\n\n"
        idle = 0.0
        while not sess.closed and sess.subscriber == me:
            if await request.is_disconnected():
                break
            try:
                ev = await asyncio.wait_for(sess.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                idle += 1.0
                if idle >= 15:
                    idle = 0.0
                    yield ": ping\n\n"
                continue
            idle = 0.0
            yield f"data: {json.dumps(ev, default=str)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/approve")
async def approve(body: ApproveIn) -> dict:
    approver = backend.approver
    pending = getattr(approver, "pending", None)
    known = pending is None or body.request_id in pending
    res = approver.resolve(body.request_id, body.approved)
    if inspect.isawaitable(res):
        res = await res
    return {"ok": bool(res) if isinstance(res, bool) else known}


@app.get("/api/sessions")
async def sessions() -> list[dict]:
    """Only sessions with history: opening the stage-4 chat creates an empty row we never want to list."""
    rows = [_jsonable(s) for s in backend.list_sessions()]
    return [s for s in rows if (s.get("message_count") if isinstance(s, dict) else 1)]


@app.delete("/api/session/{session_key}")
async def delete_session(session_key: str) -> dict:
    sess = SESSIONS.pop(session_key, None)
    if sess is None:
        return {"deleted": False}
    sess.closed = True
    if sess.task is not None and not sess.task.done():
        sess.task.cancel()
    return {"deleted": True}


@app.post("/api/compact/{session_key}")
async def compact(session_key: str) -> dict:
    sess = _get(session_key)
    if sess.stage < 4:
        raise HTTPException(400, "Compaction is a stage 4 component.")
    if sess.task is not None and not sess.task.done():
        raise HTTPException(409, "Wait for the current run to finish.")

    return await backend.compact(sess.agent, sess.queue.put_nowait)


@app.get("/api/audit")
async def audit(limit: int = 50) -> list[dict]:
    return backend.audit(max(1, min(limit, 500)))


@app.get("/api/outbox")
async def outbox() -> list[dict]:
    return backend.outbox()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)
