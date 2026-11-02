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
  'tagline': 'The company file, always on: facts, prices and rules.',
  'headline': 'Tell it who we are',
  'problem': 'The model knows nothing about Kestrel, so it invents our prices and our rules. AGENTS.md is '
             'the always-on company file: who we are, our plans and prices, and the business rules every '
             'answer must follow. It rides in the system prompt of every call; nothing else about the call '
             'changes.',
  'bullets': ['company/AGENTS.md becomes the system prompt',
              'Facts: the company, plans and list prices',
              'Rules: discounts, tone, what we never promise',
              'Same single call as stage 0: no tools, no loop'],
  'unlocked_tools': [],
  'middlewares': [],
  'subagents': [],
  'new_keywords': ['instructions']},
 {'id': 2,
  'name': 'Actions',
  'component': 'actions',
  'tagline': 'Tools, the agent loop, middleware, skills on demand and a subagent.',
  'headline': 'Let it look things up itself',
  'problem': "AGENTS.md can't hold every customer record or every playbook, so we still had to tell it who "
             'Acme is. Now the model has to fetch facts and know-how itself: tools for our records, skills '
             'it loads only when a task needs them, a reviewer for its draft. A loop that keeps calling '
             'tools also needs a brake.',
  'bullets': ['Five company tools declared with @tool, run in a loop',
              'Skills listed by name; load_skill pulls one in on demand',
              'CallLimit middleware: a budget on every run',
              'A proposal-reviewer subagent with its own context'],
  'unlocked_tools': ['load_skill',
                     'list_customers',
                     'lookup_customer',
                     'lookup_issue',
                     'get_revenue',
                     'send_proposal',
                     'run_subagent'],
  'middlewares': ['CallLimit'],
  'subagents': ['proposal-reviewer'],
  'new_keywords': ['tools', 'middleware', 'skills', 'subagents']},
 {'id': 3,
  'name': 'Boundaries',
  'component': 'boundaries',
  'tagline': 'Role permissions, human approval, audit log.',
  'headline': 'Draw the lines in code',
  'problem': 'Now the agent can act, and it treats every user the same. An engineer can pull revenue, anyone '
             "can email a customer, and a prompt that says please don't is not a control. Permissions, "
             "approvals and an audit trail have to live in the harness, where the model can't talk its way "
             'past them.',
  'bullets': ['RoleGate: each role gets only its tools',
              "send_proposal pauses for a human's approval",
              'The tool itself rejects addresses not on record',
              'Every tool call is written to an audit log'],
  'unlocked_tools': [],
  'middlewares': ['RoleGate', 'ApprovalGate', 'CallLimit', 'AuditLog'],
  'subagents': ['proposal-reviewer'],
  'new_keywords': ['permissions', 'approve', 'audit']},
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
  'middlewares': ['RoleGate', 'ApprovalGate', 'CallLimit', 'AuditLog', 'Compactor'],
  'subagents': ['proposal-reviewer'],
  'new_keywords': ['checkpointer', 'workspace', 'compaction']}]

SCENARIOS: dict[int, list[dict]] = {0: [{'title': "Who's Acme?",
      'role': 'sales',
      'prompt': 'Who is Acme Robotics and when is their renewal due?',
      'watch': "It can't know. Nothing is around the model.",
      'resume': False},
     {'title': 'Price the renewal',
      'role': 'sales',
      'prompt': 'Draft a renewal proposal for Acme Robotics: 40 seats on our Enterprise plan, with pricing.',
      'watch': 'It invents a price, or asks for one. It has no idea what our plans cost.',
      'resume': False}],
 1: [{'title': 'Price the renewal, again',
      'role': 'sales',
      'prompt': 'Draft a renewal proposal for Acme Robotics: 40 seats on our Enterprise plan, with pricing.',
      'watch': 'Plan-table price ($2,400 per seat per year), our tone, our sections, no discount. Tokens in '
               'jumped: AGENTS.md rides on every call. We still had to say who Acme is.',
      'resume': False},
     {'title': 'Can I discount?',
      'role': 'sales',
      'prompt': 'Can I offer Acme 15% off to close this quarter?',
      'watch': '"No: above 10% needs written approval from finance", straight from AGENTS.md. A business '
               'rule, not a fact.',
      'resume': False}],
 2: [{'title': 'Prepare the renewal',
      'role': 'sales',
      'prompt': "Prepare Acme Robotics' renewal proposal: check their record and open issues, then have the "
                'proposal-reviewer check it before you show it to me.',
      'watch': 'load_skill pulls the playbook, lookup_customer and lookup_issue pull the facts, the reviewer '
               'runs as a nested subagent. The model fetched what it needed.',
      'resume': False},
     {'title': 'Account health, every customer',
      'role': 'engineering',
      'prompt': 'Give me an account health report for every customer: their record plus their open issues.',
      'watch': 'A realistic over-sized request. CallLimit denies the 11th tool call; the model reports '
               'partial results and says why.',
      'resume': False}],
 3: [{'title': 'Wrong role',
      'role': 'engineering',
      'prompt': 'What was our revenue in FY2026?',
      'watch': 'RoleGate denies get_revenue, in code, before it runs; the model says so instead of guessing.',
      'resume': False},
     {'title': 'Right role',
      'role': 'finance',
      'prompt': 'What was our revenue in FY2026?',
      'watch': 'Same question, allowed, answered with record ids.',
      'resume': False},
     {'title': 'Send it',
      'role': 'sales',
      'prompt': 'Draft a short renewal proposal for Acme Robotics (40 seats, Enterprise, SSO and audit logs) '
                'and send it to procurement@acme-robotics.example with the subject "Kestrel renewal '
                'proposal".',
      'watch': 'The approval card appears and the loop waits. Approve → outbox file + audit line. Variant: '
               'send to ceo@acme-robotics.example and the tool rejects the address as not on record.',
      'resume': False}],
 4: [{'title': 'Save the draft',
      'role': 'sales',
      'prompt': 'Draft a short renewal proposal for Acme Robotics (40 seats, Enterprise, SSO and audit '
                'logs), save it as workspace/acme-renewal.md, and add a line to company/AGENTS.md saying the '
                'Acme draft is done.',
      'watch': 'write_workspace_file writes the draft and checkpoints tick up; the AGENTS.md write is '
               'refused by the tool (outside workspace/), and the model reports it.',
      'resume': False},
     {'title': "Pick up yesterday's work",
      'role': 'sales',
      'prompt': 'Where did we leave off with Acme, and what did we save?',
      'watch': 'Run resumes the most recent saved session from SQLite (the divider says so) and answers from '
               'history. In the sidebar the session is highlighted.',
      'resume': True},
     {'title': 'Long day',
      'role': 'sales',
      'prompt': '',
      'watch': '9 → 7 messages, a compaction row with the summary.',
      'resume': False}]}

SNIPPETS: dict[int, list[dict]] = {0: [{'file': 'harness/stages.py',
      'title': 'A chatbot: a model and a prompt',
      'code': 'return Agent(model=llm, **common)'}],
 1: [{'file': 'harness/stages.py',
      'title': 'Context: the company file, always on',
      'code': 'return Agent(model=llm, instructions=COMPANY_DIR / "AGENTS.md", **common)'}],
 2: [{'file': 'harness/stages.py',
      'title': 'Actions: tools, a loop with middleware, skills on demand, a subagent',
      'code': 'return Agent(model=llm, instructions=COMPANY_DIR / "AGENTS.md",\n'
              '             tools=COMPANY_TOOLS, middleware=[CallLimit()],\n'
              '             skills=SKILLS_DIR, subagents=[PROPOSAL_REVIEWER], **common)'},
     {'file': 'harness/tools_company.py',
      'title': 'A tool is a typed, documented function',
      'code': '@tool(component="actions")\n'
              'async def lookup_customer(name: str, ctx: RunContext) -> str:\n'
              '    """Get ONE customer\'s full record by id (cust_acme) or company name (partial is fine):\n'
              '    plan, seats, ARR, contact, renewal date and notes."""\n'
              '    if len(name.strip()) < 2:\n'
              '        raise ToolError("Give at least 2 characters of a customer id or name.")\n'
              '    matches = _match_customers(name)\n'
              '    if not matches:\n'
              '        raise ToolError(f"No customer matches \'{name}\'. list_customers shows every '
              'customer.")\n'
              '    if len(matches) > 1:  # like a real CRM: a vague query gets a pick-list, never every '
              'record\n'
              '        picks = "\\n".join(f"- {c[\'id\']}: {c[\'name\']}" for c in matches)\n'
              '        return f"{len(matches)} customers match \'{name}\'; be more specific:\\n{picks}"\n'
              '    return _pretty(matches[0])'},
     {'file': 'harness/subagents.py',
      'title': 'A subagent: its own prompt, a subset of tools, a cheaper model',
      'code': 'PROPOSAL_REVIEWER = SubagentDef(\n'
              '    name="proposal-reviewer",\n'
              '    description="Checks a drafted proposal against the customer record and flags commitments '
              '"\n'
              '                "the record does not support. Use after drafting any proposal.",\n'
              '    system_prompt="You are a read-only proposal reviewer at Kestrel Software. If the task '
              'names a "\n'
              '                  "saved draft and you have read_workspace_file, read it. Call '
              'lookup_customer for "\n'
              '                  "the customer in the draft, then return a terse checklist with three '
              'headings: "\n'
              '                  "Supported, Unsupported, Missing. Cite the customer id. Do not rewrite the '
              'proposal.",\n'
              '    tools=["lookup_customer", "read_workspace_file"],  # only those the parent has are given\n'
              ')'}],
 3: [{'file': 'harness/stages.py',
      'title': 'Boundaries: roles, human approval, audit',
      'code': 'return Agent(model=llm, instructions=COMPANY_DIR / "AGENTS.md",\n'
              '             tools=COMPANY_TOOLS, middleware=[CallLimit()],\n'
              '             skills=SKILLS_DIR, subagents=[PROPOSAL_REVIEWER],\n'
              '             permissions=ROLE_TOOLS, approve={"send_proposal"}, audit=True, **common)'},
     {'file': 'harness/middleware.py',
      'title': 'Who may use which tool',
      'code': 'ROLE_TOOLS: dict[str, set[str]] = {\n'
              '    "sales":       {"list_customers", "lookup_customer", "send_proposal"},\n'
              '    "engineering": {"list_customers", "lookup_customer", "lookup_issue"},\n'
              '    "finance":     {"list_customers", "lookup_customer", "get_revenue"},\n'
              '}'},
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
      'code': 'return Agent(model=llm, instructions=COMPANY_DIR / "AGENTS.md",\n'
              '             tools=COMPANY_TOOLS, middleware=[CallLimit()],\n'
              '             skills=SKILLS_DIR, subagents=[PROPOSAL_REVIEWER],\n'
              '             permissions=ROLE_TOOLS, approve={"send_proposal"}, audit=True,\n'
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
