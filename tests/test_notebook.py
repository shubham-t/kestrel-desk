"""The notebook version: every stage cell is the real Agent(...) call, and the notebook runs offline."""
from __future__ import annotations

import re
import socket
from pathlib import Path

import pytest

from harness.talk import stage_snippet

nbformat = pytest.importorskip("nbformat")

NOTEBOOK = Path(__file__).resolve().parent.parent / "notebooks" / "kestrel_desk.ipynb"


def _squash(code: str) -> str:
    return re.sub(r"\s+", "", code)


def _code_cells() -> list[str]:
    nb = nbformat.read(NOTEBOOK, as_version=4)
    return [c.source for c in nb.cells if c.cell_type == "code"]


@pytest.mark.parametrize("stage", range(5))
def test_stage_cell_is_the_real_agent_call(stage):
    """Each build_stage_N cell holds stages.py's Agent(...) call verbatim (modulo whitespace)."""
    cell = next(c for c in _code_cells() if c.lstrip().startswith(f"def build_stage_{stage}("))
    assert _squash(stage_snippet(stage)[0]["code"]) in _squash(cell)
    assert f'def build_stage_{stage}(role="sales", session_id=None, approvals=None):' in cell
    # `common` is defined the way stages.py defines it, then expanded with **common
    assert _squash("common = dict(role=role, stage=%d, session_id=session_id or uuid.uuid4().hex[:12], "
                   "approvals=approvals)" % stage) in _squash(cell)
    assert cell.count("Agent(") == 1
    assert f"serve(build_stage_{stage}, stage={stage})" in "\n".join(_code_cells())


def test_code_cells_stay_short():
    assert all(len(c.splitlines()) <= 15 for c in _code_cells())


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.filterwarnings("ignore:Proactor event loop:RuntimeWarning")  # pyzmq on Windows, harmless
def test_notebook_runs_top_to_bottom_offline(tmp_path, monkeypatch):
    nbclient = pytest.importorskip("nbclient")
    monkeypatch.setenv("KESTREL_FAKE_LLM", "1")
    monkeypatch.setenv("KESTREL_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("KESTREL_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("KESTREL_CHAT_PORT", str(_free_port()))
    nb = nbformat.read(NOTEBOOK, as_version=4)
    client = nbclient.NotebookClient(nb, timeout=180, kernel_name="python3",
                                     resources={"metadata": {"path": str(NOTEBOOK.parent)}})
    client.execute()  # raises CellExecutionError on the first failing cell

    errors = [o for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", [])
              if o.get("output_type") == "error"]
    assert not errors
    text = "\n".join(o.get("text", "") for c in nb.cells if c.cell_type == "code"
                     for o in c.get("outputs", []) if o.get("output_type") == "stream")
    assert "refresh the chat window" in text
    assert "lookup_customer" in text  # stage 2 made a tool call
    assert "get_revenue" in text and "denied" in text  # stage 3: engineering may not see revenue
    assert "resumed session" in text  # stage 4 picked a saved session back up
    assert (tmp_path / "workspace" / "acme-renewal.md").exists()  # stage 4 wrote into the temp workspace
    assert (tmp_path / "state" / "kestrel.sqlite").exists()
