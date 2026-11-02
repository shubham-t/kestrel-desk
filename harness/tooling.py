"""Tool plumbing: the Tool record, a registry, and the `@tool` decorator.

The decorator reads the JSON schema off the function's type hints and docstring, so a
tool is just a typed, documented async function. The model only ever sees the schema.
"""
from __future__ import annotations

import inspect
import json
import re
import types
import typing
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from .llm import ToolSpec

if TYPE_CHECKING:
    from .events import RunContext


class ToolError(Exception):
    """A tool failed in a way the model should read and recover from."""


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable[[dict, "RunContext"], Awaitable[str]]
    component: str = "actions"  # which harness node lights up in the UI
    read_only: bool = True
    requires_approval: bool = False

    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, self.parameters)


class ToolRegistry:
    """Name -> Tool. Order is kept so the model sees tools in a stable order."""

    def __init__(self, tools: list[Tool] | None = None):
        self._tools: dict[str, Tool] = {}
        for t in tools or []:
            self.add(t)

    def add(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def specs(self) -> list[ToolSpec]:
        return [t.spec() for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools)

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self):
        return iter(self._tools.values())


_SCALARS = {str: "string", int: "integer", float: "number", bool: "boolean", dict: "object"}


def _json_schema(annotation: Any) -> dict:
    """Map a Python type hint to a JSON Schema fragment."""
    if annotation in _SCALARS:
        return {"type": _SCALARS[annotation]}
    origin, args = typing.get_origin(annotation), typing.get_args(annotation)
    if origin in (typing.Union, types.UnionType):  # `X | None` -> X
        rest = [a for a in args if a is not type(None)]
        return _json_schema(rest[0]) if rest else {}
    if origin is typing.Literal:
        return {"type": _SCALARS.get(type(args[0]), "string"), "enum": list(args)}
    if annotation is list or origin is list:
        return {"type": "array", "items": _json_schema(args[0]) if args else {}}
    if origin is dict:
        return {"type": "object"}
    return {"type": "string"}


def _parse_docstring(doc: str) -> tuple[str, dict[str, str]]:
    """First paragraph -> description; an optional `Args:` section -> per-parameter text."""
    doc = inspect.cleandoc(doc or "")
    description = doc.split("\n\n")[0].replace("\n", " ").strip()
    params: dict[str, str] = {}
    match = re.search(r"^Args:\s*\n(.*?)(?:\n\s*\n|\Z)", doc, re.S | re.M)
    if match:
        for line in match.group(1).splitlines():
            m = re.match(r"\s*(\w+)(?:\s*\(.*?\))?:\s*(.+)", line)
            if m:
                params[m.group(1)] = m.group(2).strip()
    return description, params


def _resolve(fn: Callable, annotation: Any) -> Any:
    """Evaluate a string annotation (we use `from __future__ import annotations`)."""
    if isinstance(annotation, str):
        return eval(annotation, fn.__globals__)  # noqa: S307 - our own source code
    return annotation


def schema_for(fn: Callable) -> tuple[str, dict]:
    """Build (description, JSON Schema) from a function. `ctx` is injected, never exposed."""
    description, arg_docs = _parse_docstring(fn.__doc__ or "")
    properties: dict[str, dict] = {}
    required: list[str] = []
    for name, param in inspect.signature(fn).parameters.items():
        if name == "ctx":
            continue
        prop = _json_schema(_resolve(fn, param.annotation)) if param.annotation is not param.empty else {}
        if name in arg_docs:
            prop["description"] = arg_docs[name]
        properties[name] = prop
        if param.default is param.empty:
            required.append(name)
    return description, {"type": "object", "properties": properties, "required": required}


def tool(*, component: str = "actions", read_only: bool = True, requires_approval: bool = False):
    """Turn a typed, documented async function into a Tool. The function name is the tool name."""

    def wrap(fn: Callable[..., Awaitable[Any]]) -> Tool:
        description, parameters = schema_for(fn)
        names = set(parameters["properties"])
        wants_ctx = "ctx" in inspect.signature(fn).parameters

        async def handler(args: dict, ctx: "RunContext") -> str:
            missing = [p for p in parameters["required"] if p not in args]
            if missing:
                raise ToolError(f"Missing required argument(s): {', '.join(missing)}")
            kwargs = {k: v for k, v in args.items() if k in names}
            result = await (fn(**kwargs, ctx=ctx) if wants_ctx else fn(**kwargs))
            return result if isinstance(result, str) else json.dumps(result, indent=2, default=str)

        return Tool(name=fn.__name__, description=description, parameters=parameters, handler=handler,
                    component=component, read_only=read_only, requires_approval=requires_approval)

    return wrap
