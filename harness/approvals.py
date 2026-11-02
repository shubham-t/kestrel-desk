"""Human approval: how a paused tool call gets a yes or no.

The loop only knows `await approvals.ask(request) -> bool`. Where the human sits
(terminal, web page, nobody) is a pluggable broker.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger(__name__)


@dataclass
class ApprovalRequest:
    id: str
    tool: str
    arguments: dict
    session_id: str


class ApprovalBroker(Protocol):
    async def ask(self, req: ApprovalRequest) -> bool: ...


class AutoReject:
    """Default when nothing is wired: anything that needs a human is refused (fail closed)."""

    async def ask(self, req: ApprovalRequest) -> bool:
        log.warning("Auto-rejected %s (no approver wired) in session %s", req.tool, req.session_id)
        return False


class AutoApprove:
    """For tests and scripted demos only."""

    async def ask(self, req: ApprovalRequest) -> bool:
        return True


def describe_request(req: ApprovalRequest) -> str:
    target = req.arguments.get("to_email") or req.arguments.get("path")
    return f"{req.tool} → {target}" if target else f"{req.tool} {json.dumps(req.arguments)[:120]}"


class StdinApprover:
    """CLI: asks on the terminal."""

    async def ask(self, req: ApprovalRequest) -> bool:
        answer = await asyncio.to_thread(input, f"Approve {describe_request(req)}? [y/N] ")
        return answer.strip().lower() in ("y", "yes")


class FutureApprover:
    """Web: each request becomes a Future that `resolve(id, approved)` completes. Times out to False."""

    def __init__(self, timeout: float = 600.0):
        self.timeout = timeout
        self.pending: dict[str, asyncio.Future] = {}
        self.requests: dict[str, ApprovalRequest] = {}

    async def ask(self, req: ApprovalRequest) -> bool:
        future = asyncio.get_running_loop().create_future()
        self.pending[req.id] = future
        self.requests[req.id] = req
        try:
            return bool(await asyncio.wait_for(future, self.timeout))
        except asyncio.TimeoutError:
            return False
        finally:
            self.pending.pop(req.id, None)
            self.requests.pop(req.id, None)

    def resolve(self, request_id: str, approved: bool) -> bool:
        """Returns False if the request is unknown or already settled."""
        future = self.pending.get(request_id)
        if future is None or future.done():
            return False
        future.set_result(bool(approved))
        return True
