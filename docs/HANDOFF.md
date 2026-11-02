# Handoff: setting up Kestrel Desk on the org laptop

This file is written for a coding agent (or a person) who has never seen this repository
and has to get the live demo running on a locked-down corporate laptop against an internal,
OpenAI-compatible model endpoint, then rehearse it. Read it top to bottom before touching
anything. `README.md` has the day-to-day commands; `SPEC.md` is the design contract.

## 1. What this is

An internal engineering talk, "Agent harness engineering", with a live demo. The demo app,
**Kestrel Desk**, is an internal assistant for a fictional company (Kestrel Software: sales,
engineering, finance). It grows from a chatbot to an agent in five stages, one harness
component per stage:

| Stage | Component | `Agent(...)` keywords added | What the audience sees |
|---|---|---|---|
| 0 | Chatbot | `model` | A plain model call. It knows nothing about the company. |
| 1 | Context | `instructions` | `company/AGENTS.md` as the system prompt. Prices, rules, tone. |
| 2 | Actions | `tools`, `middleware`, `skills`, `subagents` | Company tools, the agent loop, `CallLimit`, skills loaded on demand, a reviewer subagent. |
| 3 | Boundaries | `permissions`, `approve`, `audit` | Role gate, human approval before sending, audit log. |
| 4 | Persistence | `checkpointer`, `workspace`, `compaction` | SQLite sessions in a sidebar, a writable `workspace/`, compaction. |

Everything is our own code under `harness/`. Each stage is literally one `Agent(...)` call in
`harness/stages.py`; the web app shows that call on screen, cut from the running source by the
`# [stage:N]` marker comments. The talk's slide deck (`deck/`) shows the same snippets.

The one external dependency for model access is the `openai` Python SDK speaking the
OpenAI chat-completions protocol. **Only `harness/llm.py` talks to a provider.** Everything
provider-specific is configured in `.env`.

## 2. What the org laptop must provide

- Python 3.12 (3.11 may work; 3.12 is what was tested).
- `pip install` access to PyPI (or a mirror) for the six packages in `requirements.txt`.
- An OpenAI-compatible endpoint that supports **`POST /chat/completions` with `stream=true`,
  function `tools`, streamed `tool_calls` deltas, `max_tokens`, and `stream_options={"include_usage": true}`**
  (usage is used for the token counter and compaction; if the endpoint never sends usage, the
  harness still works but shows 0 tokens and compaction has to be forced with the button).
- A browser (Chrome or Edge). The web app loads **no** CDN scripts, web fonts or external
  images, so it runs with the network off except for the model endpoint.
- PowerPoint for `deck/Kestrel-Desk-Harness-Engineering.pptx` (preview grids are in `deck/preview/`).

No Node.js, no Docker, no database server. State is one SQLite file under `.harness_state/`.

## 3. Setup, in order

```powershell
git clone https://github.com/shubham-t/kestrel-desk.git
cd kestrel-desk
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` (this is the whole provider switch; nothing else changes):

```ini
LLM_BASE_URL=https://<internal-gateway>/v1/        # the base the endpoint's /chat/completions hangs off
LLM_API_KEY=<internal key>
LLM_MODEL=<internal model id, exactly as the endpoint names it>
LLM_SUBAGENT_MODEL=<same id, or a cheaper one on the same endpoint>
LLM_EXTRA_BODY=                                    # CLEAR IT: the default holds an Anthropic-only field
LLM_EXTRA_HEADERS=                                  # only if the gateway needs headers, as one-line JSON
```

If the corporate network needs it: `SSL_CERT_FILE=<path to the root CA bundle>` and/or
`HTTPS_PROXY=...` also go in `.env`; the HTTP client honours both.

Then verify, in this order, stopping at the first failure:

```powershell
.venv\Scripts\python scripts\verify_offline.py        # no key, no network: data, skills, 116 tests, web app boots. Every line PASS.
.venv\Scripts\python -m harness.cli --stage 0          # type "hello": one live reply proves URL, key and model id.
.venv\Scripts\python -m harness.cli --stage 3 --role finance
#   type: What was our revenue in FY2026?              # proves tool calling: a get_revenue call, then an answer with record ids.
.venv\Scripts\python scripts\live_smoke.py             # every demo scenario against the real endpoint, PASS/FAIL per check (costs tokens).
.venv\Scripts\python -m app.server                     # http://127.0.0.1:8765 ; the top bar must read LIVE · <your model id>
```

`live_smoke.py` prints what the audience is supposed to see for each scenario and asserts it
(the role gate denies, the approval request fires, the limit trips, the saved session resumes).
28 checks should pass. Run `live_smoke.py 3` to run one stage.

## 4. If the endpoint misbehaves

Symptoms and where to look. All fixes live in `harness/llm.py` (the `OpenAICompatibleLLM`
class) or `.env`; do not patch the loop or the tools for provider quirks.

| Symptom | Likely cause | Fix |
|---|---|---|
| `[error] Model endpoint returned 400` on the first call | the endpoint rejects a field | clear `LLM_EXTRA_BODY`; if it still fails, the request sends only `model, messages, max_tokens, stream, stream_options, tools`: drop `stream_options` in `llm.py` if the server rejects it |
| 401 / 403 | key or header | `LLM_API_KEY`, `LLM_EXTRA_HEADERS` |
| 404 | wrong base URL | `LLM_BASE_URL` must be the prefix of `/chat/completions` (usually ends in `/v1/`) |
| Replies arrive but no tool rows ever appear | the endpoint doesn't support function tools, or streams them in a non-standard shape | check with `--stage 3 --role finance`; inspect the raw deltas in `llm.py`'s accumulation loop; the harness expects OpenAI-style `delta.tool_calls[i].function.{name,arguments}` with `index` |
| Tokens show 0 in/0 out | no `usage` in the stream | harmless; compaction is forced with **Compact now** |
| Model refuses or hedges where the script expects an action | a weaker model | rehearse once; the prompts are in `harness/talk.py` and may be tightened, but keep the titles and the component each one demonstrates |
| Certificate errors | corporate TLS inspection | `SSL_CERT_FILE` in `.env` |

If the endpoint is down on talk day: `$env:KESTREL_MOCK = "1"` before starting the server.
The top bar reads `MOCK · REHEARSAL` and every scenario replays a scripted event stream.

## 5. The talk flow (what the presenter does)

Browser full screen, `P` for presenter mode. Keys: `→`/`←` change stage, `Enter` opens the
chat, `/` opens the code-and-scenarios drawer, `1`–`3` switch role, `Esc` closes or stops.

For each stage: the "Add stage" screen (problem, component cards, the `Agent(...)` call with
new keywords marked) → **Open the chat** → `/` → **Scenarios** → **Run**. The 13 scenarios
tell one story, the Acme Robotics renewal (full table in `README.md`, "Scenarios"). Stage 3's
"Send it" pauses on an approval card: click **Approve and send**. Stage 4 shows the sessions
sidebar; "Pick up yesterday's work" resumes the saved session by itself; "Long day" is the
**Compact now** card.

Before the talk: delete `.harness_state\` (sessions, audit log, outbox) and everything in
`workspace\` except `.gitkeep`, so the sidebar and the workspace start empty.

## 6. Do not change these

- The visual design (`app/static/`): approved by the presenter; light paper theme, centered
  chatbox, system fonts, no network assets.
- The scenario titles, roles and prompts in `harness/talk.py`, and the stage keywords in
  `harness/stages.py`: the slide deck quotes them.
- The `# [stage:N] ... # [/stage:N]` marker comments: the UI and the deck extract code through them.
- The lightness rule from `SPEC.md`: every stage stays one `Agent(...)` call; tools stay
  `@tool` functions of ~10 lines; no framework gets added.
- Never commit `.env`, `.harness_state/`, `workspace/*` (all git-ignored) or print the key.

## 7. Repo map

```
harness/      the harness: stages.py (five Agent(...) calls), loop.py (the agent loop), middleware.py,
              tools*.py (@tool functions), subagents.py, approvals.py, persistence.py (SQLite),
              compaction.py, context.py, llm.py (THE provider seam), talk.py (scenarios, stage text, snippets)
company/      AGENTS.md (the always-on company file) and synthetic data (customers, issues, revenue)
skills/       SKILL.md files loaded on demand from stage 2
app/          FastAPI server + vanilla JS UI; mock.py / mock_data.py = rehearsal mode
deck/         the .pptx, its build script (node; not needed on the laptop), preview grids
tests/        116 offline tests (FakeLLM); scripts/verify_offline.py runs them plus data checks
scripts/      verify_offline.py, live_smoke.py
docs/         this file
```

## 8. Rebuilding the deck (optional, needs Node.js)

The deck is generated by `deck/build_deck.js` with pptxgenjs and reads the snippets from the
harness at build time. It is already built and committed; rebuild only if code snippets
change. `deck/outline.md` lists every slide with speaker notes.
