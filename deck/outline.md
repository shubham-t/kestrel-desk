# Agent harness engineering: slide outline

Deck: `deck/Kestrel-Desk-Harness-Engineering.pptx` (16:9, light "paper workbench" theme matching the approved Kestrel Desk demo UI). Built by `deck/build_deck.js`.

Timing: about 25-30 min of slides, interleaved with five live demo stops (→ Demo slides). Speaker notes below are also in the .pptx notes pane.

Preview without PowerPoint: `deck/preview/grid-1.jpg` … `grid-4.jpg` (thumbnail grids of every slide, 9 per image, rendered by PowerPoint from this build).

CallLimit numbers on slide 16 (8 model calls, 10 tool calls per run) are read at build time from `CallLimit.__init__` defaults in harness/middleware.py.

## Snippet sources

Every code slide is cut at build time by `harness.stages.stage_snippet(s)` from the `# [stage:N]` marker blocks in `harness/*.py` (dedented, verbatim); the one exception is the load_skill slide, whose code is the inner `load_skill` function of `make_load_skill_tool` in harness/context.py, cut with `ast` at build time (also verbatim). Over-long lines are soft-wrapped on the slide with a muted ↪; no characters are changed. Demo slides list `harness.stages.scenarios(s)`: titles, roles and prompts verbatim (two long prompts shortened with …, each cut checked against the real prompt), and a watch line made of exact excerpts of each scenario's `watch` text.

- slide 8: harness/stages.py [stage:0] "A chatbot: a model and a prompt"
- slide 11: harness/stages.py [stage:1] "Context: the company file, always on"
- slide 13: harness/tools_company.py [stage:2] "A tool is a typed, documented function"
- slide 15: harness/context.py make_load_skill_tool(): the inner load_skill, verbatim (read with ast at build time)
- slide 17: harness/subagents.py [stage:2] "A subagent: its own prompt, a subset of tools, a cheaper model"
- slide 18: harness/stages.py [stage:2] "Actions: tools, a loop with middleware, skills on demand, a subagent"
- slide 20: harness/middleware.py [stage:3] "Who may use which tool"
- slide 22: harness/tools_company.py [stage:3] "The tool checks what the model might get wrong"
- slide 23: harness/stages.py [stage:3] "Boundaries: roles, human approval, audit"
- slide 26: harness/tools_workspace.py [stage:4] "Writes are confined to workspace/"
- slide 27: harness/compaction.py [stage:4] "What compaction asks the model to keep"
- slide 28: harness/stages.py [stage:4] "Persistence: checkpoints, a workspace, compaction"
- slide 7: `.env` sample (illustrative values; variable names from harness/config.py)

## Introduction

### 1. Agent harness engineering

Key points:
- From a chatbot to an agent, one component at a time
- Live demo: Kestrel Desk

Speaker notes: Today we're going to build an agent in front of you, one piece at a time. The demo is Kestrel Desk, an internal assistant for a made-up software company called Kestrel. Everything around the model is our own code, no agent framework, so you can read all of it afterwards. The row at the bottom is where we'll end up: four components around one model. Let's start with why we need any of it.

### 2. What you'll leave with

Key points:
- A mental model: four components around one model
- A working harness you can read in an hour
- A checklist: ten questions for any agent

Speaker notes: Three things to take home. First, a mental model: four components around one model. You can use it to read any agent product you come across. Second, a working harness, about two thousand lines of Python, small enough to read end to end in an hour. Third, a checklist of ten questions you can hold up against whatever agent your team builds or buys next.

### 3. Models answer. Tasks need more

Key points:
- Then: a question in, an answer out
- Now: whole tasks (proposals, incident triage, code changes)
- The model only decides the next step

Speaker notes: A couple of years ago we asked models questions and got answers back. One call, done. Now we hand them whole tasks: prepare a proposal, triage an incident, change the code and run the tests. A task is many steps, and the model can only ever decide the next one. Everything else, fetching the data, running the step, checking it's allowed, remembering where we are, has to come from somewhere else.

### 4. What a harness is

Key points:
- The software around the model
- Supplies information · carries out actions
- Checks what's allowed · keeps track of work
- Examples: Claude Code, Codex, Cursor's agent, ChatGPT with tools, Stripe's Minions

Speaker notes: That somewhere else is the harness: all the software around the model. It supplies information, carries out actions, checks what's allowed, and keeps track of the work. Think of it as the operating system around the model. You've used plenty of these: Claude Code, Codex, Cursor's agent, ChatGPT with tools, and companies build their own, like Stripe's internal coding agent, Minions. It's a widely reported observation that the same model does noticeably better in a better harness, which is why this is engineering work, not prompt tweaking.

### 5. Anatomy of an agent loop

Key points:
- Prompt → model → tool calls?
- Yes: middleware checks → execute → results → model
- No: the answer
- This is the loop we run live

Speaker notes: Here's the whole engine on one slide. A prompt goes to the model. If the model asks for tools, each call goes through the middleware checks, gets executed, and the results go back to the model as new messages. Round and round, until the model answers without asking for a tool, and that's the answer. This is exactly the loop you'll watch run live; it's about a hundred lines in loop.py.

### 6. Four components, one model

Key points:
- Context: what the model knows
- Actions: what it can do
- Boundaries: what it's allowed to do
- Persistence: what survives between turns

Speaker notes: Every harness feature we'll add falls into one of four buckets. Context is what the model knows. Actions are what it can do. Boundaries are what it's allowed to do. Persistence is what survives between turns and sessions. We add them in that order, one stage each. This row comes back on every stage slide, and the demo UI shows exactly the same strip: blue when a component is in, orange ring for the one we just added, gray for not yet.

### 7. One file talks to the model

Key points:
- harness/llm.py speaks OpenAI chat-completions
- Today: Anthropic's OpenAI-compatible endpoint
- Your laptop: the internal model, a .env change
- Nothing else knows the provider

Speaker notes: One practical note before the demo. Exactly one file, harness/llm.py, talks to a model provider, and it speaks the OpenAI chat-completions protocol through the openai Python SDK. Today it points at Anthropic's OpenAI-compatible endpoint. When you run it on your laptop, you change the base URL, the key and the model name in .env, and the same code runs against our internal model. Nothing else in the harness knows or cares what's behind that URL. That's a good habit for any harness: keep the provider behind one seam.

## Stage 0 · Chatbot

### 8. Stage 0 is one line

Key points:
- Agent(...) for stage 0; new keywords: model
- A system prompt, a message list, one model call.

Speaker notes: Stage zero is the baseline, and in code it is literally one line: an Agent with a model and nothing else. One generic system prompt, a message list kept in memory, one streamed model call per turn. No tools, no company knowledge, no memory across restarts. Look at the strip: the model in the middle, and all four components gray. Let's see how far that gets us.

### 9. → Demo: Stage 0 · Chatbot

**Demo:** Switch to the browser: Stage 0 (Chatbot)

Key points:
- Who's Acme? (as sales): "Who is Acme Robotics and when is their renewal due?". Watch: It can't know. Nothing is around the model.
- Price the renewal (as sales): "Draft a renewal proposal for Acme Robotics: 40 seats on our Enterprise plan, with pricing.". Watch: It invents a price, or asks for one. It has no idea what our plans cost.

Speaker notes: Switch to the browser, stage 0. Two runs, both as sales, and this is where the Acme Robotics renewal story starts. First, 'Who's Acme?': Who is Acme Robotics and when is their renewal due? It can't know: nothing is around the model, so it guesses or says it doesn't know. Second, 'Price the renewal': Draft a renewal proposal for Acme Robotics: 40 seats on our Enterprise plan, with pricing. It invents a price, or asks for one; it has no idea what our plans cost. Remember that prompt: we run it again at stage 1. Then come back to the slides.

## Stage 1 · Context

### 10. Context we push, on every call

Key points:
- company/AGENTS.md becomes the system prompt
- Pushed on every call: facts, plans and prices, business rules
- The request is identical to stage 0 except the system prompt
- Every line costs tokens on every call: keep it short

Speaker notes: The first component is context: what the model knows before it starts. Stage 1 adds exactly one thing: company/AGENTS.md becomes the system prompt. It holds what the model can't guess: who we are, our plans and list prices, and the business rules every answer has to follow, like 'discounts above 10% need written approval from finance'. This is context we push: it rides along on every single call, whether the task needs it or not. Look at the request on the right. Compared to stage 0, nothing changed except the system prompt: same single call, no tools, no loop. The file is about 530 words on purpose, because every line costs tokens every time.

### 11. Stage 1 in code

Key points:
- Agent(...) for stage 1; new keywords: instructions
- AGENTS.md is the system prompt. Nothing else about the call changes.

Speaker notes: In code, stage 1 is one keyword: instructions, pointing at AGENTS.md. The harness reads the file when the agent is built and sends it as the system prompt. No tools, no skills, no loop yet: it is exactly the stage 0 call with a better system prompt. In the strip, Context is in, with the orange ring because we just added it.

### 12. → Demo: Stage 1 · Context

**Demo:** Switch to the browser: Stage 1 (Context)

Key points:
- Price the renewal, again (as sales): "Draft a renewal proposal for Acme Robotics: 40 seats on our Enterprise plan, with pricing.". Watch: Plan-table price ($2,400 per seat per year), our tone, our sections, no discount. Tokens in jumped: AGENTS.md rides on every call.
- Can I discount? (as sales): "Can I offer Acme 15% off to close this quarter?". Watch: "No: above 10% needs written approval from finance", straight from AGENTS.md. A business rule, not a fact.

Speaker notes: Back to the browser, stage 1, still as sales. First, 'Price the renewal, again': the exact same prompt as stage 0, draft a renewal proposal for Acme Robotics, 40 seats on our Enterprise plan, with pricing. Now the price comes from the plan table, $2,400 per seat per year, in our tone and our sections, with no discount. Look at tokens in on the facts line: it jumped, because AGENTS.md rides on every call. And notice we still had to tell it who Acme is. Second, 'Can I discount?': Can I offer Acme 15% off to close this quarter? No: above 10% needs written approval from finance, straight from AGENTS.md. That's a business rule, not a fact. What it can't do yet is look anything up: that's the next component.

## Stage 2 · Actions

### 13. A tool is a typed, documented function

Key points:
- @tool turns the type hints and docstring into the schema the model sees. ctx is injected.

Speaker notes: AGENTS.md can't hold every customer record, which is why we still had to say who Acme is. So the second component is actions: the model fetches facts itself. A tool is just a typed async function with a docstring. This is lookup_customer, exactly as it is in the repo. The @tool decorator reads the type hints and the docstring and generates the JSON schema the model sees; ctx is injected by the harness and never shown to the model. It takes an id or part of a name. And when nothing matches, the error is written for the model: it points at list_customers instead of letting it guess.

### 14. Skills: an index now, the body on demand

Key points:
- Stage 1 pushed AGENTS.md on every call; skills are context the model pulls
- The prompt lists each skill: name + one line
- The model calls load_skill when a task needs one
- The full SKILL.md enters context only then

Speaker notes: Stage 1 was context we push: AGENTS.md rides on every call. That doesn't scale to every playbook we have. So at stage 2, next to the tools that pull facts, we add context the model pulls: skills. The prompt only lists each skill's name and its one-line description, straight from the SKILL.md frontmatter. When a task needs one, the model calls load_skill, and only then does the full text enter the conversation. That's progressive disclosure: cheaper, less distracting, and it scales. It needs the loop, a tool call and then another model call, which is why it arrives here and not at stage 1.

### 15. load_skill is the whole mechanism

Key points:
- An unknown name raises a ToolError: the model gets the valid names back and can correct itself.

Speaker notes: And this is the tool the skills keyword installs, the real code from context.py. It's a closure over the discovered skills: look the name up, return the body. Notice the error path: if the model asks for a skill that doesn't exist, nothing crashes; it raises a ToolError, and the message goes back to the model with the list of valid names. Errors written for the model to read are a recurring pattern in a good harness.

### 16. Actions: middleware in the loop

Key points:
- Small objects the loop calls at fixed points
- Hooks: before_model, after_model, before_tool, after_tool
- CallLimit: 8 model calls and 10 tool calls per run
- TodoTracker-style planning: one more middleware you could add

Speaker notes: A loop that keeps calling tools needs a brake, and the place for rules about acting is middleware: a small object the loop calls at fixed points, before and after each model call and before and after each tool call. Stage 2 ships exactly one: CallLimit, a budget of 8 model calls and 10 tool calls per run. Past it, the call is denied or the run stops, always with a reason the model can report. Planning in the style of TodoTracker, an update_todos tool and a plan you can watch in the UI, is one more middleware you could add the same way. And everything in the next stage, boundaries, is middleware too.

### 17. A subagent is a definition

Key points:
- Own prompt, a subset of tools, a cheaper model, a clean context. Only its checklist comes back.

Speaker notes: Some work is better done in a separate room. A subagent has its own prompt, its own small set of tools, and runs on a cheaper model, here the subagent model from .env. It starts with a clean context, does its job, and hands back only a summary, so the main conversation doesn't fill up with its working. Our proposal-reviewer checks a draft against the customer record and returns three headings: Supported, Unsupported, Missing. It's just data; the harness turns it into a run_subagent tool.

### 18. Stage 2 in code

Key points:
- Agent(...) for stage 2; new keywords: tools, middleware, skills, subagents
- Company tools, a call budget, skills on demand, one subagent.

Speaker notes: Four new keywords: tools, middleware, skills and subagents. The loop that runs tool calls was always there; now it finally has something to do. skills installs the index and load_skill, subagents turns the reviewer definition into a run_subagent tool, and the only middleware is CallLimit. In the strip, Context is blue and Actions has the orange ring.

### 19. → Demo: Stage 2 · Actions

**Demo:** Switch to the browser: Stage 2 (Actions)

Key points:
- Prepare the renewal (as sales): "Prepare Acme Robotics' renewal proposal: check their record and open issues, then have the proposal-reviewer check it before you show it to me.". Watch: load_skill pulls the playbook, lookup_customer and lookup_issue pull the facts, the reviewer runs as a nested subagent.
- Account health, every customer (as engineering): "Give me an account health report for every customer: their record plus their open issues.". Watch: CallLimit denies the 11th tool call; the model reports partial results and says why.

Speaker notes: Stage 2, two runs. First, as sales, 'Prepare the renewal': Prepare Acme Robotics' renewal proposal: check their record and open issues, then have the proposal-reviewer check it before you show it to me. Watch load_skill pull the proposal playbook, lookup_customer and lookup_issue pull the facts, and the reviewer run as a nested subagent row. This time we never said who Acme is: the model fetched what it needed. Then switch the role to engineering and run 'Account health, every customer': Give me an account health report for every customer: their record plus their open issues. A realistic over-sized request: CallLimit denies the 11th tool call, and the model reports partial results and says why.

## Stage 3 · Boundaries

### 20. Permissions live in code

Key points:
- A rule in the prompt is a suggestion. A rule in code is a guarantee.

Speaker notes: Third component: boundaries. Each role gets a set of tools; that's the ROLE_TOOLS table, real code. Sales can send proposals, engineering can look up issues, finance can see revenue. RoleGate checks that set before every tool call. This lives in code, not in the prompt. A prompt that says 'please don't' is a suggestion the model may or may not follow; a denied call is a guarantee. And the model gets the reason back, so it can explain instead of guessing.

### 21. Boundaries: the permission chain

Key points:
- RoleGate → ApprovalGate → CallLimit → AuditLog
- First deny wins
- ask beats allow: the loop waits for a human
- Every outcome lands in the audit log

Speaker notes: Every tool call runs through the same chain, in order: RoleGate checks the role, the ApprovalGate decides whether a human has to say yes, then your own middleware, here CallLimit from stage 2, and after the tool runs the AuditLog writes one line with the outcome. Each gate answers allow, ask or deny. The first deny wins. An ask beats an allow: the loop pauses and waits for a human to approve or reject. Each box comes from one keyword, shown at the bottom of the card. You'll see these decisions spelled out in the demo's event rows.

### 22. The tool checks, too

Speaker notes: Boundaries aren't only middleware. Here's send_proposal, the real code. It's marked as needing approval, so a human sees a card before it runs. And the tool itself refuses an email address that isn't the contact on record. Defense in depth: the model might hallucinate an address, the human might click approve too fast, the tool still says no. And it never sends a real email; it writes a file to the outbox. The arrows mark lines that wrap on the slide; in the source they're one line.

### 23. Stage 3 in code

Key points:
- Agent(...) for stage 3; new keywords: permissions, approve, audit
- Same tools as stage 2; now they run under rules.

Speaker notes: Three keywords: permissions, approve and audit. Notice what didn't change: the tools. send_proposal is the same function it was in stage 2; we just told the harness it needs a human. Boundaries now has the orange ring in the strip.

### 24. → Demo: Stage 3 · Boundaries

**Demo:** Switch to the browser: Stage 3 (Boundaries)

Key points:
- Wrong role (as engineering): "What was our revenue in FY2026?". Watch: RoleGate denies get_revenue, in code, before it runs
- Right role (as finance): "What was our revenue in FY2026?". Watch: Same question, allowed, answered with record ids.
- Send it (as sales): "Draft a short renewal proposal for Acme Robotics (…) and send it to procurement@acme-robotics.example with the subject "Kestrel renewal proposal".". Watch: The approval card appears and the loop waits. Approve → outbox file + audit line.

Speaker notes: Stage 3, three runs. As engineering, 'Wrong role': What was our revenue in FY2026? RoleGate denies get_revenue in code, before it runs, and the model says so instead of guessing. 'Right role': the same question as finance, allowed, answered with record ids. Then as sales, 'Send it': draft a short renewal proposal for Acme Robotics and send it to procurement@acme-robotics.example with the subject Kestrel renewal proposal. The approval card appears and the loop waits; the Boundaries card says waiting on you. Approve, and a file lands in the outbox, never a real email, plus an audit line. Variant if there's time: ask it to send to ceo@acme-robotics.example instead, and the tool itself rejects the address as not on record.

## Stage 4 · Persistence

### 25. Persistence: save and resume

Key points:
- Every message checkpointed to SQLite
- New in the demo: a Sessions sidebar (list, click to resume, New task)
- workspace/: the one folder the file tools write to
- Any path outside it is refused by the tool itself

Speaker notes: Fourth component: persistence. Until now history lived in memory: restart the server and it's gone. Now every message is checkpointed to SQLite. In the demo that shows up as something new: a Sessions sidebar to the left of the chat, with the saved sessions newest first. Click one and it resumes in place, or press New task to start fresh. The agent also gets a workspace folder with three file tools, and it's the only place they write: the tools themselves refuse any path outside workspace/, so the company files, the skills and the harness code stay untouched.

### 26. Writes are confined to workspace/

Key points:
- The path is resolved first, then checked. "../" can't climb out.

Speaker notes: Here's the write tool, real code. The interesting line is the comment: the path is resolved and then checked with is_relative_to, so tricks like dot-dot-slash end there. The confinement lives in the tool itself, not in the prompt and not in a middleware: whatever the model asks for, a path outside workspace/ is refused, and the model gets the reason back. That's exactly what you'll see when the demo asks it to edit AGENTS.md.

### 27. Persistence: compaction

Key points:
- Trigger: prompt above 6,000 tokens (demo setting)
- Summarize the middle with one extra model call
- Keep decisions, facts, files, open items
- System prompt and last 6 messages stay verbatim

Speaker notes: Long sessions eventually outgrow the context window. Compaction watches the prompt size. Past a threshold, 6,000 tokens in the demo, set low on purpose so you can see it, it makes one extra model call that summarizes the middle of the conversation into a single message. The system prompt stays, the last six messages stay verbatim, and the summary replaces everything in between. This is the actual prompt we use, and the last sentence is the important one: anything you leave out is forgotten.

### 28. Stage 4 in code

Key points:
- Agent(...) for stage 4; new keywords: checkpointer, workspace, compaction
- That's the whole agent: one constructor.

Speaker notes: Three keywords: checkpointer, workspace and compaction. That's the whole agent: five stages, one constructor, and every keyword maps to one card in the strip. The loop, the middleware chain and the approvals are all wired inside Agent from these keywords. All four cards are in now, Persistence with the ring.

### 29. → Demo: Stage 4 · Persistence

**Demo:** Switch to the browser: Stage 4 (Persistence); the Sessions sidebar appears left of the chat

Key points:
- Save the draft (as sales): "Draft a short renewal proposal for Acme Robotics (…), save it as workspace/acme-renewal.md, and add a line to company/AGENTS.md …". Watch: write_workspace_file writes the draft and checkpoints tick up … the AGENTS.md write is refused by the tool (outside workspace/)
- Pick up yesterday's work (as sales, resumes the latest saved session): "Where did we leave off with Acme, and what did we save?". Watch: Run resumes the most recent saved session from SQLite (the divider says so) and answers from history. In the sidebar the session is highlighted.
- Long day (as sales): no prompt, press Compact now. Watch: 9 → 7 messages, a compaction row with the summary.

Speaker notes: Stage 4, and the first thing to notice is the new Sessions sidebar sliding in to the left of the chat: saved sessions from SQLite, newest first, and a New task button. Three runs, all as sales. 'Save the draft': draft a short renewal proposal for Acme Robotics, save it as workspace/acme-renewal.md, and add a line to company/AGENTS.md saying the Acme draft is done. write_workspace_file writes the draft and the checkpoint counter ticks up; the AGENTS.md write is refused by the tool, because it is outside workspace/, and the model reports it. 'Pick up yesterday's work': Run resumes the most recent saved session from SQLite, the divider says so, and the session is highlighted in the sidebar; then it asks: Where did we leave off with Acme, and what did we save? It answers from history. You can also just click any session in the sidebar. 'Long day': no prompt, press Compact now in the drawer: 9 messages become 7, with a compaction row holding the summary.

## Wrap-up

### 30. What we didn't build (yet)

Key points:
- Per-user memory
- Scheduled and background runs
- Sandboxed tool execution
- Evals and regression tests
- Tracing, cost controls, prompt-injection defenses

Speaker notes: Here's what a production harness adds next. Memory that follows a user across sessions. Runs on a schedule or in the background. Tool execution in a sandbox. Evals and regression tests for the harness itself, so a prompt or middleware change can't silently make things worse. And tracing, cost controls, and defenses against prompt injection arriving through tool results. Each of these is another tool, another middleware, or another store. The shape you've seen holds.

### 31. Ten questions for any harness

Key points:
- Does it have: Instructions the team owns and reviews
- Does it have: Skills loaded only when needed
- Does it have: Tools whose schemas come from code
- Does it have: Hard limits on model and tool calls
- Does it have: Subagents for focused, disposable work
- Does it have: Permissions enforced in code, per role
- Does it have: Human approval for irreversible actions
- Does it have: An audit log of every tool call
- Does it have: Checkpoints you can resume from
- Does it have: Compaction before the window fills

Speaker notes: Here's the checklist. Hold any agent up against it: yours, a vendor's, an open-source one. Every 'no' is either a deliberate choice or a gap, and it's worth knowing which. Each line is tagged with its component, so you can see at a glance where a harness is thin.

### 32. Takeaways

Key points:
- The model decides; the harness does the rest
- Add components one at a time, for a reason
- Enforce rules in code, not in the prompt
- The repo is yours: start at harness/stages.py

Speaker notes: Four things. The model decides the next step; the harness does everything else. Add components one at a time, and know why each one is there. Enforce rules in code, not in the prompt. And the repo is small on purpose: start at harness/stages.py, which is the file we've been reading all along, and you can read the rest in an hour.

### 33. Questions?

Key points:
- Kestrel Desk is still running: ask it something

Speaker notes: That's the talk. Kestrel Desk is still running, so if a question is easier to answer by trying it, let's try it live. Otherwise, fire away.
