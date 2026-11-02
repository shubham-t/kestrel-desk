# Kestrel Desk: build an agent harness, stage by stage

A live demo for an engineering talk on **agent harness engineering**. We start with a plain
chatbot and add one harness component per stage until it is a production-shaped agent:
context, actions, boundaries, persistence. Every component is our own code in `harness/`;
the only model dependency is the `openai` Python SDK speaking the OpenAI chat-completions
protocol, so it runs against any OpenAI-compatible endpoint.

The company (Kestrel Software), its customers, issues and revenue are fictional. No real
email is ever sent: "sending" a proposal writes a file to `.harness_state/outbox/`.

`SPEC.md` is the full contract. This file is how to run it.

## Setup (Windows, PowerShell, Python 3.12)

```powershell
cd C:\Projects\harness-builder
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env      # then put your key in .env
.venv\Scripts\python scripts\verify_offline.py
```

`verify_offline.py` needs no key and no network. It checks the company data, skills and
`AGENTS.md`, runs the test suite, and boots the web app in-process. Every line must say PASS.

## Run it

**Web app** (the demo surface): http://127.0.0.1:8765

```powershell
.venv\Scripts\python -m app.server
# or: .venv\Scripts\python -m uvicorn app.server:app --port 8765
```

`→`/`←` change stage, `Enter` opens the chat, `1`–`3` switch role, `/` opens the code and
scenarios drawer, `P` is presenter mode.

**Terminal** (same harness, events printed with their component tag):

```powershell
.venv\Scripts\python -m harness.cli --stage 3 --role finance
.venv\Scripts\python -m harness.cli --stage 4 --role sales --session <id>   # resume a session
.venv\Scripts\python -m harness.cli --list-sessions
```

Approvals are asked on stdin (`Approve send_proposal → procurement@…? [y/N]`).

**Mock mode** (rehearsal, or the fallback if the model endpoint is down on talk day): canned
metadata and scripted event streams for every scenario, no model calls, no key needed.

```powershell
$env:KESTREL_MOCK = "1"; .venv\Scripts\python -m app.server
Remove-Item Env:KESTREL_MOCK      # back to the real model
```

The top bar shows `MOCK · REHEARSAL` instead of `LIVE · <model>`, so you always know which one is up.

## Point it at another OpenAI-compatible endpoint (edit `.env` only)

Nothing outside `harness/llm.py` knows which provider is behind the URL, and `llm.py` reads
everything from `.env`. To use the internal model on the org laptop, change these lines:

```ini
LLM_BASE_URL=https://llm-gateway.internal.example/v1/   # the URL that /chat/completions hangs off
LLM_API_KEY=<internal key>
LLM_MODEL=<internal model id>
LLM_SUBAGENT_MODEL=<same id, or a cheaper one on the same endpoint>
LLM_EXTRA_HEADERS={"X-Team": "platform"}                # only if the gateway needs headers
LLM_EXTRA_BODY=                                         # clear this: it holds Anthropic-only fields
```

`LLM_EXTRA_BODY` is JSON merged into every request body for provider-specific settings. The
Anthropic setup uses `{"output_config": {"effort": "medium"}}` (medium reasoning effort for
Sonnet 5.5); clear it on an endpoint that rejects unknown fields. Defaults are `claude-sonnet-5-5`
for the agent and `claude-haiku-5-5` for the subagent.

What the endpoint must support: `POST /chat/completions` with `stream=true`, function
`tools` / streamed `tool_calls`, and `max_tokens`. The harness sends nothing else
(no `temperature`, `top_p`, `strict`, `parallel_tool_calls` or `reasoning_effort`) because
some compatible servers reject them. It asks for token usage with
`stream_options={"include_usage": true}`; usage drives the token counter and compaction.

Corporate network: `SSL_CERT_FILE` (a root CA bundle) and `HTTPS_PROXY` are honoured by the
HTTP client and can also go in `.env`. All settings are listed in `.env.example`.

Quick live check after editing `.env`: run `python -m harness.cli --stage 0` and say hello.
If the endpoint fails, the error appears as an `[error] Model endpoint returned 4xx: …` line
(the key is never printed).

## What each stage adds

Every stage is one `Agent(...)` call in `harness/stages.py`; each component is one keyword.
The web app's code panel shows that call, cut from the running source.

| Stage | Component | New `Agent(...)` keywords | What it adds |
|---|---|---|---|
| 0 Chatbot | model | `model` | A system prompt, a message list, one streamed model call. No tools, no memory. |
| 1 Context | context | `instructions`, `skills` | `company/AGENTS.md` as the always-on prompt; skills listed by name and loaded on demand with `load_skill`. |
| 2 Actions | actions | `tools`, `middleware`, `subagents` | Four company tools (`@tool`), the agent loop, `CallLimit` and `TodoTracker` middleware, a `proposal-reviewer` subagent. |
| 3 Boundaries | boundaries | `permissions`, `approve`, `protected_paths`, `audit` | `RoleGate` per role, protected paths, human approval for `send_proposal`, an audit log. Enforced in code, not in the prompt. |
| 4 Persistence | persistence | `checkpointer`, `workspace`, `compaction` | SQLite checkpoints with resume, a writable `workspace/` with file tools, a `Compactor` that summarizes old turns. |

Roles: **sales** may use `lookup_customer`, `send_proposal`; **engineering** `lookup_customer`,
`lookup_issue`; **finance** `lookup_customer`, `get_revenue` (`ROLE_TOOLS` in `harness/middleware.py`).

## Scenarios (the demo script)

Each is a **Run** button in the web app's Scenarios drawer.

| Stage | Title | Role | Prompt | Watch |
|---|---|---|---|---|
| 0 | Does it know us? | sales | What do you know about Kestrel Software and our proposal process? | The model guesses or admits it doesn't know. Nothing lights up but the model. |
| 1 | Skill-guided draft | sales | Use the proposal-writing skill to draft a proposal for Acme Robotics: Enterprise plan, 40 seats, they care about SSO and audit logs. | `load_skill` fires (Context), and the draft follows the skill's sections. We still had to explain who Acme is. |
| 2 | Look it up yourself | sales | Draft a proposal for Acme Robotics and have the proposal-reviewer check it before you show it to me. | `lookup_customer`, a todo list, then the subagent's nested review. |
| 2 | Runaway loop | engineering | For every open issue, look up its customer, then look up every other issue for that customer, and keep going until you have checked everything twice. | `CallLimit` stops it. |
| 3 | Wrong role | engineering | What was our revenue in FY2026? | `RoleGate` denies `get_revenue`; the model says so instead of guessing. |
| 3 | Right role | finance | What was our revenue in FY2026? | Same question, allowed, answered with record ids. |
| 3 | Needs a human | sales | Draft a short Enterprise proposal for Acme Robotics (40 seats, SSO and audit logs) and send it to procurement@acme-robotics.example with the subject "Kestrel Enterprise proposal". | The approval card appears and the loop waits; approve → outbox file and an audit line. Variant: send to ceo@acme-robotics.example and the tool rejects the unverified address. |
| 4 | Save it | sales | Draft a short Enterprise proposal for Acme Robotics (40 seats, SSO and audit logs) and save it as workspace/acme-proposal.md. Give me the path. | `write_workspace_file` (Persistence); `checkpoint` events. Also show a write to `company/AGENTS.md` being blocked. |
| 4 | Come back tomorrow | sales | *(resume the previous session)* What did we save earlier, and what was in it? | Resumed history answers without re-reading. Then trigger compaction on a long session and show the summary marker. |

## Talk-day checklist

The day before
- [ ] On the talk laptop: `pip install -r requirements.txt` (do this on the org network, not at the venue).
- [ ] Edit `.env` for the internal endpoint (section above). Confirm `LLM_MODEL` and `LLM_SUBAGENT_MODEL` exist there.
- [ ] `python scripts\verify_offline.py` → every line PASS.
- [ ] `python scripts\live_smoke.py` → runs all nine scenarios against the real endpoint and prints PASS/FAIL for what the audience should see (costs real tokens; `live_smoke.py 3` runs one stage).
- [ ] Rehearse every scenario once in the web app. Rehearse once in mock mode too.

One hour before
- [ ] Start fresh: delete `.harness_state\` (sessions, audit log, outbox) and any files in `workspace\` except `.gitkeep`.
- [ ] Start the web app; the top bar must say `LIVE · <model>`. Run the stage 0 scenario once to warm up the endpoint.
- [ ] Browser zoom so the code panel is readable from the back row; press `P` for presenter mode.
- [ ] Close anything that shows `.env`. The key is never printed by the app.

During the talk
- [ ] Stage 4 "Come back tomorrow": to make the point, reload the page (or restart the server) after "Save it", then use the Sessions list in the drawer (or `--session <id>` in the terminal) to resume the "Save it" session before running the scenario. Without a reload it simply continues the open session, which also works.
- [ ] Compaction triggers at `KESTREL_COMPACT_AT_TOKENS` (6000 by default); the **Compact now** button forces it.

If the endpoint is down: stop the server, `$env:KESTREL_MOCK = "1"`, start it again. The demo
script runs unchanged on scripted events.

## Repo map

```
harness/       the harness (Agent, @tool, middleware, approvals, persistence, stages)
  stages.py    the five stages, one Agent(...) call each: read this file during the talk
  loop.py      the agent loop; talk.py holds headlines, problems, scenarios, snippet extraction
company/       AGENTS.md and synthetic data (customers, issues, revenue)
skills/        proposal-writing, issue-triage, revenue-brief (SKILL.md with frontmatter)
workspace/     the only folder the agent may write into
app/           FastAPI server and the browser UI (no CDN, no web fonts)
deck/          the slide deck
tests/         offline pytest suite (FakeLLM, no network)
scripts/       verify_offline.py (no key, no network) and live_smoke.py (every scenario against the real model)
```

Runtime state lives in `.harness_state/` (SQLite sessions, `audit.jsonl`, `outbox/`), which is git-ignored.
