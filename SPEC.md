# Harness Builder — shared spec (v2, hand-built harness)

A live-demo project for an internal engineering talk on **agent harness engineering**.
We go from a plain chatbot to a production-shaped agent by adding one harness component per
stage. **Everything in the harness is our own code** (the point of the talk); the only
model dependency is the `openai` Python SDK speaking the OpenAI chat-completions protocol.

Today it runs against Anthropic's OpenAI-compatible endpoint
(`base_url=https://api.anthropic.com/v1/`, model `claude-opus-5-5`). On the presenter's
org laptop it will run against an internal OpenAI-compatible endpoint by changing **only**
`.env`. Nothing outside `harness/llm.py` may know which provider is behind the URL.

Every piece of code in this repo follows this document. If something here is impossible
or wrong, do the closest right thing and say so in your final report.

## The story

Company: **Kestrel Software**, a mid-size B2B SaaS vendor (fictional; synthetic data only).
Internal assistant: **Kestrel Desk**. Teams: **sales**, **engineering**, **finance**.

Five cumulative stages. Stage N contains everything stage N-1 had.

| Stage | Name | Component | What it adds |
|---|---|---|---|
| 0 | Chatbot | model | A system prompt, a message list, one model call. No tools, no memory. |
| 1 | Context | context | `company/AGENTS.md` as the always-on system prompt; **skills** (`skills/*/SKILL.md`) listed by name/description in the prompt and loaded on demand with a `load_skill` tool. |
| 2 | Actions | actions | Four company tools; the **agent loop** (model → tool calls → results → model …); **middleware** (`CallLimit`, `TodoTracker`); a **subagent** (`proposal-reviewer`) the main agent can delegate to. |
| 3 | Boundaries | boundaries | **Role permissions** (`RoleGate` middleware), **protected paths**, **human approval** (`send_proposal` pauses for approve/reject), **audit log**. Enforced in code, not in the prompt. |
| 4 | Persistence | persistence | **SQLite checkpoints** (list, resume, continue a conversation later); a **writable workspace** with file tools; **context compaction** (`Compactor` middleware summarizes old turns when the prompt grows). |

## Repo layout (fixed — do not rename)

```
harness-builder/
  SPEC.md                         this file
  README.md                       (core agent) how to run, how to point at another endpoint, talk-day checklist
  requirements.txt                (core agent) openai>=2, fastapi, uvicorn[standard], python-dotenv, pytest, pytest-asyncio
  .env.example                    (core agent) see Config
  .gitignore                      (core agent) .venv/ .env .harness_state/ workspace/* !workspace/.gitkeep __pycache__/ .pytest_cache/
  company/
    AGENTS.md                     (core agent) company facts + working conventions (~60 lines)
    data/customers.json           (core agent) 7 customers: id, name, industry, plan, seats, arr_usd, contact_name, contact_email, renewal_date, notes
    data/issues.json              (core agent) 10 issues: id, customer_id, title, severity (S1–S4), status, component, opened, summary
    data/revenue.json             (core agent) quarterly revenue by product line FY2025–FY2026, ARR by plan, a one-line "source" note
  skills/
    proposal-writing/SKILL.md     (core agent) company-wide: required sections, tone, what never to promise
    issue-triage/SKILL.md         (core agent) engineering: severity rubric, triage steps, output format
    revenue-brief/SKILL.md        (core agent) finance: how to summarize revenue, always cite record ids
  workspace/.gitkeep              (core agent) the ONLY folder the agent may write into
  harness/                        (core agent) the Python package — see Module contracts
    __init__.py  config.py  llm.py  context.py  tools.py  middleware.py
    subagents.py  approvals.py  loop.py  persistence.py  stages.py  cli.py
  tests/                          (core agent) pytest, offline, FakeLLM-driven
    test_tools.py  test_middleware.py  test_loop.py  test_persistence.py  test_stages.py
  scripts/verify_offline.py       (core agent) one command, PASS/FAIL per check, exit 1 on failure
  app/                            (web agent)
    server.py
    static/index.html  static/app.js  static/styles.css  static/highlight.js
  deck/                           (deck agent) Kestrel-Desk-Harness-Engineering.pptx + outline.md — same paper/forest look as the app
```

## Config (`harness/config.py`)

Loaded with `python-dotenv` from `.env` at `REPO_ROOT`. Dataclass `Settings` (frozen), module-level `settings = Settings.load()`.

| env var | default | meaning |
|---|---|---|
| `LLM_BASE_URL` | `https://api.anthropic.com/v1/` | OpenAI-compatible base URL. **The portability seam.** |
| `LLM_API_KEY` | falls back to `ANTHROPIC_API_KEY`, then `OPENAI_API_KEY` | bearer key |
| `LLM_MODEL` | `claude-opus-5-5` | main agent model id |
| `LLM_SUBAGENT_MODEL` | `claude-sonnet-5-5` | cheaper model for subagents |
| `LLM_MAX_TOKENS` | `4096` | per call |
| `LLM_EXTRA_HEADERS` | empty | JSON object; e.g. `{"anthropic-workspace-id": "..."}` |
| `KESTREL_COMPACT_AT_TOKENS` | `6000` | prompt-token threshold that triggers compaction (low on purpose so the demo shows it) |
| `KESTREL_KEEP_LAST_MESSAGES` | `6` | messages kept verbatim after compaction |

Paths: `REPO_ROOT`, `COMPANY_DIR`, `DATA_DIR`, `SKILLS_DIR`, `WORKSPACE_DIR`, `STATE_DIR=REPO_ROOT/.harness_state`, `DB_PATH=STATE_DIR/kestrel.sqlite`, `OUTBOX_DIR=STATE_DIR/outbox`, `AUDIT_LOG=STATE_DIR/audit.jsonl`. `ensure_dirs()`.
`ROLES = ("sales","engineering","finance")`. `STAGES` = list of `StageInfo(id, name, component, tagline)`.
If no API key is present, `settings.api_key` is `None`; `llm.py` raises `ConfigError("Set LLM_API_KEY (or ANTHROPIC_API_KEY) in .env")` only when a real call is attempted, so offline tests and the UI's meta endpoint still work.

## Lightness rule (the presenter's explicit ask)

The code the audience sees must look as light as the YouTube demo it is modelled on, where
each component was one keyword argument on `create_deep_agent(...)`. So:

- The public API is **one constructor, `Agent(...)`, with one keyword per component**.
  Every stage in `stages.py` is a single `return Agent(...)` call of **3–8 lines**. The loop,
  middleware chain, approvals, and checkpointing are wired *inside* `Agent.__init__` from
  those keywords; the audience never has to read them to follow along.
- Tools are declared with an **`@tool` decorator** that infers the JSON schema from type
  hints and the docstring, so a tool is ~8 lines.
- Each stage's "what we added" is **1–3 snippets, each ≤ 20 lines**: the `Agent(...)` call
  for that stage plus at most two tiny supporting definitions (a tool, a `SubagentDef`, the
  `ROLE_TOOLS` dict). Internals (`loop.py`, `middleware.py` bodies) are never snippets.
- Internals may be as thorough as needed, but they stay out of sight and under ~300 lines per file.

```python
# what stages.py looks like, end to end (illustrative — write the real thing)
def build_agent(stage, role, *, session_id=None, approvals=None, llm=None, store=None):
    llm = llm or make_llm()
    common = dict(role=role, session_id=session_id, approvals=approvals)
    if stage == 0:
        # [stage:0] A chatbot: a model and a prompt
        return Agent(model=llm, **common)
        # [/stage:0]
    if stage == 1:
        # [stage:1] Context: company instructions and skills
        return Agent(model=llm, instructions=COMPANY_DIR / "AGENTS.md", skills=SKILLS_DIR, **common)
        # [/stage:1]
    if stage == 2:
        # [stage:2] Actions: tools, a loop with middleware, a subagent
        return Agent(model=llm, instructions=COMPANY_DIR / "AGENTS.md", skills=SKILLS_DIR,
                     tools=COMPANY_TOOLS, middleware=[CallLimit(), TodoTracker()],
                     subagents=[PROPOSAL_REVIEWER], **common)
        # [/stage:2]
    ...
```

### `Agent(...)` keywords (in `loop.py`)

| keyword | type | installs |
|---|---|---|
| `model` | `LLM \| str \| None` | a `str` is a model id → `make_llm(model)`; `None` → `make_llm()` |
| `instructions` | `str \| Path` | system prompt; a `Path` is read at construction. Default `"You are a helpful assistant."` |
| `skills` | `Path \| None` | `discover_skills(dir)` → skills index appended to the prompt + `load_skill` tool |
| `tools` | `list[Tool]` | registered as-is |
| `middleware` | `list[Middleware]` | appended after the ones installed by the keywords below |
| `subagents` | `list[SubagentDef]` | `run_subagent` tool |
| `permissions` | `dict[str, set[str]] \| None` | `RoleGate(permissions)`; also appends the role line to the prompt |
| `approve` | `set[str]` | `ApprovalGate(names)` |
| `protected_paths` | `list[Path]` | `ProtectedPaths(paths)` |
| `audit` | `bool` | `AuditLog()` |
| `checkpointer` | `SessionStore \| None` | history saved after every message; resumed if `session_id` exists |
| `workspace` | `Path \| None` | workspace file tools + the "save under workspace/" prompt line |
| `compaction` | `Compactor \| None` | the compaction middleware (`Compactor(at_tokens=…, keep_last=…)`) |
| `role`, `session_id`, `approvals` | | run context; `approvals` defaults to `AutoReject()` |

Middleware order when several are installed: `RoleGate, ProtectedPaths, ApprovalGate, *user middleware, AuditLog, Compactor`.

### `@tool` decorator (in `tools.py`)

```python
@tool(component="actions")                         # read_only=True by default; requires_approval=False
async def lookup_customer(name: str, ctx: RunContext) -> str:
    """Look up a Kestrel customer by (partial) company name."""
    ...
```
Schema: parameters from the signature (`str`, `int`, `float`, `bool`, `list[...]`, `dict` →
JSON Schema; every param without a default is required; `ctx` is injected, never exposed).
Description = the docstring's first paragraph; per-parameter descriptions may come from an
`Args:` section if present. The decorated name is the tool name.

## Module contracts (`harness/`)

### `llm.py` — the only file that talks to a model provider

```python
@dataclass
class ToolSpec:            # provider-neutral tool definition
    name: str; description: str; parameters: dict        # JSON Schema object

@dataclass
class ToolCall:  id: str; name: str; arguments: dict      # arguments already json-parsed; {} on parse failure + raw kept in .raw_arguments

@dataclass
class LLMChunk:            # streamed delta
    text: str = ""                                        # text delta
    tool_calls: list[ToolCall] | None = None              # only on the final chunk
    usage: Usage | None = None                            # only on the final chunk
    finish_reason: str | None = None                      # only on the final chunk

@dataclass
class Usage: prompt_tokens: int; completion_tokens: int

class LLM(Protocol):
    model: str
    async def stream(self, messages: list[dict], tools: list[ToolSpec] | None) -> AsyncIterator[LLMChunk]: ...

class OpenAICompatibleLLM(LLM):
    def __init__(self, *, model: str, base_url: str, api_key: str | None, max_tokens: int, extra_headers: dict | None)
    # uses openai.AsyncOpenAI(base_url=..., api_key=..., default_headers=...)
    # chat.completions.create(model, messages, tools=[{"type":"function","function":{...}}] or omitted, stream=True, stream_options={"include_usage": True}, max_tokens)
    # DO NOT send temperature/top_p/strict/parallel_tool_calls/reasoning_effort — some providers 400 on them, Anthropic ignores or rejects them.
    # Accumulate tool_call deltas by index; json.loads arguments at the end.
    # Convert openai.APIStatusError / APIConnectionError into LLMError(message, status) so the loop can surface it as an Event.

class FakeLLM(LLM):
    """Scripted responses for tests and the offline verify script. Each script item is either a str (text reply) or a list[ToolCall]. Pops one per call; raises if exhausted. Records every messages/tools payload it received in .calls for assertions."""

def make_llm(model: str | None = None) -> OpenAICompatibleLLM     # from settings
```

Messages are plain OpenAI-shaped dicts throughout the codebase: `{"role":"system"|"user"|"assistant"|"tool", "content": str|None, "tool_calls": [...], "tool_call_id": ...}`. The assistant message that carries tool calls must be appended **before** the `tool` results, one `tool` message per call, in the same order as the calls.

### `context.py`

```python
def load_agents_md() -> str                                   # company/AGENTS.md text
@dataclass
class Skill: name: str; description: str; body: str; path: Path
def discover_skills() -> list[Skill]                          # parse YAML-ish frontmatter (--- name: / description: ---); body = rest
def skills_index_text(skills) -> str                          # "Available skills (load with load_skill):\n- proposal-writing: …"
def build_system_prompt(stage: int, role: str, skills: list[Skill]) -> str
    # stage 0: "You are a helpful assistant."
    # stage ≥1: AGENTS.md + "\n\nCurrent user: role={role}." + skills index
    # stage ≥3: + "Tools outside the user's role are blocked by the harness; if a request needs one, say so plainly instead of guessing."
    # stage ≥4: + "You can save files under workspace/. When you save something, tell the user the path. Earlier turns may appear as a '[Conversation summary]' message."
```

### `tools.py`

```python
@dataclass
class Tool:
    name: str; description: str; parameters: dict
    handler: Callable[[dict, "RunContext"], Awaitable[str]]   # returns the tool result text; raise ToolError(msg) for failures
    component: str                                            # "context"|"actions"|"persistence" — which harness node lights up in the UI
    read_only: bool = True
    requires_approval: bool = False
    def spec(self) -> ToolSpec

class ToolError(Exception): ...
class ToolRegistry:  add(tool), get(name), specs() -> list[ToolSpec], names() -> list[str], __contains__

# Company tools (component="actions"):
lookup_customer(name)                     case-insensitive substring on customers.json; exact match wins; returns pretty JSON; ToolError if none
lookup_issue(query)                       by id, or substring on title / customer name; returns list
get_revenue(period)                       "FY2026" | "FY2026-Q2" | "ARR"; returns the slice + the source note
send_proposal(customer_id, to_email, subject, body_markdown)   requires_approval=True, read_only=False
                                          to_email must equal the customer's contact_email (ToolError "Unverified address: … is not the contact on record (…)")
                                          writes OUTBOX_DIR/<UTC ts>_<customer_id>.md with a header; returns "Queued to outbox: <path>". No real email, ever.
# Context tool (component="context"):
load_skill(name)                          returns the SKILL.md body; ToolError listing valid names
# Workspace tools (component="persistence", stage 4):
write_workspace_file(path, content)       read_only=False; path relative to workspace/; resolve + is_relative_to(WORKSPACE_DIR) else ToolError; mkdir parents
read_workspace_file(path)
list_workspace_files()
# Planning tool (component="actions", installed by TodoTracker middleware):
update_todos(items: list[{text, status: "pending"|"in_progress"|"done"}])   stores into RunContext.state["todos"]; returns "ok (n items)"
# Delegation tool (component="actions", installed by subagents.py):
run_subagent(name, task)                   see subagents.py
```

`RunContext` (defined in `loop.py`, imported by tools via TYPE_CHECKING): `role`, `stage`, `session_id`, `state: dict`, `emit(event)`.

### `middleware.py`

```python
@dataclass
class Decision:
    action: Literal["allow", "deny", "ask"]; reason: str = ""; component: str = "boundaries"

class Middleware:                                    # base class; all methods default to no-op / allow
    name: str; component: str
    async def before_model(self, messages: list[dict], ctx) -> list[dict]      # may return a modified copy (compaction does)
    async def after_model(self, assistant_msg: dict, usage: Usage | None, ctx) -> None
    async def before_tool(self, call: ToolCall, tool: Tool, ctx) -> Decision
    async def after_tool(self, call: ToolCall, tool: Tool, result: str, ok: bool, ctx) -> None
    def tools(self) -> list[Tool]                                              # tools a middleware installs (TodoTracker → update_todos)

class CallLimit(Middleware):          component="actions";  max_model_calls=8, max_tool_calls=10 (low on purpose so the 'Runaway loop' scenario trips it) → deny with a reason that names the limit; counts live in ctx.state["calls"]
class TodoTracker(Middleware):        component="actions";  installs update_todos; emits Event("todo_update") when it changes
class RoleGate(Middleware):           component="boundaries"; ROLE_TOOLS below; deny if tool.component=="actions" company tool and name ∉ ROLE_TOOLS[ctx.role]; reason: "Role '{role}' is not allowed to use {tool}. Allowed: …"
class ProtectedPaths(Middleware):     component="boundaries"; for tools with a `path` argument and read_only=False: deny unless resolved path is inside WORKSPACE_DIR; also deny any path whose resolved form is under COMPANY_DIR, SKILLS_DIR, REPO_ROOT/harness, REPO_ROOT/app
class ApprovalGate(Middleware):       component="boundaries"; for tool.requires_approval → Decision("ask") (the loop then goes through approvals.py)
class AuditLog(Middleware):           component="boundaries"; after_tool appends {ts, session_id, role, tool, args (truncated 300 chars), ok, decision} to AUDIT_LOG; emits Event("audit")
class Compactor(Middleware):          component="persistence"; in before_model: if ctx.state.get("last_prompt_tokens",0) > settings.compact_at_tokens and len(messages) > keep_last+2 → summarize messages[1:-keep_last] with one extra LLM call ("Summarize this conversation for your future self: decisions, facts, open items, file paths…"), replace them with a single user message "[Conversation summary]\n…", emit Event("compaction", {before: n, after: m, summary_preview}); after_model stores usage.prompt_tokens into ctx.state["last_prompt_tokens"]

ROLE_TOOLS = {
  "sales":       {"lookup_customer", "send_proposal"},
  "engineering": {"lookup_customer", "lookup_issue"},
  "finance":     {"lookup_customer", "get_revenue"},
}
```
The chain runs middlewares in list order; the first `deny` wins; an `ask` wins over `allow`.

### `subagents.py`

```python
@dataclass
class SubagentDef: name: str; description: str; system_prompt: str; tools: list[str]; model: str | None
PROPOSAL_REVIEWER = SubagentDef(
    name="proposal-reviewer",
    description="Checks a drafted proposal against the customer record and flags commitments the record does not support. Use after drafting any proposal.",
    system_prompt="…read-only reviewer; call lookup_customer; return a checklist: Supported / Unsupported / Missing; be terse…",
    tools=["lookup_customer"], model=None → settings.subagent_model)
def make_run_subagent_tool(defs: list[SubagentDef], registry: ToolRegistry, llm_factory) -> Tool
    # run_subagent(name, task): builds a child Agent (loop.py) with its own fresh message list, the subset of tools, CallLimit(6,8), no approvals;
    # child events are re-emitted on the parent ctx with event.subagent = name (so the UI nests them); returns the child's final text
```

### `approvals.py`

```python
@dataclass
class ApprovalRequest: id: str; tool: str; arguments: dict; session_id: str
class ApprovalBroker(Protocol):
    async def ask(self, req: ApprovalRequest) -> bool
class AutoReject(ApprovalBroker)          # default when nothing is wired; logs
class StdinApprover(ApprovalBroker)       # CLI: "Approve send_proposal → ceo@…? [y/N] "
class FutureApprover(ApprovalBroker)      # web: creates asyncio.Future per req.id, stores in .pending; .resolve(id, approved); timeout 600 s → False
```

### `loop.py` — the agent loop

```python
@dataclass
class Event:
    kind: Literal["run_start","text_delta","text_done","tool_call","decision","approval_request","approval_result",
                  "tool_result","todo_update","subagent_start","subagent_end","compaction","audit","checkpoint",
                  "usage","run_end","error"]
    data: dict
    component: str | None = None        # "model"|"context"|"actions"|"boundaries"|"persistence" — drives the UI's harness map
    subagent: str | None = None         # set on events that happened inside a subagent run
    ts: float = field(default_factory=time.time)
    def to_json(self) -> dict

@dataclass
class RunContext: role: str; stage: int; session_id: str; state: dict; emit: Callable[[Event], None]

class Agent:
    def __init__(self, *, llm: LLM, system_prompt: str, tools: ToolRegistry, middlewares: list[Middleware],
                 approvals: ApprovalBroker, store: "SessionStore | None", session_id: str, role: str, stage: int)
    messages: list[dict]                 # history (without the system prompt); loaded from store on resume
    async def run(self, user_text: str) -> AsyncIterator[Event]
```
`run()` algorithm (write it so the loop itself is readable on a slide):
1. emit `run_start`; append user message; checkpoint.
2. loop: `msgs = [system] + history`; for each middleware `msgs = await mw.before_model(msgs, ctx)`.
3. stream the model: emit `text_delta` per chunk (component "model"); collect tool calls + usage; emit `usage`.
4. append assistant message (content + tool_calls); checkpoint; `after_model` on every middleware.
5. no tool calls → emit `text_done`, `run_end` {session_id, model_calls, tool_calls, prompt_tokens, completion_tokens}; return.
6. for each tool call: emit `tool_call` (component = tool.component); unknown tool → tool message with error text.
   Run the middleware chain → `Decision`; emit `decision` for every non-allow (component from the decision; also emit allow decisions with `data.silent=True` so the UI can count them).
   `deny` → tool message `"Blocked by harness: {reason}"`.
   `ask` → emit `approval_request`; `ok = await approvals.ask(...)`; emit `approval_result`; rejected → tool message `"User rejected the action."`.
   allowed → `try: result = await tool.handler(args, ctx)` / `ToolError` → `"Tool error: …"` (ok=False); emit `tool_result` {name, ok, preview (first 400 chars)}; `after_tool` on every middleware; append tool message; checkpoint.
7. back to 2. Any `LLMError`/unexpected exception → emit `error` and `run_end` with `error=True`; never leave the history with a dangling tool call (append a tool message "aborted" for each unanswered call).

### `persistence.py`

```python
class SessionStore:                     # sqlite3 (stdlib), WAL mode, one file DB_PATH
    def __init__(self, path: Path = DB_PATH)
    def create(self, session_id: str, stage: int, role: str, title: str = "") -> None
    def append(self, session_id: str, message: dict) -> None          # table messages(session_id, seq, json)
    def replace_all(self, session_id: str, messages: list[dict])      # after compaction
    def load(self, session_id: str) -> list[dict]
    def list_sessions(self) -> list[dict]                             # [{session_id, stage, role, title, created_at, updated_at, message_count}] newest first
    def set_title(self, session_id, title)                            # first user message, truncated to 60 chars, set automatically on first append
    def delete(self, session_id)
```
Stages 0–3 use `store=None` (history lives in memory only, and is lost on restart — the UI makes this point). Stage 4 passes a real store.

### `stages.py` — the one place that composes a stage

```python
@dataclass
class Scenario: title: str; role: str; prompt: str; watch: str          # watch = one sentence telling the audience what to look at

def build_agent(stage: int, role: str, *, session_id: str | None = None, approvals: ApprovalBroker | None = None,
                llm: LLM | None = None, store: SessionStore | None = None) -> Agent
    # stage 0: Agent(llm, "You are a helpful assistant.", empty registry, [], AutoReject, None)
    # stage 1: + system prompt from context.build_system_prompt; registry += load_skill
    # stage 2: + company tools; middlewares [CallLimit(), TodoTracker()]; registry += run_subagent([PROPOSAL_REVIEWER])
    # stage 3: middlewares = [RoleGate(), ProtectedPaths(), ApprovalGate(), CallLimit(), TodoTracker(), AuditLog()]; approvals = given or AutoReject
    # stage 4: registry += workspace tools; middlewares += [Compactor(llm)]; store = given or SessionStore(); session resumed if session_id exists in store
    # session_id default: uuid4 hex[:12]

def stage_snippet(stage: int) -> list[dict]      # [{file, title, code}] — REAL code extracted from the package by marker comments:
    #   put `# [stage:N] <title>` on the line before a block and `# [/stage:N]` after it, in whichever module the block lives.
    #   stage_snippet scans harness/*.py for those markers (the marker lines themselves are stripped; indentation is dedented).
    #   Every stage has 1–3 snippets, each ≤ 20 lines (see Lightness rule). The first snippet is always the stage's Agent(...) call.
def scenarios(stage: int) -> list[Scenario]      # see Scenarios
def describe_stage(stage: int) -> dict           # {id, name, component, tagline, headline, problem, bullets: [3–4 strings], unlocked_tools: [...], middlewares: [...], subagents: [...], new_keywords: [...]}  # new_keywords = Agent(...) kwargs first used in this stage; headline ≤ 6 words, no end punctuation; problem = 2–3 plain sentences
```

### `cli.py`

`python -m harness.cli --stage 3 --role finance [--session <id>] [--list-sessions]`. REPL; prints events compactly with the component tag (`[boundaries] deny: …`), approvals on stdin.

## Scenarios (also the talk's demo script)

| Stage | Title | Role | Prompt | Watch |
|---|---|---|---|---|
| 0 | Does it know us? | sales | What do you know about Kestrel Software and our proposal process? | The model guesses or admits it doesn't know. Nothing lights up but the model. |
| 1 | Skill-guided draft | sales | Use the proposal-writing skill to draft a proposal for Acme Robotics: Enterprise plan, 40 seats, they care about SSO and audit logs. | `load_skill` fires (Context node), and the draft follows the skill's sections. We still had to explain who Acme is. |
| 2 | Look it up yourself | sales | Draft a proposal for Acme Robotics and have the proposal-reviewer check it before you show it to me. | `lookup_customer`, a todo list, then the subagent's nested review. |
| 2 | Runaway loop | engineering | For every open issue, look up its customer, then look up every other issue for that customer, and keep going until you have checked everything twice. | `CallLimit` stops it. |
| 3 | Wrong role | engineering | What was our revenue in FY2026? | `RoleGate` denies `get_revenue`; the model says so instead of guessing. |
| 3 | Right role | finance | What was our revenue in FY2026? | Same question, allowed, answered with record ids. |
| 3 | Needs a human | sales | Draft a short Enterprise proposal for Acme Robotics (40 seats, SSO and audit logs) and send it to procurement@acme-robotics.example with the subject "Kestrel Enterprise proposal". | Approval card appears and the loop waits; approve → outbox file + audit line. Variant with ceo@acme-robotics.example: the tool rejects the unverified address. |
| 4 | Save it | sales | Draft a short Enterprise proposal for Acme Robotics (40 seats, SSO and audit logs) and save it as workspace/acme-proposal.md. Give me the path. | `write_workspace_file` (Persistence node); `checkpoint` events. Also show a write to `company/AGENTS.md` being blocked. |
| 4 | Come back tomorrow | sales | *(resume the previous session)* What did we save earlier, and what was in it? | Resumed history answers without re-reading. Then trigger compaction on a long session and show the summary marker. |

## Web app (`app/`) — the demo surface

**Approved design (round 3, 2026-11-02):** a light "paper workbench" in the visual language of
the presenter's earlier Harness Lab project, evolved for Kestrel Desk, with the **chat as a
centered chatbox** like the NS Work demo in the reference video. The design canvas the presenter
approved has two artboards: "Workbench: adding stage 2" and "Workbench: stage 3, approval
pending". Build exactly those; the sections below describe them in words.

**Zero network dependencies at runtime**: no CDN scripts, no web fonts, no external images.
Fonts are the system stack: headlines `Georgia, "Times New Roman", serif`; UI
`"Segoe UI", system-ui, -apple-system, sans-serif`; code `"Cascadia Code", Consolas, ui-monospace, monospace`.

### Visual language (CSS variables in `styles.css`)

| token | value | use |
|---|---|---|
| `--paper` | `#f7f7f1` | page ground |
| `--surface` | `#fffefa` | cards, chat window, inputs |
| `--forest` | `#163e2f` | primary buttons, brand mark, approval card header, headline color |
| `--forest-soft` | `#eaf0e7` | user bubbles, assistant avatar, tool-name pills |
| `--ink` | `#263d32` | body text |
| `--muted` | `#7b8379` | secondary text, kickers |
| `--line` | `#e2e5da` | hairlines and card borders (1px) |
| `--lime` | `#d5e5b4` | success ticks, "APPROVAL NEEDED" label text on forest |
| `--code-bg` / `--code-line` | `#f6f9ef` / `#e5ebd8` | code blocks |
| `--blue` | `#174b91` | component card "added" |
| `--orange` | `#ff9d36` (ring `#ffe2bd`, mark `#ffb454`, text `#8a4b1f`) | "ADDED NOW / ACTIVE NOW / WAITING ON YOU", progress segment, live dot, new-code highlight |
| `--amber` | `#a77728` | tool icon, string literals in code |
| `--red` | `#a24b3f` | denials, Stop button, "blocked" counters |
| `--gray-card` | `#eef0e8` | component card "not yet" |

Type scale: kicker 10.5px / letter-spacing 2px / 700 / muted (e.g. `1 · WHAT WE ADD`); page
headline Georgia 40–44px / 700 / forest with an orange full stop; chat text 15.5–16px; event
rows 13.5px title + 12.5px detail; code 16px on the add-stage screen, 13px in the drawer;
labels 9–10px tracked. Radii: cards 12px, chat window 14px, buttons 8px, pills 999px. Shadows
only on the approval card (`0 10px 30px rgba(22,62,47,.08)`). Light theme only (no dark mode).

Brand mark: a 30px forest rounded square with a Georgia `k` and an orange `·`, then
"**Kestrel**Desk" (bold + regular).

### Screen A — "Add stage" (`view=add`)

Shown when the presenter presses → / Next stage. Layout at 1440×900:

1. **Top bar** (58px): brand; breadcrumb "Kestrel Desk / Build a harness, stage by stage";
   right: live badge (`LIVE · <model>` with a pulsing orange dot, or `MOCK · REHEARSAL` in mock
   mode), **Back**, **Open the chat →** (forest primary).
2. **Page heading**: kicker with a short orange rule `STAGE 2 OF 4 · ACTIONS`; Georgia headline
   from `describe_stage(s).headline` (e.g. "Let it look things up itself."); right: a 5-segment
   progress bar (blue done, orange current filling in over 0.9 s, gray later).
3. **Left column (~0.9fr)**: card `1 · THE PROBLEM` (Georgia 23px, 2–3 sentences from
   `describe_stage(s).problem`); card `2 · WHAT WE ADD` (one sentence from `tagline`, then the
   **four component cards** in a row: blue "Added" with ✓, the current one blue with an orange
   `ADDED NOW` badge and a pulsing orange ring, later ones gray "Not yet"; then pills for
   `unlocked_tools` (forest-soft) and `middlewares` (outlined) and subagents (amber outline)).
4. **Right column (~1.1fr)**: card `3 · THE CODE`: header line "Read from the running source ·
   **N new keywords**"; the snippets from `stage_snippet(s)` as lime code blocks with a
   `harness/stages.py · the whole stage, one call` caption; lines reveal one by one (~150 ms
   apart); every line containing a `new_keywords` entry followed by `=` gets an orange `<mark>`
   (`#ffe2bd` bg, `#38220a` text, 1px `#ffb454` ring) around the `kw=value` span. Bottom: a
   `NEXT` bar naming the first scenario with a **Run scenario** button (forest) that opens the
   chat and runs it.
5. **Footer**: `KESTREL DESK · Every stage is one Agent(...) call in the running code. The chat
   on the next screen runs exactly this configuration.` and the shortcut hint.

Stage 0 has no "new keywords" and shows `Agent(model=llm)` alone; its problem text explains
that nothing but the model is there.

### Screen B — "Chat" (`view=chat`)

1. **Top bar** as above; breadcrumb `Build a harness / Stage 3 · Boundaries`; right: live badge,
   **Code & scenarios /** (opens the drawer), **Back**, **Next stage**.
2. **Component strip** `AROUND THE MODEL`: one row, same width as the chat (940px), the four
   component cards as compact pills (number · name · ✓ / badge). The card whose component is
   acting pulses (orange ring, 600 ms) on each event with that `component`; during an approval
   the Boundaries card shows `WAITING ON YOU`; on `decision.deny` it flashes red once with the
   reason as a tooltip; `checkpoint` increments a small counter on Persistence; `compaction`
   shows a one-line note under the strip for 4 s.
3. **Chat window** (940px, centered, surface card, 14px radius): header with the assistant
   avatar (forest-soft circle with a Georgia `k`), "Kestrel Desk" + the stage line, and on the
   right "Signed in as" + the **role picker** (segmented pill: Sales / Engineering / Finance, the
   active one forest) and a **status pill** (`READY`, `THINKING`, `RUNNING TOOL`, `WAITING FOR
   APPROVAL`, `DONE`, `BLOCKED`, `ERROR`).
   Transcript: user messages as forest-soft bubbles on the right (14px radius, 3px on the
   bottom-right corner); assistant turns with the avatar on the left; streamed text appended per
   `text_delta` with a blinking forest caret while streaming. **Event rows** inside the assistant
   turn, indented with a 2px left rule (orange while a gate is active, lime for the subagent):
   28px icon circle · title (`lookup_customer` + mono args) · detail (result preview or
   decision chain `RoleGate allow · ProtectedPaths allow · ApprovalGate ask`) · label chip
   (`TOOL · ACTIONS · 118 MS`, `GATE · BOUNDARIES`, `SUBAGENT · PROPOSAL-REVIEWER`, `TODO`,
   `CHECKPOINT`, `COMPACTION`) · timestamp on the right. A denied call renders its row with a
   red rule and `Blocked by harness: <reason>`. A subagent renders as one row that expands to
   show its nested rows. `todo_update` renders a compact checklist row that updates in place.
   **Approval card**: forest header bar (`APPROVAL NEEDED` in lime tracked caps, the tool name
   in mono, `expires in m:ss`), a definition list of the arguments (with `✓ contact on record`
   when `to_email` matches), **Approve and send** (forest) / **Reject** (outlined), and the line
   "Nothing has been sent. Your decision goes to the audit log." Resolves with a stamp
   (`APPROVED` lime / `REJECTED` red) and stays in the transcript.
   Composer: input + **Stop** (red text, outlined) + send button; disabled while a run is in
   flight. Under it a facts line: `session <id> · N model calls · N tool calls · N blocked ·
   tokens in/out · audit.jsonl · n lines · outbox · n files` and the shortcut hint.
4. **Drawer** (`/` key, the top-bar button, or the vertical `CODE · SCENARIOS` tab on the right
   edge): slides in from the right (420px, surface, hairline), two tabs. **Code**: the stage's
   snippets as lime code blocks (13px) with the orange marks on new keywords. **Scenarios**: the
   stage's cards (title, role, prompt in quotes, "Watch:" line); **Run** sets the role, closes
   the drawer, fills the composer and sends; a running card gets an orange 2px border and a
   pulsing numbered dot; a finished one a lime ✓. Stage 4 adds a **Sessions** section (list from
   `/api/sessions` with Resume) and a **Compact now** button.
5. Transitions: stage change → Screen A with the progress segment filling and the component
   card ring pulsing; **Open the chat** → Screen B with the chat window rising 12px/300 ms;
   events → rows slide in 8px/250 ms. `prefers-reduced-motion` respected; nothing flashes faster
   than 3 Hz.

Keyboard: `←`/`→` stage (always lands on Screen A), `Enter` on Screen A opens the chat,
`1–3` role, `/` drawer, `Esc` closes the drawer / stops a run (with confirmation while a run
is in flight), `P` presenter mode (+15% type, hides the facts line).

### `server.py` (FastAPI, `127.0.0.1:8765`)

- `GET /` → `static/index.html`; static mounted at `/static`.
- `GET /api/meta` → `{model, base_url_host, mock: bool, stages:[describe_stage(s)…], roles, scenarios:{stage:[…]}, snippets:{stage:[…]}}`
- `POST /api/session` body `{stage, role, resume_session_id?}` → `{session_key, session_id, resumed, history}`; one `Agent` per `session_key`, built with `build_agent(..., approvals=<shared FutureApprover>)`
- `POST /api/send` body `{session_key, text}` → `{run_id}`; runs `agent.run(text)` as a task pushing `event.to_json()` into that session's queue
- `GET /api/events/{session_key}` → SSE (`data: <json>\n\n`, `: ping` every 15 s)
- `POST /api/stop/{session_key}` → cancels the task
- `POST /api/approve` body `{request_id, approved}` → resolves the pending future
- `GET /api/sessions` → `SessionStore().list_sessions()`
- `DELETE /api/session/{session_key}`
- `POST /api/compact/{session_key}` → runs the Compactor once (stage 4)
- `GET /api/audit?limit=50`, `GET /api/outbox`
- `KESTREL_MOCK=1` → `app/mock.py` serves canned meta and scripted event streams per scenario (the rehearsal fallback if the model endpoint is down on talk day)

`describe_stage(s)` must also return `headline` (the Georgia page title, ≤ 6 words, ends
without punctuation; the UI adds the orange full stop) and `problem` (2–3 plain sentences).

Files: `app/server.py`, `app/mock.py`, `app/static/index.html`, `app.js`, `styles.css`,
`highlight.js` (our own ~80-line Python tokenizer: keywords, builtins, strings incl. f-strings,
comments, decorators, numbers, def/class names, light-theme colors matching the code block).
Vanilla ES2020, no build step, `app.js` ≤ ~1000 lines organized by section (state, api, sse,
screen A, strip, transcript, approval, drawer, keyboard).

## Tests & verification (core agent)

`tests/` run with `pytest -q`, no network, `FakeLLM` only:
- tools: lookups, unverified email rejected, outbox write (tmp OUTBOX via monkeypatched settings), workspace path escape blocked
- middleware: RoleGate deny/allow per role, ProtectedPaths, CallLimit, Compactor replaces the middle and keeps the last N, TodoTracker state
- loop: FakeLLM script `[ToolCall lookup_customer] → "final text"` yields events in order `run_start, text_delta…, tool_call, decision(allow,silent), tool_result, usage, text_done, run_end`; a denied call produces `decision.deny` and a tool message starting "Blocked by harness"; an `ask` with an approver that returns False produces `approval_result{approved:false}`; an exhausted FakeLLM produces `error` then `run_end`
- persistence: create/append/load round-trip; `build_agent(4, …, session_id=existing)` loads history; list_sessions newest first
- stages: every stage × role builds; stage 0 has no tools; stage 3 registry includes `send_proposal` but RoleGate blocks it for engineering; `stage_snippet(s)` is non-empty for s in 0..4 and each snippet ≤ 40 lines; `scenarios(s)` roles are valid

`scripts/verify_offline.py` runs the data/skill/AGENTS checks (schema, ids resolve, frontmatter present, all three roles mentioned), then `pytest -q`, then imports `app.server` and hits `/api/meta` with `fastapi.testclient`, printing PASS/FAIL lines; exit 1 on any FAIL.

## Conventions

- Python 3.12, `from __future__ import annotations`, type hints, docstrings that say *why*.
- Comments at the points where a harness lesson lives ("permissions are enforced here, in code, not in the prompt"). These are the lines the audience will read.
- `# [stage:N] Title` / `# [/stage:N]` markers around the blocks that *define* each stage (the stage branch in `stages.py`, the middleware class, the tool, the loop's decision handling…). They are the slides.
- Windows-friendly: `pathlib` only; compare paths with `Path.resolve()` + `is_relative_to`.
- No real email, no real company data, no network except through `llm.py`.
- Files ≤ ~300 lines; split before they grow past that.
- Never print or log the API key.
