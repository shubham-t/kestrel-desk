"""Canned copies of the harness's talk metadata, for rehearsal mode (KESTREL_MOCK=1).

GENERATED from the running harness so the mock can never drift from the real snippets:

    .venv/Scripts/python -m app.mock_data      # rewrites this file from harness.stages

Do not hand-edit below the marker; rerun the command instead.
"""
from __future__ import annotations

# --- generated ---
HARNESS_STAGES: list[dict] = [{'id': 0,
  'name': 'Chatbot',
  'component': 'model',
  'tagline': 'A system prompt, a message list, one model call.',
  'headline': 'Just a model and a prompt',
  'problem': 'This is where most teams start: a system prompt, a message list and one model call. The model '
             "is capable, but it has never heard of Kestrel, our customers or how we write proposals. Let's "
             'see what it does with nothing around it.',
  'bullets': ['One system prompt: "You are a helpful assistant."',
              'A message list kept in memory',
              'One model call per turn, streamed',
              'No tools, no company knowledge, no memory across restarts'],
  'unlocked_tools': [],
  'middlewares': [],
  'subagents': [],
  'new_keywords': ['model']},
 {'id': 1,
  'name': 'Context',
  'component': 'context',
  'tagline': 'Company instructions always on; skills loaded on demand.',
  'headline': 'Tell it who we are',
  'problem': 'The model knows nothing about Kestrel, so every answer about us is a guess. Pasting every '
             'playbook into every prompt would bloat it and go stale. It needs standing instructions, plus '
             'know-how it pulls in only when a task calls for it.',
  'bullets': ['company/AGENTS.md is the always-on system prompt',
              'Skills are listed by name and description only',
              "load_skill pulls a skill's full text on demand"],
  'unlocked_tools': ['load_skill'],
  'middlewares': [],
  'subagents': [],
  'new_keywords': ['instructions', 'skills']},
 {'id': 2,
  'name': 'Actions',
  'component': 'actions',
  'tagline': 'Tools, the agent loop, middleware and a subagent.',
  'headline': 'Let it look things up itself',
  'problem': "With context alone, the model still can't see our records, so we had to tell it who Acme is. "
             'It needs tools to fetch facts, a loop that keeps going until the job is done, and a second '
             'pair of eyes on its draft. A loop also needs a brake, or one bad request runs forever.',
  'bullets': ['Four company tools declared with @tool',
              'The agent loop: model -> tools -> results -> model',
              'Middleware: CallLimit budgets, TodoTracker plans',
              'A proposal-reviewer subagent with its own context'],
  'unlocked_tools': ['lookup_customer',
                     'lookup_issue',
                     'get_revenue',
                     'send_proposal',
                     'update_todos',
                     'run_subagent'],
  'middlewares': ['CallLimit', 'TodoTracker'],
  'subagents': ['proposal-reviewer'],
  'new_keywords': ['tools', 'middleware', 'subagents']},
 {'id': 3,
  'name': 'Boundaries',
  'component': 'boundaries',
  'tagline': 'Role permissions, protected paths, human approval, audit log.',
  'headline': 'Draw the lines in code',
  'problem': 'Now the agent can act, and it treats every user the same. An engineer can pull revenue, anyone '
             "can email a customer, and a prompt that says please don't is not a control. Permissions, "
             "approvals and an audit trail have to live in the harness, where the model can't talk its way "
             'past them.',
  'bullets': ['RoleGate: each role gets only its tools',
              'ProtectedPaths: company files and code are never writable',
              "send_proposal pauses for a human's approval",
              'Every tool call is written to an audit log'],
  'unlocked_tools': [],
  'middlewares': ['RoleGate', 'ProtectedPaths', 'ApprovalGate', 'CallLimit', 'TodoTracker', 'AuditLog'],
  'subagents': ['proposal-reviewer'],
  'new_keywords': ['permissions', 'approve', 'protected_paths', 'audit']},
 {'id': 4,
  'name': 'Persistence',
  'component': 'persistence',
  'tagline': 'Checkpoints, a writable workspace, context compaction.',
  'headline': 'Remember, save, and keep going',
  'problem': 'Everything so far lives in memory: restart the server and the conversation is gone, and '
             'nothing the agent writes survives. Long sessions also keep growing until the prompt is too big '
             'and too slow. We need checkpoints to resume, one safe folder to write in, and a way to shrink '
             'old turns.',
  'bullets': ['Every message checkpointed to SQLite; sessions resume',
              'A writable workspace/ with file tools',
              'Compactor summarizes old turns when the prompt grows'],
  'unlocked_tools': ['write_workspace_file', 'read_workspace_file', 'list_workspace_files'],
  'middlewares': ['RoleGate',
                  'ProtectedPaths',
                  'ApprovalGate',
                  'CallLimit',
                  'TodoTracker',
                  'AuditLog',
                  'Compactor'],
  'subagents': ['proposal-reviewer'],
  'new_keywords': ['checkpointer', 'workspace', 'compaction']}]

SCENARIOS: dict[int, list[dict]] = {0: [{'title': 'Does it know us?',
      'role': 'sales',
      'prompt': 'What do you know about Kestrel Software and our proposal process?',
      'watch': "The model guesses or admits it doesn't know. Nothing lights up but the model."}],
 1: [{'title': 'Skill-guided draft',
      'role': 'sales',
      'prompt': 'Use the proposal-writing skill to draft a proposal for Acme Robotics: Enterprise plan, 40 '
                'seats, they care about SSO and audit logs.',
      'watch': "load_skill fires (Context node), and the draft follows the skill's sections. We still had to "
               'explain who Acme is.'}],
 2: [{'title': 'Look it up yourself',
      'role': 'sales',
      'prompt': 'Draft a proposal for Acme Robotics and have the proposal-reviewer check it before you show '
                'it to me.',
      'watch': "lookup_customer, a todo list, then the subagent's nested review."},
     {'title': 'Runaway loop',
      'role': 'engineering',
      'prompt': 'For every open issue, look up its customer, then look up every other issue for that '
                'customer, and keep going until you have checked everything twice.',
      'watch': 'CallLimit stops it.'}],
 3: [{'title': 'Wrong role',
      'role': 'engineering',
      'prompt': 'What was our revenue in FY2026?',
      'watch': 'RoleGate denies get_revenue; the model says so instead of guessing.'},
     {'title': 'Right role',
      'role': 'finance',
      'prompt': 'What was our revenue in FY2026?',
      'watch': 'Same question, allowed, answered with record ids.'},
     {'title': 'Needs a human',
      'role': 'sales',
      'prompt': 'Draft a short Enterprise proposal for Acme Robotics (40 seats, SSO and audit logs) and send '
                'it to procurement@acme-robotics.example with the subject "Kestrel Enterprise proposal".',
      'watch': 'The approval card appears and the loop waits. Approve -> an outbox file and an audit line. '
               'Try the same with ceo@acme-robotics.example: the tool rejects the unverified address.'}],
 4: [{'title': 'Save it',
      'role': 'sales',
      'prompt': 'Draft a short Enterprise proposal for Acme Robotics (40 seats, SSO and audit logs) and save '
                'it as workspace/acme-proposal.md. Give me the path.',
      'watch': 'write_workspace_file (Persistence node); checkpoint events. Also show a write to '
               'company/AGENTS.md being blocked.'},
     {'title': 'Come back tomorrow',
      'role': 'sales',
      'prompt': 'What did we save earlier, and what was in it?',
      'watch': 'Resume the previous session first: resumed history answers without re-reading. Then trigger '
               'compaction on a long session and show the summary marker.'}]}

SNIPPETS: dict[int, list[dict]] = {0: [{'file': 'harness/stages.py',
      'title': 'A chatbot: a model and a prompt',
      'code': 'return Agent(model=llm, **common)'}],
 1: [{'file': 'harness/stages.py',
      'title': 'Context: company instructions and skills',
      'code': 'return Agent(model=llm, instructions=COMPANY_DIR / "AGENTS.md", skills=SKILLS_DIR, **common)'},
     {'file': 'harness/context.py',
      'title': 'Skills load on demand',
      'code': '@tool(component="context")\n'
              'async def load_skill(name: str, ctx: RunContext) -> str:\n'
              '    """Load the full instructions of a skill listed in the system prompt.\n'
              '    Call it before doing the kind of task the skill covers."""\n'
              '    if name not in by_name:\n'
              '        raise ToolError(f"Unknown skill \'{name}\'. Valid names: {\', \'.join(by_name)}")\n'
              '    return by_name[name].body'}],
 2: [{'file': 'harness/stages.py',
      'title': 'Actions: tools, a loop with middleware, a subagent',
      'code': 'return Agent(model=llm, instructions=COMPANY_DIR / "AGENTS.md", skills=SKILLS_DIR,\n'
              '             tools=COMPANY_TOOLS, middleware=[CallLimit(), TodoTracker()],\n'
              '             subagents=[PROPOSAL_REVIEWER], **common)'},
     {'file': 'harness/tools_company.py',
      'title': 'A tool is a typed, documented function',
      'code': '@tool(component="actions")\n'
              'async def lookup_customer(name: str, ctx: RunContext) -> str:\n'
              '    """Look up a Kestrel customer by (partial) company name.\n'
              '    Returns the customer record: plan, seats, ARR, contact, renewal date and notes."""\n'
              '    query = name.strip().lower()\n'
              '    customers = _customers()\n'
              '    exact = [c for c in customers if c["name"].lower() == query]\n'
              '    matches = exact or [c for c in customers if query in c["name"].lower()]\n'
              '    if not matches:\n'
              '        raise ToolError(f"No customer matches \'{name}\'. Known: {\', \'.join(c[\'name\'] for '
              'c in customers)}")\n'
              '    return _pretty(matches[0] if len(matches) == 1 else matches)'},
     {'file': 'harness/subagents.py',
      'title': 'A subagent: its own prompt, a subset of tools, a cheaper model',
      'code': 'PROPOSAL_REVIEWER = SubagentDef(\n'
              '    name="proposal-reviewer",\n'
              '    description="Checks a drafted proposal against the customer record and flags commitments '
              '"\n'
              '                "the record does not support. Use after drafting any proposal.",\n'
              '    system_prompt="You are a read-only proposal reviewer at Kestrel Software. Call '
              'lookup_customer "\n'
              '                  "for the customer in the draft, then return a terse checklist with three '
              'headings: "\n'
              '                  "Supported, Unsupported, Missing. Cite the customer id. Do not rewrite the '
              'proposal.",\n'
              '    tools=["lookup_customer"],\n'
              ')'}],
 3: [{'file': 'harness/stages.py',
      'title': 'Boundaries: roles, protected paths, human approval, audit',
      'code': 'return Agent(model=llm, instructions=COMPANY_DIR / "AGENTS.md", skills=SKILLS_DIR,\n'
              '             tools=COMPANY_TOOLS, middleware=[CallLimit(), TodoTracker()],\n'
              '             subagents=[PROPOSAL_REVIEWER], permissions=ROLE_TOOLS,\n'
              '             approve={"send_proposal"}, protected_paths=PROTECTED_PATHS, audit=True, '
              '**common)'},
     {'file': 'harness/middleware.py',
      'title': 'Who may use which tool, and what is never writable',
      'code': 'ROLE_TOOLS: dict[str, set[str]] = {\n'
              '    "sales":       {"lookup_customer", "send_proposal"},\n'
              '    "engineering": {"lookup_customer", "lookup_issue"},\n'
              '    "finance":     {"lookup_customer", "get_revenue"},\n'
              '}\n'
              '\n'
              'PROTECTED_PATHS = [config.COMPANY_DIR, config.SKILLS_DIR,\n'
              '                   config.REPO_ROOT / "harness", config.REPO_ROOT / "app"]'},
     {'file': 'harness/tools_company.py',
      'title': 'The tool checks what the model might get wrong',
      'code': '@tool(component="actions", read_only=False, requires_approval=True)\n'
              'async def send_proposal(customer_id: str, to_email: str, subject: str, body_markdown: str,\n'
              '                        ctx: RunContext) -> str:\n'
              '    """Queue a proposal email to a customer\'s contact on record. A human must approve it '
              'first.\n'
              '    Writes to the outbox; no real email is ever sent."""\n'
              '    customer = _customer_by_id(customer_id)\n'
              '    on_record = customer["contact_email"]\n'
              '    if to_email.strip().lower() != on_record.lower():\n'
              '        raise ToolError(f"Unverified address: {to_email} is not the contact on record '
              '({on_record}).")\n'
              '    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")\n'
              '    path = config.OUTBOX_DIR / f"{stamp}_{customer_id}.md"\n'
              '    path.parent.mkdir(parents=True, exist_ok=True)\n'
              '    header = f"To: {on_record}\\nSubject: {subject}\\nCustomer: {customer[\'name\']} '
              '({customer_id})\\n\\n"\n'
              '    path.write_text(header + body_markdown, encoding="utf-8")\n'
              '    return f"Queued to outbox: {path}"'}],
 4: [{'file': 'harness/stages.py',
      'title': 'Persistence: checkpoints, a workspace, compaction',
      'code': 'return Agent(model=llm, instructions=COMPANY_DIR / "AGENTS.md", skills=SKILLS_DIR,\n'
              '             tools=COMPANY_TOOLS, middleware=[CallLimit(), TodoTracker()],\n'
              '             subagents=[PROPOSAL_REVIEWER], permissions=ROLE_TOOLS,\n'
              '             approve={"send_proposal"}, protected_paths=PROTECTED_PATHS, audit=True,\n'
              '             checkpointer=store or SessionStore(), workspace=WORKSPACE_DIR,\n'
              '             compaction=Compactor(at_tokens=settings.compact_at_tokens), **common)'},
     {'file': 'harness/tools_workspace.py',
      'title': 'Writes are confined to workspace/',
      'code': '@tool(component="persistence", read_only=False)\n'
              'async def write_workspace_file(path: str, content: str, ctx: RunContext) -> str:\n'
              '    """Save a text file under workspace/ (e.g. "acme-proposal.md"). Overwrites if it '
              'exists."""\n'
              '    target = _inside_workspace(path)  # resolve() + is_relative_to: "../" tricks end here\n'
              '    if target == config.WORKSPACE_DIR.resolve():\n'
              '        raise ToolError("Give a file name, not the workspace folder itself.")\n'
              '    target.parent.mkdir(parents=True, exist_ok=True)\n'
              '    target.write_text(content, encoding="utf-8")\n'
              '    return f"Saved {len(content)} characters to {_display(target)}"'},
     {'file': 'harness/compaction.py',
      'title': 'What compaction asks the model to keep',
      'code': 'COMPACTION_PROMPT = (\n'
              '    "Summarize this conversation for your future self: decisions made, facts looked up "\n'
              '    "(with record ids), files saved (with paths), and open items. Be terse; bullets are fine. '
              '"\n'
              '    "Anything you leave out is forgotten."\n'
              ')'}]}


if __name__ == "__main__":
    import dataclasses
    import pprint
    from pathlib import Path

    from harness.stages import describe_stage, scenarios, stage_snippet

    ids = range(5)
    blocks = [
        "HARNESS_STAGES: list[dict] = " + pprint.pformat([describe_stage(s) for s in ids], width=110, sort_dicts=False),
        "SCENARIOS: dict[int, list[dict]] = " + pprint.pformat(
            {s: [dataclasses.asdict(x) for x in scenarios(s)] for s in ids}, width=110, sort_dicts=False),
        "SNIPPETS: dict[int, list[dict]] = " + pprint.pformat({s: stage_snippet(s) for s in ids},
                                                               width=110, sort_dicts=False),
    ]
    path = Path(__file__)
    src = path.read_text(encoding="utf-8")
    head, _, rest = src.partition("# --- generated ---\n")
    _, _, tail = rest.partition("\n\n\nif __name__")
    path.write_text(head + "# --- generated ---\n" + "\n\n".join(blocks) + "\n\n\nif __name__" + tail, encoding="utf-8")
    print(f"Wrote {path.name}: {len(blocks)} blocks from harness.stages")
