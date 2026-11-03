"""Offline model for the notebook and the chat window (`KESTREL_FAKE_LLM=1`): no key, no network.

A `FakeLLM` whose script refills itself from the conversation: with tools it makes one tool
call that fits the prompt, then answers; without tools it answers directly. Plausible, not smart.
"""
from __future__ import annotations

import json
import os
import uuid

from harness import config
from harness.compaction import COMPACTION_PROMPT
from harness.llm import FakeLLM, ToolCall, make_llm


def redirect_state() -> None:
    """Honour KESTREL_STATE_DIR / KESTREL_WORKSPACE_DIR, so offline runs never touch the real
    .harness_state/ or workspace/ (harness modules read these config paths at call time)."""
    from pathlib import Path
    if state := os.environ.get("KESTREL_STATE_DIR", "").strip():
        root = Path(state)
        config.STATE_DIR, config.DB_PATH = root, root / "kestrel.sqlite"
        config.OUTBOX_DIR, config.AUDIT_LOG = root / "outbox", root / "audit.jsonl"
    if workspace := os.environ.get("KESTREL_WORKSPACE_DIR", "").strip():
        config.WORKSPACE_DIR = Path(workspace)
        config.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


def fake_enabled() -> bool:
    return os.environ.get("KESTREL_FAKE_LLM", "").strip().lower() in {"1", "true", "yes", "on"}


def get_llm():
    """The real model from .env, or the offline script when KESTREL_FAKE_LLM=1."""
    return NotebookFakeLLM() if fake_enabled() else make_llm()


def _acme_email() -> str:
    customers = json.loads((config.DATA_DIR / "customers.json").read_text(encoding="utf-8"))
    return next(c["contact_email"] for c in customers if c["id"] == "cust_acme")


def _pick_call(prompt: str, tools: set[str]):
    """One tool call that suits the prompt, if the agent has that tool."""
    p = prompt.lower()
    wanted = []
    if "revenue" in p:
        wanted.append(("get_revenue", dict(period="FY2026")))
    if "send" in p:
        wanted.append(("send_proposal", dict(customer_id="cust_acme", to_email=_acme_email(),
                                             subject="Kestrel renewal proposal",
                                             body_markdown="# Acme Robotics renewal\n\n40 seats, Enterprise.")))
    if "where did we leave off" in p:
        wanted.append(("list_workspace_files", {}))
    elif "save it" in p:
        wanted.append(("write_workspace_file", dict(path="workspace/acme-renewal.md",
                                                    content="# Acme Robotics renewal (draft)\n\n40 seats, Enterprise.\n")))
    if "record" in p:
        wanted.append(("lookup_customer", dict(name="Acme Robotics")))
    if "issue" in p and "every customer" not in p:
        wanted.append(("lookup_issue", dict(query="Acme Robotics")))
    wanted.append(("lookup_customer", dict(name="Acme Robotics")))
    for name, args in wanted:
        if name in tools:
            return ToolCall(id=f"call_{uuid.uuid4().hex[:8]}", name=name, arguments=args)
    return None


def _reply(messages: list[dict]) -> str:
    last = messages[-1]
    if last["role"] == "tool":
        result = str(last.get("content") or "")
        if result.startswith("Blocked by harness"):
            return f"I can't do that from this role. The harness said: *{result[len('Blocked by harness: '):]}*"
        if result.startswith(("Tool error", "User rejected")):
            return f"That didn't go through: {result}"
        name = next((c["function"]["name"] for m in reversed(messages) if m["role"] == "assistant"
                     for c in m.get("tool_calls") or [] if c["id"] == last.get("tool_call_id")), "the tool")
        head = "\n".join(result.splitlines()[:8])
        return ("**Offline reply** (`KESTREL_FAKE_LLM=1`): the real model would answer here.\n\n"
                f"| Tool | Result size |\n|---|---|\n| `{name}` | {len(result)} chars |\n\n"
                f"```\n{head}\n```")
    has_company = "Kestrel" in str(messages[0].get("content", ""))
    if has_company:
        return ("**Offline reply** (`KESTREL_FAKE_LLM=1`). I know Kestrel's plans and rules from "
                "AGENTS.md, but I can't look up customer records yet.")
    return ("**Offline reply** (`KESTREL_FAKE_LLM=1`). I'm a general assistant: I don't know who "
            "Acme Robotics is or what Kestrel charges.")


class NotebookFakeLLM(FakeLLM):
    """FakeLLM with a self-refilling script (see module docstring)."""

    def __init__(self):
        super().__init__([], model="fake-model")

    async def stream(self, messages, tools=None):
        if not self.script:
            self.script.append(self._next(messages, tools))
        async for chunk in super().stream(messages, tools):
            yield chunk

    def _next(self, messages: list[dict], tools):
        if messages and messages[0].get("content") == COMPACTION_PROMPT:
            return "- Drafted the Acme Robotics renewal (cust_acme).\n- Saved workspace/acme-renewal.md."
        names = {t.name for t in tools or []}
        if names and messages[-1]["role"] == "user":
            call = _pick_call(str(messages[-1].get("content") or ""), names)
            if call is not None:
                return [call]
        return _reply(messages)
