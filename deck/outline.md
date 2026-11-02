# Agent harness engineering: slide outline

Deck: `deck/Kestrel-Desk-Harness-Engineering.pptx` (16:9, light "paper workbench" theme matching the approved Kestrel Desk demo UI). Built by `deck/build_deck.js`.

Timing: about 25-30 min of slides, interleaved with five live demo stops (→ Demo slides). Speaker notes below are also in the .pptx notes pane.

Preview without PowerPoint: `deck/preview/grid-1.jpg` … `grid-4.jpg` (thumbnail grids of every slide, 9 per image, rendered by PowerPoint from this build).

CallLimit numbers on slide 16 (8 model calls, 10 tool calls per run) are read at build time from `CallLimit.__init__` defaults in harness/middleware.py.

## Snippet sources

Every code slide is cut at build time by `harness.stages.stage_snippet(s)` from the `# [stage:N]` marker blocks in `harness/*.py` (dedented, verbatim). Over-long lines are soft-wrapped on the slide with a muted ↪; no characters are changed.

- slide 8: harness/stages.py [stage:0] "A chatbot: a model and a prompt"
- slide 12: harness/stages.py [stage:1] "Context: company instructions and skills"
- slide 13: harness/context.py [stage:1] "Skills load on demand"
- slide 15: harness/tools_company.py [stage:2] "A tool is a typed, documented function"
- slide 17: harness/subagents.py [stage:2] "A subagent: its own prompt, a subset of tools, a cheaper model"
- slide 18: harness/stages.py [stage:2] "Actions: tools, a loop with middleware, a subagent"
- slide 20: harness/middleware.py [stage:3] "Who may use which tool, and what is never writable"
- slide 22: harness/tools_company.py [stage:3] "The tool checks what the model might get wrong"
- slide 23: harness/stages.py [stage:3] "Boundaries: roles, protected paths, human approval, audit"
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
- Does it know us? (sales): It guesses, or admits it doesn't know. Only the Model lights up.

Speaker notes: Switch to the browser, stage 0. Run 'Does it know us?' as sales. The prompt is: What do you know about Kestrel Software and our proposal process? Watch: the model either guesses about Kestrel or admits it doesn't know. Only the Model lights up, nothing else in the strip moves. That's our baseline. Then come back to the slides.

## Stage 1 · Context

### 10. Context: always-on instructions

Key points:
- company/AGENTS.md becomes the system prompt
- Facts the model can't guess
- Conventions: tone, format, citations
- Sent with every call: keep it short

Speaker notes: The first component is context: what the model knows before it starts. The cheapest, highest-leverage piece is an always-on instruction file, and we use company/AGENTS.md as the system prompt. It holds the facts the model can't guess, like our plans and prices and who the teams are, and the conventions we want followed. It's about 480 words, and that's on purpose: it's sent on every single call, so every line has to earn its place.

### 11. Context: skills, on demand

Key points:
- The prompt lists each skill: name + one line
- The model calls load_skill when it needs one
- The full SKILL.md enters context only then
- Why not stuff it all in: cost, distraction, scale

Speaker notes: But you can't put everything in the system prompt. Every token costs on every turn, and rules that don't apply to this task distract the model. So skills are procedures on demand. The prompt only lists each skill's name and its one-line description, straight from the SKILL.md frontmatter. When the model decides it needs one, it calls load_skill, and only then does the full text enter the conversation. That's progressive disclosure: the index is always there, the body only when needed.

### 12. Stage 1 in code

Key points:
- Agent(...) for stage 1; new keywords: instructions, skills
- AGENTS.md as the prompt; a skills index plus load_skill.

Speaker notes: In code, context is two keywords. instructions points at AGENTS.md; skills points at the skills folder. The harness builds the skills index from each SKILL.md's frontmatter and installs the load_skill tool for us. The loop itself hasn't changed at all. And look at the strip: Context is in, with the orange ring because we just added it.

### 13. load_skill is the whole mechanism

Key points:
- An unknown name raises a ToolError: the model gets the valid names back and can correct itself.

Speaker notes: And this is the tool the harness installs, the real code. It's eight lines. It looks the name up and returns the skill's body. Notice the error path: if the model asks for a skill that doesn't exist, it doesn't crash, it raises a ToolError, and the message goes back to the model with the list of valid names. Errors written for the model to read are a recurring pattern in a good harness.

### 14. → Demo: Stage 1 · Context

**Demo:** Switch to the browser: Stage 1 (Context)

Key points:
- Skill-guided draft (sales): load_skill fires and the draft follows the skill's sections. We still had to explain who Acme is.

Speaker notes: Back to the browser, stage 1. Run 'Skill-guided draft' as sales. The prompt asks it to use the proposal-writing skill to draft a proposal for Acme Robotics: Enterprise plan, 40 seats, they care about SSO and audit logs. You'll see load_skill fire and the Context card pulse, and the draft follows the skill's required sections. But notice we had to tell it who Acme is: it can't look anything up yet. That's the next component.

## Stage 2 · Actions

### 15. A tool is a typed, documented function

Key points:
- @tool turns the type hints and docstring into the schema the model sees. ctx is injected.

Speaker notes: The second component is actions. A tool is just a typed async function with a docstring. This is lookup_customer, exactly as it is in the repo. The @tool decorator reads the type hints and the docstring and generates the JSON schema the model sees; ctx is injected by the harness and never shown to the model. And again, when nothing matches, the error tells the model which customers do exist.

### 16. Actions: middleware in the loop

Key points:
- Small objects the loop calls at fixed points
- Hooks: before_model, after_model, before_tool, after_tool
- CallLimit: stops runaway loops
- TodoTracker: a visible plan via update_todos

Speaker notes: Once the model can act, we need a place to put rules about acting. Middleware is a small object the loop calls at fixed points: before and after each model call, and before and after each tool call. Two ship in stage 2. CallLimit counts calls, 8 model calls and 10 tool calls per run, and stops a runaway loop with a reason. TodoTracker gives the model an update_todos tool, so long tasks stay organized and we can watch its plan. Everything in the next stage, boundaries, is middleware too.

### 17. A subagent is a definition

Key points:
- Own prompt, one tool, a cheaper model, a clean context. Only its checklist comes back.

Speaker notes: Some work is better done in a separate room. A subagent has its own prompt, its own small set of tools, and runs on a cheaper model, here the subagent model from .env. It starts with a clean context, does its job, and hands back only a summary, so the main conversation doesn't fill up with its working. Our proposal-reviewer checks a draft against the customer record and returns three headings: Supported, Unsupported, Missing. It's just data; the harness turns it into a run_subagent tool.

### 18. Stage 2 in code

Key points:
- Agent(...) for stage 2; new keywords: tools, middleware, subagents
- Company tools, two middlewares, one subagent.

Speaker notes: Three new keywords: tools, middleware and subagents. The loop that runs tool calls was always there; now it finally has something to do. Notice the subagent is just the definition we saw, and the harness turns it into a run_subagent tool the main agent can call. In the strip, Context is blue and Actions has the orange ring.

### 19. → Demo: Stage 2 · Actions

**Demo:** Switch to the browser: Stage 2 (Actions)

Key points:
- Look it up yourself (sales): lookup_customer, a todo list, then the reviewer's nested check.
- Runaway loop (engineering): CallLimit stops the run and says why.

Speaker notes: Stage 2, two runs. First, 'Look it up yourself' as sales: draft a proposal for Acme Robotics and have the proposal-reviewer check it. Watch lookup_customer fire, the todo list appear, and the proposal-reviewer's nested card. Then switch the role to engineering and run 'Runaway loop'. The prompt basically asks it never to stop: for every open issue look up its customer, then every other issue, and check everything twice. CallLimit stops it with a clear reason.

## Stage 3 · Boundaries

### 20. Permissions live in code

Key points:
- A rule in the prompt is a suggestion. A rule in code is a guarantee.

Speaker notes: Third component: boundaries. Each role gets a set of tools; that's the ROLE_TOOLS table, real code. Sales can send proposals, engineering can look up issues, finance can see revenue. RoleGate checks that set before every tool call. And PROTECTED_PATHS lists what is never writable: the company files, the skills, and the harness's own code. This lives in code, not in the prompt. A prompt that says 'please don't' is a suggestion the model may or may not follow; a denied call is a guarantee. And the model gets the reason back, so it can explain instead of guessing.

### 21. Boundaries: the permission chain

Key points:
- RoleGate → ProtectedPaths → ApprovalGate → yours → AuditLog
- First deny wins
- ask beats allow: the loop waits for a human
- Every outcome lands in the audit log

Speaker notes: Every tool call runs through the same chain, in order: RoleGate, protected paths, the approval gate, then the rest of the middleware like CallLimit, and after the tool runs the audit log records the outcome. Each gate answers allow, ask or deny. The first deny wins. An ask beats an allow: the loop pauses and waits for a human to approve or reject. You'll see these decisions spelled out in the demo's event rows.

### 22. The tool checks, too

Key points:
- undefined

Speaker notes: Boundaries aren't only middleware. Here's send_proposal, the real code. It's marked as needing approval, so a human sees a card before it runs. And the tool itself refuses an email address that isn't the contact on record. Defense in depth: the model might hallucinate an address, the human might click approve too fast, the tool still says no. And it never sends a real email; it writes a file to the outbox. The arrows mark lines that wrap on the slide; in the source they're one line.

### 23. Stage 3 in code

Key points:
- Agent(...) for stage 3; new keywords: permissions, approve, protected_paths, audit
- Same tools as stage 2; now they run under rules.

Speaker notes: Four keywords: permissions, approve, protected_paths and audit. Notice what didn't change: the tools. send_proposal is the same function it was in stage 2; we just told the harness it needs a human. Boundaries now has the orange ring in the strip.

### 24. → Demo: Stage 3 · Boundaries

**Demo:** Switch to the browser: Stage 3 (Boundaries)

Key points:
- Wrong role (engineering): RoleGate denies get_revenue. The model says so, no guessing.
- Right role (finance): Same question, allowed, answered with record ids.
- Needs a human (sales): An approval card. Approve: an outbox file and an audit line.

Speaker notes: Stage 3, three runs. As engineering, ask: What was our revenue in FY2026? RoleGate denies get_revenue, and the model says so instead of guessing. Same question as finance: answered, with record ids. Then as sales, send the Acme Robotics proposal to ceo@acme-robotics.example with the subject Kestrel Enterprise proposal. An approval card appears, and the Boundaries card says waiting on you. Approve it and a file lands in the outbox, never a real email, plus an audit line. If the address isn't the contact on record, the tool itself rejects it.

## Stage 4 · Persistence

### 25. Persistence: save and resume

Key points:
- Every message checkpointed to SQLite
- List sessions; resume one tomorrow
- workspace/: the one folder it may write
- Writes elsewhere are blocked

Speaker notes: Fourth component: persistence. Until now, history lived in memory, so restart the server and it's gone. Now every message is checkpointed to SQLite, so you can list sessions and resume one tomorrow exactly where you left off. The agent also gets a workspace folder, the one place it may write files. Everything else, company files, skills, the harness code, stays protected by the boundaries we just added.

### 26. Writes are confined to workspace/

Key points:
- The path is resolved first, then checked. "../" can't climb out.

Speaker notes: Here's the write tool, real code. The interesting line is the comment: the path is resolved and then checked with is_relative_to, so tricks like dot-dot-slash end there. Combined with ProtectedPaths from stage 3, there are two independent checks between the model and the files we care about.

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

**Demo:** Switch to the browser: Stage 4 (Persistence)

Key points:
- Save it (sales): write_workspace_file and checkpoints tick up. Then try writing company/AGENTS.md.
- Come back tomorrow (sales): Resume the session: it answers from history. Then press Compact now.

Speaker notes: Stage 4. As sales, ask it to save the Acme proposal we discussed as workspace/acme-proposal.md. Watch the Persistence card and the checkpoint counter. Then ask it to write to company/AGENTS.md and see it blocked. Open the drawer, go to Sessions, resume the session, and ask: What did we save earlier, and what was in it? It answers from history without re-reading anything. Finally hit Compact now and look for the summary marker under the strip.

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
