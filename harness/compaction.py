"""Context compaction: when the prompt grows past a budget, old turns become one summary.

The summary is written by the agent's own model. Tool calls and their results are
summarized or kept together, so the history never holds a call without its result.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .config import settings
from .events import Event
from .middleware_base import Middleware

if TYPE_CHECKING:
    from .events import RunContext
    from .llm import LLM, Usage

SUMMARY_MARKER = "[Conversation summary]"

# [stage:4] What compaction asks the model to keep
COMPACTION_PROMPT = (
    "Summarize this conversation for your future self: decisions made, facts looked up "
    "(with record ids), files saved (with paths), and open items. Be terse; bullets are fine. "
    "Anything you leave out is forgotten."
)
# [/stage:4]


def _render(messages: list[dict]) -> str:
    """Flatten messages to a plain transcript, so the summary call has no tool-call structure to break."""
    lines = []
    for m in messages:
        if m.get("content"):
            text = m["content"] if m["role"] != "tool" else m["content"][:1500]
            lines.append(f"{m['role']}: {text}")
        for call in m.get("tool_calls") or []:
            fn = call["function"]
            lines.append(f"assistant called {fn['name']}({fn['arguments']})")
    return "\n\n".join(lines)


class Compactor(Middleware):
    """Replaces old turns with one summary message once the prompt passes `at_tokens`."""

    name, component = "Compactor", "persistence"

    def __init__(self, llm: LLM | None = None, *, at_tokens: int | None = None, keep_last: int | None = None):
        self.llm = llm  # None -> Agent binds its own model
        self.at_tokens = at_tokens if at_tokens is not None else settings.compact_at_tokens
        self.keep_last = keep_last if keep_last is not None else settings.keep_last_messages

    async def after_model(self, assistant_msg: dict, usage: Usage | None, ctx: RunContext) -> None:
        if usage is not None:
            ctx.state["last_prompt_tokens"] = usage.prompt_tokens

    async def before_model(self, messages: list[dict], ctx: RunContext) -> list[dict]:
        too_big = ctx.state.get("last_prompt_tokens", 0) > self.at_tokens
        if too_big and len(messages) > self.keep_last + 2:
            return await self.compact(messages, ctx)
        return messages

    def _cut_point(self, messages: list[dict]) -> int:
        """Index where the verbatim tail starts. Never start the tail on a tool result."""
        cut = max(1, len(messages) - self.keep_last)
        while cut > 1 and messages[cut]["role"] == "tool":
            cut -= 1  # keep the assistant's tool_calls message together with its results
        return cut

    async def compact(self, messages: list[dict], ctx: RunContext) -> list[dict]:
        """Summarize messages[1:cut] (messages[0] is the system prompt) into one user message."""
        cut = self._cut_point(messages)
        old = messages[1:cut]
        if len(old) < 2:
            return messages
        summary = await self._summarize(old)
        note = {"role": "user", "content": f"{SUMMARY_MARKER}\n{summary}"}
        compacted = [messages[0], note, *messages[cut:]]
        # The loop persists this as the new history (and to the checkpoint store).
        ctx.state["history_rewritten"] = True
        ctx.state["last_prompt_tokens"] = 0
        ctx.emit(Event("compaction", {"before": len(messages) - 1, "after": len(compacted) - 1,
                                      "summarized": len(old), "summary_preview": summary[:400]},
                       component=self.component))
        return compacted

    async def _summarize(self, old: list[dict]) -> str:
        request = [{"role": "system", "content": COMPACTION_PROMPT},
                   {"role": "user", "content": _render(old)}]
        parts = [chunk.text async for chunk in self.llm.stream(request, None)]
        return "".join(parts).strip() or "(empty summary)"


__all__ = ["Compactor", "COMPACTION_PROMPT", "SUMMARY_MARKER"]
