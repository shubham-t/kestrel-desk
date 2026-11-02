"""The only file that talks to a model provider.

Everything else sees provider-neutral types (ToolSpec, ToolCall, LLMChunk, Usage) and
plain OpenAI-shaped message dicts. Swapping providers means editing `.env`, not code.
"""
from __future__ import annotations

import copy
import json
import uuid
from dataclasses import dataclass
from typing import AsyncIterator, Protocol

from .config import settings


class LLMError(Exception):
    """A model call failed. The loop turns this into an `error` event instead of crashing."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class ConfigError(LLMError):
    """Raised only when a real call is attempted without a key, so offline paths keep working."""


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict
    raw_arguments: str | None = None  # kept when the model sent arguments that are not valid JSON


@dataclass
class Usage:
    prompt_tokens: int
    completion_tokens: int


@dataclass
class LLMChunk:
    text: str = ""
    tool_calls: list[ToolCall] | None = None  # final chunk only
    usage: Usage | None = None  # final chunk only
    finish_reason: str | None = None  # final chunk only


class LLM(Protocol):
    model: str

    def stream(self, messages: list[dict], tools: list[ToolSpec] | None) -> AsyncIterator[LLMChunk]: ...


def fake_call(name: str, **arguments) -> ToolCall:
    """Convenience for scripting FakeLLM: `fake_call("lookup_customer", name="Acme")`."""
    return ToolCall(id=f"call_{uuid.uuid4().hex[:8]}", name=name, arguments=arguments)


class OpenAICompatibleLLM:
    """Any OpenAI-compatible chat-completions endpoint (Anthropic's compat layer by default)."""

    def __init__(self, *, model: str, base_url: str, api_key: str | None, max_tokens: int,
                 extra_headers: dict | None = None, extra_body: dict | None = None):
        self.model = model
        self.base_url = base_url
        self._api_key = api_key
        self.max_tokens = max_tokens
        self.extra_headers = dict(extra_headers or {})
        # Provider-specific request fields (LLM_EXTRA_BODY), e.g. Anthropic's output_config.effort.
        # Empty by default so the request stays portable across OpenAI-compatible endpoints.
        self.extra_body = dict(extra_body or {})
        self._client = None  # created lazily: no key is needed until a real call happens

    def for_model(self, model: str) -> "OpenAICompatibleLLM":
        """Same endpoint, different model (subagents use a cheaper one)."""
        return OpenAICompatibleLLM(model=model, base_url=self.base_url, api_key=self._api_key,
                                   max_tokens=self.max_tokens, extra_headers=self.extra_headers,
                                   extra_body=self.extra_body)

    def _get_client(self):
        if not self._api_key:
            raise ConfigError("Set LLM_API_KEY (or ANTHROPIC_API_KEY) in .env")
        if self._client is None:
            import openai

            self._client = openai.AsyncOpenAI(base_url=self.base_url, api_key=self._api_key,
                                              default_headers=self.extra_headers or None)
        return self._client

    async def stream(self, messages: list[dict], tools: list[ToolSpec] | None = None) -> AsyncIterator[LLMChunk]:
        import openai

        client = self._get_client()
        # Deliberately minimal: no temperature/top_p/strict/parallel_tool_calls/reasoning_effort.
        # Some compatible endpoints reject them, and this keeps the request portable.
        request: dict = dict(model=self.model, messages=messages, max_tokens=self.max_tokens,
                             stream=True, stream_options={"include_usage": True})
        if tools:
            request["tools"] = [{"type": "function", "function": {
                "name": t.name, "description": t.description, "parameters": t.parameters}} for t in tools]
        if self.extra_body:
            request["extra_body"] = self.extra_body
        partial: dict[int, dict] = {}
        usage: Usage | None = None
        finish: str | None = None
        try:
            stream = await client.chat.completions.create(**request)
            async for chunk in stream:
                if getattr(chunk, "usage", None):
                    usage = Usage(chunk.usage.prompt_tokens or 0, chunk.usage.completion_tokens or 0)
                for choice in chunk.choices or []:
                    finish = choice.finish_reason or finish
                    delta = choice.delta
                    if delta is None:
                        continue
                    if delta.content:
                        yield LLMChunk(text=delta.content)
                    for tc in delta.tool_calls or []:
                        _accumulate_tool_delta(partial, tc)
        except openai.APIStatusError as exc:
            raise LLMError(f"Model endpoint returned {exc.status_code}: {exc.message}", exc.status_code) from exc
        except openai.APIConnectionError as exc:
            raise LLMError(f"Could not reach model endpoint {self.base_url}: {exc}") from exc
        calls = [_finish_tool_call(i, slot) for i, slot in sorted(partial.items())]
        yield LLMChunk(tool_calls=calls or None, usage=usage, finish_reason=finish)


def _accumulate_tool_delta(partial: dict[int, dict], tc) -> None:
    """Tool calls arrive in fragments keyed by index; stitch id, name and argument text together."""
    index = tc.index if tc.index is not None else (len(partial) if tc.id else max(partial, default=0))
    slot = partial.setdefault(index, {"id": "", "name": "", "arguments": ""})
    if tc.id:
        slot["id"] = tc.id
    fn = tc.function
    if fn is not None:
        if fn.name and not slot["name"]:
            slot["name"] = fn.name
        if fn.arguments:
            slot["arguments"] += fn.arguments


def _finish_tool_call(index: int, slot: dict) -> ToolCall:
    raw = slot["arguments"] or "{}"
    try:
        args = json.loads(raw)
        if not isinstance(args, dict):
            raise ValueError("arguments are not an object")
        return ToolCall(id=slot["id"] or f"call_{index}", name=slot["name"], arguments=args)
    except ValueError:
        return ToolCall(id=slot["id"] or f"call_{index}", name=slot["name"], arguments={}, raw_arguments=raw)


class FakeLLM:
    """Scripted responses for tests and the offline verify script.

    Each script item is a str (text reply), a list[ToolCall] (tool calls), or an Exception
    (raised). One item is popped per call; an exhausted script raises LLMError. Every
    payload received is recorded in `.calls` for assertions.
    """

    def __init__(self, script: list, *, model: str = "fake-model", prompt_tokens: int | None = None):
        self.model = model
        self.script = list(script)
        self.prompt_tokens = prompt_tokens  # fixed value, or None to estimate from the payload
        self.calls: list[dict] = []

    def for_model(self, model: str) -> "FakeLLM":
        return self  # subagents share the script, so a test reads top to bottom

    async def stream(self, messages: list[dict], tools: list[ToolSpec] | None = None) -> AsyncIterator[LLMChunk]:
        self.calls.append({"messages": copy.deepcopy(messages), "tools": list(tools or [])})
        if not self.script:
            raise LLMError("FakeLLM script exhausted")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        prompt = self.prompt_tokens if self.prompt_tokens is not None else len(json.dumps(messages)) // 4
        if isinstance(item, str):
            words = item.split(" ")
            for i, word in enumerate(words):
                yield LLMChunk(text=word if i == len(words) - 1 else word + " ")
            yield LLMChunk(usage=Usage(prompt, max(1, len(item) // 4)), finish_reason="stop")
        else:
            calls = [copy.deepcopy(c) for c in item]
            yield LLMChunk(tool_calls=calls, usage=Usage(prompt, 10 * len(calls)), finish_reason="tool_calls")


def make_llm(model: str | None = None) -> OpenAICompatibleLLM:
    """Build the real client from settings (.env)."""
    return OpenAICompatibleLLM(model=model or settings.model, base_url=settings.base_url,
                               api_key=settings.api_key, max_tokens=settings.max_tokens,
                               extra_headers=settings.extra_headers, extra_body=settings.extra_body)
