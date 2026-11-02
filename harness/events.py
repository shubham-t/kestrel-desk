"""Event and RunContext: what the loop tells the outside world, and what tools/middleware can see.

Defined here (and re-exported by loop.py) so tools and middleware can emit events
without importing the loop.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Callable, Literal

EventKind = Literal[
    "run_start", "text_delta", "text_done", "tool_call", "decision", "approval_request",
    "approval_result", "tool_result", "todo_update", "subagent_start", "subagent_end",
    "compaction", "audit", "checkpoint", "usage", "run_end", "error",
]


@dataclass
class Event:
    kind: EventKind
    data: dict
    component: str | None = None  # "model"|"context"|"actions"|"boundaries"|"persistence": drives the UI map
    subagent: str | None = None  # set on events that happened inside a subagent run
    ts: float = field(default_factory=time.time)

    def to_json(self) -> dict:
        """A plain JSON-serializable dict (non-JSON values in data are stringified)."""
        return {
            "kind": self.kind,
            "data": json.loads(json.dumps(self.data, default=str)),
            "component": self.component,
            "subagent": self.subagent,
            "ts": self.ts,
        }


def _drop(event: Event) -> None:
    """Default sink before a run starts."""


@dataclass
class RunContext:
    """Per-agent run context. `state` survives across turns of the same Agent (todos, counters)."""

    role: str
    stage: int
    session_id: str
    state: dict = field(default_factory=dict)
    emit: Callable[[Event], None] = _drop
