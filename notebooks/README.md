# Kestrel Desk, notebook version

The same five stages as the web app, in the format of the reference video: a Jupyter
notebook where each stage is one code cell, plus a plain chat window (one chat, a role
dropdown, tool-call lines, and at stage 4 a list of past sessions) that you refresh after
running a cell. The harness is the same `harness/` package; nothing here changes it.

- `kestrel_desk.ipynb`: an intro chapter, one chapter per stage (0 to 4), a closing chapter.
- `kestrel_chat.py`: the helpers the notebook imports: `serve`, `demo`, `list_sessions`, `get_llm`.
- `../chatwin/`: the chat window (FastAPI on http://127.0.0.1:8777 plus three static files).
- `../chatwin/PROMPTS.md`: the prompt cheat sheet, one entry per scenario, in talk order.

## Setup (once)

```powershell
cd C:\Projects\harness-builder
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-notebook.txt
```

`.env` is the same file the web app uses; the notebook never prints the key.

## Start Jupyter

```powershell
.venv\Scripts\python -m jupyter lab notebooks\kestrel_desk.ipynb
# or the classic page: .venv\Scripts\python -m jupyter notebook notebooks\kestrel_desk.ipynb
```

Pick the **Python 3** kernel (it is the venv's). Run the intro's setup cell first: it imports
the harness and prints the model name.

## Each stage chapter

1. A markdown cell: the problem this stage solves and the keywords we add.
2. `def build_stage_N(...)`: the stage. Its body is the same `Agent(...)` call as
   `harness/stages.py` (a test keeps them identical).
3. `serve(build_stage_N, stage=N)`: points the chat window at this stage. The first call starts
   the server inside the notebook's own process; later calls only swap the stage. It prints
   `http://127.0.0.1:8777` and "refresh the chat window".
4. `demo(build_stage_N, "...")`: runs the stage's first scenario inline and prints the tool calls,
   denials and approvals (auto-approved in the notebook, with a note), then the reply.

Stage 4 adds `sessions = list_sessions()` and a `demo(...)` that resumes the newest session.

## The refresh rhythm

Keep the notebook and the chat window side by side. For each stage:

**run the `build_stage_N` cell → run the `serve(...)` cell → refresh the chat window → pick the
role → paste a prompt from `chatwin/PROMPTS.md`.**

The window header shows which stage it serves (`Stage 3 · Boundaries`). If it still shows the old
stage, you skipped the refresh. Changing the role or clicking **New chat** starts a fresh chat.

In the chat window:
- tool calls are single indented lines (`lookup_customer · {"name": "Acme Robotics"} ✓`); the
  reviewer subagent's own calls are indented one step further;
- a denied call is red with the reason;
- `send_proposal` shows an approval box: **Approve** or **Reject**; the run waits for you;
- **Stop** cancels the answer in flight;
- at stage 4 the left column lists **Past sessions** (title, role, messages, time): click one to
  resume it from SQLite, **New chat** starts over, **Compact now** summarizes old turns.

## Without the notebook

```powershell
.venv\Scripts\python -m chatwin --stage 3      # the same chat window, standalone, one stage
```

## Offline: the fake model

No key or no network? Set `KESTREL_FAKE_LLM=1` before starting Jupyter (or `python -m chatwin`).
`get_llm()` then returns a scripted `FakeLLM`: from stage 2 on it makes one fitting tool call,
then replies with an "Offline reply" note. The header says `offline fake model`. Good for
rehearsing the clicks, not the answers.

```powershell
$env:KESTREL_FAKE_LLM = "1"; .venv\Scripts\python -m jupyter lab notebooks\kestrel_desk.ipynb
Remove-Item Env:KESTREL_FAKE_LLM      # back to the real model
```

Optional knobs: `KESTREL_CHAT_PORT` (default 8777), `KESTREL_STATE_DIR` and
`KESTREL_WORKSPACE_DIR` (send sessions, audit log, outbox and workspace files to another folder;
the tests use these).

## Before the talk

Same as the web app: delete `.harness_state\` and everything in `workspace\` except `.gitkeep`,
so Past sessions starts empty. Then **Restart kernel and clear outputs** (the committed notebook
keeps the outputs of one real run, as a fallback to show if the endpoint is down).

Tests: `tests/test_notebook.py` runs the whole notebook headless with the fake model;
`tests/test_chatwin.py` covers the chat window's endpoints.
