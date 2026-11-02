"""Settings and paths. `.env` is the only thing you edit to point the harness at another endpoint."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPANY_DIR = REPO_ROOT / "company"
DATA_DIR = COMPANY_DIR / "data"
SKILLS_DIR = REPO_ROOT / "skills"
WORKSPACE_DIR = REPO_ROOT / "workspace"
STATE_DIR = REPO_ROOT / ".harness_state"
DB_PATH = STATE_DIR / "kestrel.sqlite"
OUTBOX_DIR = STATE_DIR / "outbox"
AUDIT_LOG = STATE_DIR / "audit.jsonl"

ROLES = ("sales", "engineering", "finance")

load_dotenv(REPO_ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, "").strip() or default


def _json_object(var: str) -> dict:
    """Parse an optional JSON-object env var; empty means {}."""
    raw = _env(var)
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{var} must be a JSON object: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{var} must be a JSON object")
    return value


def _extra_headers() -> dict[str, str]:
    return {str(k): str(v) for k, v in _json_object("LLM_EXTRA_HEADERS").items()}


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str | None = field(repr=False)  # never printed, never logged
    model: str
    subagent_model: str
    max_tokens: int
    extra_headers: dict[str, str]
    extra_body: dict  # provider-specific request fields (e.g. Anthropic's output_config.effort); empty = portable
    compact_at_tokens: int
    keep_last_messages: int

    @classmethod
    def load(cls) -> "Settings":
        key = _env("LLM_API_KEY") or _env("ANTHROPIC_API_KEY") or _env("OPENAI_API_KEY")
        return cls(
            base_url=_env("LLM_BASE_URL", "https://api.anthropic.com/v1/"),
            api_key=key or None,
            model=_env("LLM_MODEL", "claude-sonnet-5-5"),
            subagent_model=_env("LLM_SUBAGENT_MODEL", "claude-haiku-5-5"),
            max_tokens=int(_env("LLM_MAX_TOKENS", "4096")),
            extra_headers=_extra_headers(),
            extra_body=_json_object("LLM_EXTRA_BODY"),
            compact_at_tokens=int(_env("KESTREL_COMPACT_AT_TOKENS", "6000")),
            keep_last_messages=int(_env("KESTREL_KEEP_LAST_MESSAGES", "6")),
        )


settings = Settings.load()


@dataclass(frozen=True)
class StageInfo:
    id: int
    name: str
    component: str
    tagline: str


STAGES = [
    StageInfo(0, "Chatbot", "model", "A system prompt, a message list, one model call."),
    StageInfo(1, "Context", "context", "Company instructions always on; skills loaded on demand."),
    StageInfo(2, "Actions", "actions", "Tools, the agent loop, middleware and a subagent."),
    StageInfo(3, "Boundaries", "boundaries", "Role permissions, protected paths, human approval, audit log."),
    StageInfo(4, "Persistence", "persistence", "Checkpoints, a writable workspace, context compaction."),
]


def ensure_dirs() -> None:
    """Create the runtime folders (globals are read at call time, so tests can monkeypatch them)."""
    for path in (STATE_DIR, OUTBOX_DIR, WORKSPACE_DIR):
        path.mkdir(parents=True, exist_ok=True)
