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

## Notebook version

A second format, closer to the reference video: `notebooks/kestrel_desk.ipynb` has one code
cell per stage (the same `Agent(...)` call as `harness/stages.py`), and a plain chat window
(`chatwin/`, http://127.0.0.1:8777) that the notebook points at each stage with
`serve(build_stage_N, stage=N)`; you refresh the window after each stage. Prompts are in
`chatwin/PROMPTS.md`. Setup, the refresh rhythm and the offline fake model:
[`notebooks/README.md`](notebooks/README.md).

```powershell
.venv\Scripts\python -m pip install -r requirements-notebook.txt
.venv\Scripts\python -m jupyter lab notebooks\kestrel_desk.ipynb
.venv\Scripts\python -m chatwin --stage 3      # the chat window alone, no notebook
```

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
| 1 Context | context | `instructions` | `company/AGENTS.md` as the always-on system prompt: company facts, plans and prices, business rules. Nothing else: no tool, no loop; the request is identical to stage 0 except the system prompt. |
| 2 Actions | actions | `tools`, `middleware`, `skills`, `subagents` | Five company tools (`@tool`: `list_customers`, `lookup_customer`, `lookup_issue`, `get_revenue`, `send_proposal`) and the agent loop; skills on demand (listed by name in the prompt, body pulled with `load_skill`: context the model *pulls* instead of context we *push*); `CallLimit` middleware; a `proposal-reviewer` subagent. |
| 3 Boundaries | boundaries | `permissions`, `approve`, `audit` | `RoleGate` per role, human approval for `send_proposal`, an audit log. Enforced in code, not in the prompt. Chain: `RoleGate, ApprovalGate, CallLimit, AuditLog`. |
| 4 Persistence | persistence | `checkpointer`, `workspace`, `compaction` | SQLite checkpoints with a sessions sidebar (list, resume, new task), a writable `workspace/` whose file tools refuse any path outside it, a `Compactor` that summarizes old turns. |

Roles: every role may use `list_customers` and `lookup_customer`; on top of that **sales** may use
`send_proposal`, **engineering** `lookup_issue`, **finance** `get_revenue` (`ROLE_TOOLS` in `harness/middleware.py`).
Roles only matter from stage 3, when `permissions=ROLE_TOOLS` installs `RoleGate`.

## Scenarios (the demo script)

One story runs through the talk: the **Acme Robotics renewal**. Each scenario is a **Run** button
in the web app's Scenarios drawer, needs only the component being introduced, and repeats an
earlier prompt where a before/after helps.

| Stage | Title | Role | Prompt | Watch |
|---|---|---|---|---|
| 0 | Who's Acme? | sales | Who is Acme Robotics and when is their renewal due? | It can't know. Nothing is around the model. |
| 0 | Price the renewal | sales | Draft a renewal proposal for Acme Robotics: 40 seats on our Enterprise plan, with pricing. | It invents a price, or asks for one. It has no idea what our plans cost. |
| 1 | Price the renewal, again | sales | *(same prompt as stage 0)* Draft a renewal proposal for Acme Robotics: 40 seats on our Enterprise plan, with pricing. | Plan-table price ($2,400 per seat per year), our tone, our sections, no discount. Tokens in jumped: AGENTS.md rides on every call. We still had to say who Acme is. |
| 1 | Can I discount? | sales | Can I offer Acme 15% off to close this quarter? | "No: above 10% needs written approval from finance", straight from AGENTS.md. A business rule, not a fact. |
| 2 | Prepare the renewal | sales | Prepare Acme Robotics' renewal proposal: check their record and open issues, then have the proposal-reviewer check it before you show it to me. | `load_skill` pulls the playbook, `lookup_customer` and `lookup_issue` pull the facts, the reviewer runs as a nested subagent. The model fetched what it needed. |
| 2 | Account health, every customer | engineering | Give me an account health report for every customer: their record plus their open issues. | A realistic over-sized request. `CallLimit` denies the 11th tool call; the model reports partial results and says why. |
| 3 | Wrong role | engineering | What was our revenue in FY2026? | `RoleGate` denies `get_revenue`, in code, before it runs; the model says so instead of guessing. |
| 3 | Right role | finance | What was our revenue in FY2026? | Same question, allowed, answered with record ids. |
| 3 | Send it | sales | Draft a short renewal proposal for Acme Robotics (40 seats, Enterprise, SSO and audit logs) and send it to procurement@acme-robotics.example with the subject "Kestrel renewal proposal". | The approval card appears and the loop waits. Approve → outbox file + audit line. Variant: send to ceo@acme-robotics.example and the tool rejects the address as not on record. |
| 4 | Save the draft | sales | Draft a short renewal proposal for Acme Robotics (40 seats, Enterprise, SSO and audit logs), save it as workspace/acme-renewal.md, and add a line to company/AGENTS.md saying the Acme draft is done. | `write_workspace_file` writes the draft and checkpoints tick up; the AGENTS.md write is refused by the tool (outside `workspace/`), and the model reports it. |
| 4 | Pick up yesterday's work | sales (`resume=True`) | Where did we leave off with Acme, and what did we save? | Run resumes the most recent saved session from SQLite (the divider says so) and answers from history. In the sidebar the session is highlighted. |
| 4 | Long day | sales | *(the **Compact now** button, no prompt)* | 9 → 7 messages, a compaction row with the summary. |

## Talk-day checklist

The day before
- [ ] On the talk laptop: `pip install -r requirements.txt` (do this on the org network, not at the venue).
- [ ] Edit `.env` for the internal endpoint (section above). Confirm `LLM_MODEL` and `LLM_SUBAGENT_MODEL` exist there.
- [ ] `python scripts\verify_offline.py` → every line PASS.
- [ ] `python scripts\live_smoke.py` → runs every prompt scenario against the real endpoint ("Long day" is a UI button and is skipped; "Pick up yesterday's work" resumes the "Save the draft" session) and prints PASS/FAIL for what the audience should see (costs real tokens; `live_smoke.py 3` runs one stage).
- [ ] Rehearse every scenario once in the web app. Rehearse once in mock mode too.

One hour before
- [ ] Start fresh: delete `.harness_state\` (sessions, audit log, outbox) and any files in `workspace\` except `.gitkeep`.
- [ ] Start the web app; the top bar must say `LIVE · <model>`. Run the stage 0 scenario once to warm up the endpoint.
- [ ] Browser zoom so the code panel is readable from the back row; press `P` for presenter mode.
- [ ] Close anything that shows `.env`. The key is never printed by the app.

During the talk
- [ ] Stage 4 "Pick up yesterday's work": run it after "Save the draft". Its **Run** resumes the most recent saved stage-4 session from SQLite (a `RESUMED SESSION … FROM SQLITE` divider appears) and then asks where we left off. To make the point harder, reload the page or restart the server first; or click the "Save the draft" session in the Sessions sidebar to resume it by hand (`--session <id>` in the terminal).
- [ ] Stage 4 "Long day": its Run is the **Compact now** button (no prompt); it forces the `Compactor` on the open session. Compaction also triggers by itself at `KESTREL_COMPACT_AT_TOKENS` (6000 by default).

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
