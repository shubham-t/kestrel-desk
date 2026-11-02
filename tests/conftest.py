"""Shared fixtures: every test writes state into a temp folder, never into the repo."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness import config as hconfig  # noqa: E402
from harness.events import RunContext  # noqa: E402


def pytest_configure(config):
    """Keep pytest's temp dirs inside the repo (.harness_state/), so locked-down laptops work too."""
    if not config.option.basetemp:
        hconfig.STATE_DIR.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(hconfig.STATE_DIR / "pytest-tmp")


@pytest.fixture
def tmp_state(monkeypatch, tmp_path):
    """Point outbox, audit log, DB and workspace at a temp dir."""
    state = tmp_path / "state"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(hconfig, "STATE_DIR", state)
    monkeypatch.setattr(hconfig, "OUTBOX_DIR", state / "outbox")
    monkeypatch.setattr(hconfig, "AUDIT_LOG", state / "audit.jsonl")
    monkeypatch.setattr(hconfig, "DB_PATH", state / "kestrel.sqlite")
    monkeypatch.setattr(hconfig, "WORKSPACE_DIR", workspace)
    return tmp_path


@pytest.fixture
def ctx():
    events = []
    context = RunContext(role="sales", stage=4, session_id="test", state={"calls": {"model": 0, "tool": 0}},
                         emit=events.append)
    context.events = events  # handy for assertions
    return context


async def collect(agent, text: str) -> list:
    return [event async for event in agent.run(text)]
