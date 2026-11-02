"""Terminal REPL for any stage: `python -m harness.cli --stage 3 --role finance`.

Prints every event compactly with its component tag, e.g. `[boundaries] deny: ...`.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .approvals import StdinApprover
from .config import ROLES, STAGES, ensure_dirs, settings
from .events import Event
from .persistence import SessionStore
from .stages import build_agent, describe_stage


def _short(value, limit: int = 120) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = text.replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def format_event(ev: Event) -> str | None:
    """One line per event (None = print nothing). Text deltas are streamed separately."""
    tag = f"[{ev.component or 'run'}]" + (f"[{ev.subagent}]" if ev.subagent else "")
    d = ev.data
    lines = {
        "tool_call": lambda: f"{tag} call {d['name']} {_short(d['arguments'])}",
        "decision": lambda: None if d.get("silent") else f"{tag} {d['action']}: {d['reason']}",
        "approval_result": lambda: f"{tag} approval {'granted' if d['approved'] else 'rejected'}",
        "tool_result": lambda: f"{tag} {'ok' if d['ok'] else 'FAILED'} {d['name']}: {_short(d['preview'])}",
        "todo_update": lambda: f"{tag} todos: " + "; ".join(f"[{i['status']}] {i['text']}" for i in d["items"]),
        "subagent_start": lambda: f"{tag} subagent {d['name']} started: {_short(d['task'], 80)}",
        "subagent_end": lambda: f"{tag} subagent {d['name']} finished",
        "compaction": lambda: f"{tag} compacted {d['before']} messages -> {d['after']}",
        "audit": lambda: f"{tag} audit: {d['tool']} ok={d['ok']} decision={d['decision']}",
        "checkpoint": lambda: f"{tag} checkpoint ({d['messages']} messages)",
        "error": lambda: f"[error] {d['message']}",
        "run_end": lambda: None if ev.subagent else (
            f"[run] done: {d['model_calls']} model calls, {d['tool_calls']} tool calls, "
            f"{d['prompt_tokens']} in / {d['completion_tokens']} out"),
    }
    return lines[ev.kind]() if ev.kind in lines else None


async def repl(stage: int, role: str, session_id: str | None) -> None:
    ensure_dirs()
    agent = build_agent(stage, role, session_id=session_id, approvals=StdinApprover())
    info = describe_stage(stage)
    print(f"Kestrel Desk · stage {stage} {info['name']} · role {role} · {agent.llm.model}")
    print(f"session {agent.session_id}{' (resumed, ' + str(len(agent.messages)) + ' messages)' if agent.resumed else ''}")
    print("Type a message; 'exit' to quit.\n")
    while True:
        try:
            text = (await asyncio.to_thread(input, "you> ")).strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in ("exit", "quit"):
            break
        if not text:
            continue
        streaming = False
        async for ev in agent.run(text):
            if ev.kind == "text_delta" and not ev.subagent:
                if not streaming:
                    print("desk> ", end="")
                    streaming = True
                print(ev.data["text"], end="", flush=True)
                continue
            line = format_event(ev)
            if line:
                if streaming:
                    print()
                    streaming = False
                print(line)
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m harness.cli", description="Kestrel Desk terminal REPL.")
    parser.add_argument("--stage", type=int, default=len(STAGES) - 1, choices=range(len(STAGES)),
                        help="harness stage 0-4 (default: 4)")
    parser.add_argument("--role", default="sales", choices=ROLES, help="user role (default: sales)")
    parser.add_argument("--session", help="resume this session id (stage 4)")
    parser.add_argument("--list-sessions", action="store_true", help="list saved sessions and exit")
    args = parser.parse_args(argv)
    if args.list_sessions:
        for s in SessionStore().list_sessions():
            print(f"{s['session_id']}  stage {s['stage']}  {s['role']:<11} {s['message_count']:>3} msgs  "
                  f"{s['updated_at']}  {s['title']}")
        return 0
    if not settings.api_key:
        print("Note: no API key set (LLM_API_KEY in .env); model calls will fail.", file=sys.stderr)
    try:
        asyncio.run(repl(args.stage, args.role, args.session))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
