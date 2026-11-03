"""Notebook helpers for Kestrel Desk: serve(), demo(), list_sessions(), get_llm().

Importing this module puts the repo root on sys.path, so the notebook can `import harness`.
Environment knobs (all optional):
    KESTREL_FAKE_LLM=1        offline scripted model instead of the real one from .env
    KESTREL_CHAT_PORT=8777    port of the chat window
    KESTREL_STATE_DIR=...     where sessions, the audit log and the outbox go (tests use a temp dir)
    KESTREL_WORKSPACE_DIR=... the folder the agent may write into (tests use a temp dir)
"""
from __future__ import annotations

import asyncio
import gc
import json
import queue
import sys
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from harness import config  # noqa: E402
from harness.approvals import AutoApprove  # noqa: E402

__all__ = ["serve", "demo", "list_sessions", "get_llm"]


from chatwin.fake import fake_enabled, get_llm, redirect_state  # noqa: E402,F401  (get_llm is re-exported)

redirect_state()  # before the notebook imports WORKSPACE_DIR from harness.config

from chatwin import server as _chatwin  # noqa: E402


# ------------------------------------------------------------------ the chat window

def serve(builder, stage: int) -> None:
    """Point the chat window at `builder` (start it the first time). Then refresh the browser."""
    _chatwin.set_builder(builder, stage)
    url = _chatwin.start_in_thread()
    name = config.STAGES[stage].name
    mode = " (offline fake model)" if fake_enabled() else ""
    print(f"Chat window now serves stage {stage} · {name}{mode}\n{url}\n-> refresh the chat window")


# ------------------------------------------------------------------ one scenario, inline

def _args(arguments) -> str:
    if not isinstance(arguments, dict):
        return str(arguments)
    parts = [f"{json.dumps(k)}: {json.dumps(v if not isinstance(v, str) or len(v) <= 50 else v[:49] + '…', ensure_ascii=False)}"
             for k, v in arguments.items()]
    return "{" + ", ".join(parts) + "}"


class _NotebookApprover(AutoApprove):
    """Approves everything, but says so: in the chat window a human clicks Approve instead."""

    def __init__(self, out: queue.Queue):
        self.out = out

    async def ask(self, req) -> bool:
        target = req.arguments.get("to_email") or req.arguments.get("path") or ""
        self.out.put(("line", f"  ⏸ {req.tool} {('→ ' + target) if target else ''} needs approval: "
                              "auto-approved in the notebook (the chat window asks a human)"))
        return True


def _format(event) -> str | None:
    d, indent = event.data, "      " if event.subagent else "  "
    if event.kind == "tool_call":
        return f"{indent}{d['name']} · {_args(d['arguments'])}"
    if event.kind == "tool_result":
        if d["ok"]:
            return f"{indent}  ✓ {d['name']}"
        reason = d["preview"].split("\n")[0].removeprefix("Blocked by harness: ")
        label = {"deny": "denied", "allow": "failed"}.get(d["outcome"], d["outcome"])
        return f"{indent}  ✗ {d['name']} {label}: {reason}"
    if event.kind == "compaction":
        return f"  ⇣ compacted: {d['before']} → {d['after']} messages"
    if event.kind == "error" and not event.subagent:
        return f"  ! error: {d['message']}"
    return None


def demo(builder, prompt: str, role: str = "sales", session_id: str | None = None) -> None:
    """Run one prompt through `builder`'s agent and print what happened, compactly."""
    out: queue.Queue = queue.Queue()

    async def run_one():
        agent = builder(role=role, session_id=session_id, approvals=_NotebookApprover(out))
        if getattr(agent, "resumed", False):
            out.put(("line", f"↺ resumed session {agent.session_id} from SQLite ({len(agent.messages)} messages)"))
        out.put(("line", f"▶ {role} · stage {agent.stage} · session {agent.session_id}\n  you: {prompt}"))
        async for event in agent.run(prompt):
            if line := _format(event):
                out.put(("line", line))
            if event.kind == "text_done" and not event.subagent:
                out.put(("reply", event.data["text"]))
            if event.kind == "run_end" and not event.subagent:
                d = event.data
                out.put(("line", f"  ({d['model_calls']} model calls · {d['tool_calls']} tool calls · "
                                 f"{d['prompt_tokens']:,} tokens in / {d['completion_tokens']:,} out)"))

    async def run():
        await run_one()
        # Free the model clients (subagents make their own) while their event loop is still open;
        # otherwise their cleanup lands on the next loop and prints "Event loop is closed".
        gc.collect()
        await asyncio.sleep(0.25)

    def worker():  # the notebook already runs an event loop, so the agent gets its own in a thread
        try:
            asyncio.run(run())
        except Exception as exc:
            out.put(("line", f"  ! {type(exc).__name__}: {exc}"))
        finally:
            out.put(None)

    threading.Thread(target=worker, daemon=True).start()
    while True:
        try:
            item = out.get(timeout=0.2)  # a timeout keeps "Interrupt kernel" working
        except queue.Empty:
            continue
        if item is None:
            break
        kind, text = item
        if kind == "reply":
            _show_reply(text)
        else:
            print(text, flush=True)


def _show_reply(text: str) -> None:
    try:
        from IPython import get_ipython
        from IPython.display import Markdown, display
        if get_ipython() is not None:
            print("  assistant:", flush=True)
            display(Markdown(text))
            return
    except ImportError:
        pass
    print("  assistant:\n" + "\n".join("    " + ln for ln in text.splitlines()), flush=True)


# ------------------------------------------------------------------ stage 4 sessions

def list_sessions(limit: int = 5) -> list[dict]:
    """Saved stage-4 sessions (newest first). Prints a short table and returns the rows."""
    from harness.persistence import SessionStore
    rows = [s for s in SessionStore().list_sessions() if s["stage"] == 4 and s["message_count"]]
    if not rows:
        print("No saved stage-4 sessions yet.")
    for s in rows[:limit]:
        print(f"{s['session_id']}  {s['role']:<11} {s['message_count']:>3} msgs  "
              f"{s['updated_at'][:16].replace('T', ' ')}  {s['title'][:50]}")
    return rows
