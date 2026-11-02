"""Rehearsal mode for the Kestrel Desk web app (enabled with KESTREL_MOCK=1).

Why this exists: the presenter must be able to rehearse without a key or network, and on
talk day this is the fallback if the model endpoint is down. It serves canned /api/meta
data (copied from the harness by `python -m app.mock_data`) and scripted event streams with
the same shapes `harness.loop.Agent.run()` emits, so the UI cannot tell the difference.
It never imports `harness` at runtime.
"""
from __future__ import annotations

import asyncio
import json
import random
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .mock_data import HARNESS_STAGES, SCENARIOS, SNIPPETS

ROLES = ["sales", "engineering", "finance"]
ROLE_TOOLS = {"sales": {"lookup_customer", "send_proposal"},
              "engineering": {"lookup_customer", "lookup_issue"},
              "finance": {"lookup_customer", "get_revenue"}}
TOOL_COMPONENT = {"load_skill": "context", "write_workspace_file": "persistence",
                  "read_workspace_file": "persistence", "list_workspace_files": "persistence"}


def _prompt(stage: int, title: str) -> str:
    return next(s["prompt"] for s in SCENARIOS[stage] if s["title"] == title)


P_KNOW = _prompt(0, "Does it know us?")
P_SKILL = _prompt(1, "Skill-guided draft")
P_LOOKUP = _prompt(2, "Look it up yourself")
P_RUNAWAY = _prompt(2, "Runaway loop")
P_REVENUE = _prompt(3, "Wrong role")
P_SEND = _prompt(3, "Needs a human")
P_SAVE = _prompt(4, "Save it")
P_RESUME = _prompt(4, "Come back tomorrow")

# Synthetic records, matching company/data/*.json so rehearsal answers look like live ones.
ACME = {"id": "cust_acme", "name": "Acme Robotics", "industry": "Industrial automation", "plan": "Growth",
        "seats": 25, "arr_usd": 54000, "contact_name": "Dana Whitfield",
        "contact_email": "procurement@acme-robotics.example", "renewal_date": "2027-03-31",
        "notes": "Evaluating an upgrade to the Enterprise plan for 40 seats. Security review requires SAML SSO "
                 "and exportable audit logs. Asked about a multi-year discount (not approved). Procurement is "
                 "the contact for all proposals."}
SKILL_BODY = ("# Proposal writing (company-wide)\n\nRequired sections: Summary, Their goals, Proposed plan, "
              "Security & compliance, Timeline, Next steps.\nTone: plain, specific, no superlatives.\n"
              "Never promise: roadmap dates, custom SLAs, discounts finance has not approved.")
PROPOSAL = ("## Summary\nKestrel **Enterprise** for Acme Robotics (cust_acme): an upgrade from Growth to 40 seats "
            "with SAML SSO and exportable audit logs.\n\n## Their goals\n- Pass the security review (SAML SSO, audit export)\n"
            "- Grow from 25 to 40 seats\n\n## Proposed plan\n40 seats × $150/seat/month × 12 = **$72,000/yr**.\n\n"
            "## Security & compliance\nSAML SSO, audit log export, SOC 2 Type II report under NDA.\n\n"
            "## Next steps\nSecurity review call with procurement, then an order form before the 2027-03-31 renewal.")
REVIEW = ("**Supported**\n- Upgrade to Enterprise, 40 seats: the record (cust_acme) notes the evaluation\n"
          "- SAML SSO and audit export: required by their security review\n\n"
          "**Unsupported**\n- \"Multi-year discount\": the record says it was not approved\n\n"
          "**Missing**\n- Renewal date 2027-03-31\n- Contact: procurement@acme-robotics.example")
SUMMARY = ("[Conversation summary]\n- Drafted a Kestrel Enterprise proposal for Acme Robotics (cust_acme): 40 seats, "
           "SAML SSO, audit log export, $72,000/yr\n- proposal-reviewer removed an unapproved multi-year discount\n"
           "- Saved as workspace/acme-proposal.md\n- Open item: send to procurement once approved")
REVENUE = {"FY2026-Q1": 7889000, "FY2026-Q2": 8175000, "FY2026-Q3": 8473000, "FY2026-Q4": 8783000}


@dataclass
class MockEvent:
    """Same shape as harness.events.Event.to_json()."""
    kind: str
    data: dict
    component: str | None = None
    subagent: str | None = None
    ts: float = field(default_factory=time.time)

    def to_json(self) -> dict:
        return {"kind": self.kind, "data": self.data, "component": self.component,
                "subagent": self.subagent, "ts": self.ts}


class MockApprover:
    """Mirror of harness.approvals.FutureApprover: one Future per request id."""
    def __init__(self) -> None:
        self.pending: dict[str, asyncio.Future] = {}

    async def ask(self, req_id: str, timeout: float = 600) -> bool:
        fut = asyncio.get_running_loop().create_future()
        self.pending[req_id] = fut
        try:
            return bool(await asyncio.wait_for(fut, timeout))
        except asyncio.TimeoutError:
            return False
        finally:
            self.pending.pop(req_id, None)

    def resolve(self, req_id: str, approved: bool) -> bool:
        fut = self.pending.get(req_id)
        if fut is None or fut.done():
            return False
        fut.set_result(bool(approved))
        return True


async def _pause(lo: float, hi: float | None = None) -> None:
    await asyncio.sleep(lo if hi is None else random.uniform(lo, hi))


class _Run:
    """Helpers that emit the real loop's event sequences for one scripted run."""
    def __init__(self, agent: "MockAgent", queue: asyncio.Queue, sub: str | None = None) -> None:
        self.a, self.q, self.sub = agent, queue, sub
        self.model_calls = self.tool_calls = self.prompt_tokens = self.completion_tokens = 0
        self._n = 0

    async def emit(self, kind, data=None, component=None, sub=None):
        await self.q.put(MockEvent(kind, data or {}, component, sub or self.sub))

    async def model(self, text: str = "", think=(0.45, 0.8)) -> str:
        self.model_calls += 1
        await _pause(*think)
        for word in re.findall(r"\s*\S+", text):
            await self.emit("text_delta", {"text": word}, "model")
            await asyncio.sleep(0.022)
        pt = self.a.base_tokens + 180 * len(self.a.messages) + 260 * self.tool_calls + random.randint(20, 90)
        ct = max(12, int(len(text.split()) * 1.4)) + random.randint(8, 30)
        self.prompt_tokens += pt
        self.completion_tokens += ct
        model = "claude-haiku-5-5" if self.sub else "claude-sonnet-5-5"
        await self.emit("usage", {"model": model, "prompt_tokens": pt, "completion_tokens": ct}, "model")
        await self.checkpoint()
        return text

    async def call(self, name, args, gap=(0.35, 0.6)) -> str:
        self._n += 1
        self.tool_calls += 1
        cid = f"call_{uuid.uuid4().hex[:6]}"
        await self.emit("tool_call", {"id": cid, "name": name, "arguments": args}, TOOL_COMPONENT.get(name, "actions"))
        await _pause(*gap)
        return cid

    async def tool(self, name, args, result="", ok=True, deny: str = "", deny_component="boundaries",
                   gap=(0.35, 0.6)) -> str | None:
        cid = await self.call(name, args, gap)
        comp = TOOL_COMPONENT.get(name, "actions")
        if deny:
            await self.emit("decision", {"id": cid, "tool": name, "action": "deny", "reason": deny, "silent": False},
                            deny_component)
            await self.result(cid, name, f"Blocked by harness: {deny}", False, args, "deny")
            return None
        await self.emit("decision", {"id": cid, "tool": name, "action": "allow", "reason": "", "silent": True}, comp)
        await _pause(gap[0] * 0.6, gap[1] * 0.8)
        await self.result(cid, name, result, ok, args, "allow")
        return result

    async def result(self, cid, name, result, ok, args, outcome="allow"):
        comp = TOOL_COMPONENT.get(name, "actions")
        await self.emit("tool_result", {"id": cid, "name": name, "ok": ok, "outcome": outcome,
                                        "preview": result[:400]}, comp)
        if self.a.stage >= 3 and not self.sub:
            line = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "session_id": self.a.session_id,
                    "role": self.a.role, "tool": name, "args": json.dumps(args)[:300], "ok": ok, "decision": outcome}
            self.a.backend.audit_lines.append(line)
            await self.emit("audit", line, "boundaries")
        await self.checkpoint()

    async def ask(self, name, args) -> tuple[str, bool]:
        cid = await self.call(name, args)
        await self.emit("decision", {"id": cid, "tool": name, "action": "ask",
                                     "reason": f"{name} needs a human's approval.", "silent": False}, "boundaries")
        rid = uuid.uuid4().hex[:12]
        await self.emit("approval_request", {"request_id": rid, "call_id": cid, "tool": name, "arguments": args,
                                             "reason": f"{name} needs a human's approval."}, "boundaries")
        approved = await self.a.backend.approver.ask(rid)
        await self.emit("approval_result", {"request_id": rid, "tool": name, "approved": approved}, "boundaries")
        return cid, approved

    async def todos(self, *statuses):
        texts = ["Look up Acme Robotics", "Load the proposal-writing skill", "Draft the proposal",
                 "Get a proposal-reviewer check"]
        await self.emit("todo_update", {"items": [{"text": t, "status": s} for t, s in zip(texts, statuses)]}, "actions")

    async def checkpoint(self):
        if self.a.stage >= 4 and not self.sub:
            await self.emit("checkpoint", {"session_id": self.a.session_id, "messages": len(self.a.messages)},
                            "persistence")


# ---------------------------------------------------------------- scripts (one per scenario)
async def s_know(r: _Run, text: str) -> str:
    if r.a.stage == 0:
        return await r.model(
            "I don't have specific information about Kestrel Software or your internal proposal process. I'm not "
            "connected to your company's documents or systems, so anything specific would be a guess.\n\n"
            "Typical B2B SaaS proposal processes look like this:\n\n- **Discovery**: understand needs and constraints\n"
            "- **Drafting**: scope, pricing, timeline, terms\n- **Review**: legal, finance and leadership sign-off\n"
            "- **Delivery**: send, follow up, negotiate\n\nShare your team's guidelines and I'll follow them.")
    await r.model("From our company instructions: Kestrel Software sells B2B SaaS; the teams are sales, engineering and finance.")
    await r.tool("load_skill", {"name": "proposal-writing"}, SKILL_BODY)
    return await r.model("\n\nOur proposal process (proposal-writing skill):\n\n- Required sections: Summary, Their goals, "
                         "Proposed plan, Security & compliance, Timeline, Next steps\n- Plain, specific tone\n"
                         "- Never promise roadmap dates, custom SLAs, or discounts finance has not approved")


async def s_skill(r: _Run, text: str) -> str:
    await r.model("I'll load the proposal-writing skill first so the draft follows our house format.")
    await r.tool("load_skill", {"name": "proposal-writing"}, SKILL_BODY)
    return await r.model("\n\n# Proposal: Acme Robotics\n\n" + PROPOSAL +
                         "\n\n_Note: I have no customer record for Acme, so plan and seats are as you described._")


async def subagent_review(r: _Run, task: str) -> str:
    sub = "proposal-reviewer"
    cid = await r.call("run_subagent", {"name": sub, "task": task})
    await r.emit("decision", {"id": cid, "tool": "run_subagent", "action": "allow", "reason": "", "silent": True}, "actions")
    await r.emit("subagent_start", {"name": sub, "task": task}, "actions")
    child = _Run(r.a, r.q, sub)
    await child.emit("run_start", {"session_id": f"{r.a.session_id}:{sub}", "stage": r.a.stage, "role": r.a.role,
                                   "text": task})
    await child.model("Checking the draft against the record.")
    await child.tool("lookup_customer", {"name": "Acme Robotics"}, json.dumps(ACME, indent=2))
    await child.model("\n\n" + REVIEW)
    await child.emit("text_done", {"text": REVIEW}, "model")
    await child.emit("run_end", {"session_id": f"{r.a.session_id}:{sub}", "model_calls": child.model_calls,
                                 "tool_calls": child.tool_calls, "prompt_tokens": child.prompt_tokens,
                                 "completion_tokens": child.completion_tokens, "error": False, "stopped": False})
    await r.emit("subagent_end", {"name": sub, "ok": True, "preview": REVIEW[:400]}, "actions")
    await r.result(cid, "run_subagent", REVIEW, True, {"name": sub, "task": task})
    return REVIEW


async def s_lookup(r: _Run, text: str) -> str:
    await r.model("Plan first, then the record.")
    items = [{"text": t, "status": "pending"} for t in ["Look up Acme Robotics", "Load the proposal-writing skill",
                                                         "Draft the proposal", "Get a proposal-reviewer check"]]
    await r.tool("update_todos", {"items": items}, "ok (4 items)")
    await r.todos("in_progress", "pending", "pending", "pending")
    await r.model()
    await r.tool("lookup_customer", {"name": "Acme Robotics"}, json.dumps(ACME, indent=2))
    await r.todos("done", "in_progress", "pending", "pending")
    if r.a.stage >= 1:
        await r.tool("load_skill", {"name": "proposal-writing"}, SKILL_BODY)
    await r.todos("done", "done", "in_progress", "pending")
    await r.model("Draft ready: Enterprise, 40 seats, SSO, audit export, and a multi-year discount. "
                  "Sending it to proposal-reviewer before I show you.")
    await r.todos("done", "done", "done", "in_progress")
    await subagent_review(r, "Review this Acme Robotics draft against the customer record and flag unsupported commitments.")
    await r.todos("done", "done", "done", "done")
    return await r.model("\n\nThe reviewer caught one unsupported commitment, so I fixed it before showing you.\n\n"
                         "# Proposal: Acme Robotics\n\n" + PROPOSAL +
                         "\n\n**Review notes applied:** removed the multi-year discount (not approved); renewal date added.")


async def s_runaway(r: _Run, text: str) -> str:
    await r.model("Starting with the open issues.")
    await r.tool("lookup_issue", {"query": "open"},
                 '[{"id": "ISS-1041", "customer_id": "cust_northwind"}, {"id": "ISS-1043", "customer_id": "cust_acme"}, ...]')
    customers = ["Northwind Freight", "Acme Robotics", "Blue Harbor Health", "Pinecrest Credit Union", "Tidewater Studios"]
    for i in range(9):  # CallLimit default: 10 tool calls per run, so the 11th is denied
        if i % 2 == 0:
            await r.model(think=(0.12, 0.22))
            c = customers[(i // 2) % len(customers)]
            await r.tool("lookup_customer", {"name": c}, json.dumps({"name": c}), gap=(0.25, 0.35))
        else:
            await r.tool("lookup_issue", {"query": customers[(i // 2) % len(customers)]},
                         f'[{{"id": "ISS-10{41 + i % 10}", "status": "open"}}]', gap=(0.25, 0.35))
    await r.model(think=(0.2, 0.3))
    await r.tool("lookup_customer", {"name": "Acme Robotics"}, deny_component="actions",
                 deny="Tool call limit reached (10 per run). Stop calling tools and answer with what you have.")
    return await r.model("The harness stopped me at its 10 tool-call limit, which is the right call: this request "
                         "never terminates on its own. What I covered:\n\n- 5 of 7 open issues, across 5 customers\n"
                         "- Northwind Freight has an open **S1** (ISS-1041)\n\nWant a bounded version, such as one pass "
                         "over S1–S2 issues only?")


async def s_revenue(r: _Run, text: str) -> str:
    allowed = r.a.stage < 3 or "get_revenue" in ROLE_TOOLS.get(r.a.role, set())
    await r.model()
    if not allowed:
        ok = ", ".join(sorted(ROLE_TOOLS[r.a.role]))
        await r.tool("get_revenue", {"period": "FY2026"},
                     deny=f"Role '{r.a.role}' is not allowed to use get_revenue. Allowed: {ok}.")
        return await r.model(f"I can't pull revenue figures for the **{r.a.role}** role: the harness blocked "
                             f"`get_revenue` (allowed: {ok}). I won't guess at numbers; someone in finance can run this.")
    quarters = [{"id": f"rev-{p}", "period": p, "total": v} for p, v in REVENUE.items()]
    await r.tool("get_revenue", {"period": "FY2026"}, json.dumps({"period": "FY2026", "quarters": quarters,
                 "source": "Synthetic FP&A export (demo data only)"}, indent=2))
    lines = "\n".join(f"- {p[-2:]}: ${v / 1e6:.2f}M (`rev-{p}`)" for p, v in REVENUE.items())
    return await r.model(f"**FY2026 revenue: ${sum(REVENUE.values()) / 1e6:.2f}M**\n\n{lines}\n\n"
                         "Steady growth of about 3.6% quarter over quarter. Source: synthetic FP&A export.")


async def _send(r: _Run, to: str) -> str:
    args = {"customer_id": "cust_acme", "to_email": to, "subject": "Kestrel Enterprise proposal",
            "body_markdown": "# Kestrel Enterprise proposal\n\n" + PROPOSAL}
    if r.a.stage >= 3 and "send_proposal" not in ROLE_TOOLS.get(r.a.role, set()):
        await r.tool("send_proposal", args, deny=f"Role '{r.a.role}' is not allowed to use send_proposal. Allowed: "
                     + ", ".join(sorted(ROLE_TOOLS[r.a.role])) + ".")
        return await r.model("Your role can't send proposals; the harness blocked it. Ask someone in sales.")
    if r.a.stage < 3:  # no ApprovalGate yet: it just runs
        cid = await r.call("send_proposal", args)
        approved = True
    else:
        cid, approved = await r.ask("send_proposal", args)
    if not approved:
        await r.result(cid, "send_proposal", "User rejected the action.", False, args, "rejected")
        return await r.model("Understood, nothing was sent. The draft is unchanged if you want to edit it first.")
    await _pause(0.3, 0.5)
    outcome = "approved" if r.a.stage >= 3 else "allow"
    if to.lower() != ACME["contact_email"]:
        await r.result(cid, "send_proposal", f"Tool error: Unverified address: {to} is not the contact on record "
                       f"({ACME['contact_email']}).", False, args, outcome)
        return await r.model(f"You approved it, but the tool itself refused: **{to}** isn't Acme's contact on record. "
                             f"Proposals go to **{ACME['contact_email']}**. Two layers, two checks.\n\n"
                             "Want me to send it there instead?")
    name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_cust_acme.md"
    path = f".harness_state/outbox/{name}"
    r.a.backend.outbox_files.insert(0, {"name": name, "path": path, "size": 1284, "modified": time.time(),
                                        "preview": f"To: {to}\nSubject: Kestrel Enterprise proposal"})
    await r.result(cid, "send_proposal", f"Queued to outbox: {path}", True, args, outcome)
    return await r.model(f"Done: queued to the outbox at `{path}`. Nothing leaves the building; the outbox is a folder.\n\n"
                         "_Variant: ask for the same send to ceo@acme-robotics.example and the tool itself rejects the "
                         "unverified address, even after you approve._")


async def _draft(r: _Run) -> None:
    """First half of the self-contained stage 3/4 prompts: look up Acme, load the skill, draft."""
    await r.model("I'll check Acme's record and our proposal format, then draft.")
    await r.tool("lookup_customer", {"name": "Acme Robotics"}, json.dumps(ACME, indent=2))
    await r.tool("load_skill", {"name": "proposal-writing"}, SKILL_BODY)
    await r.model("Drafted a short Enterprise proposal for Acme Robotics (cust_acme): 40 seats, SAML SSO, "
                  "audit export, $72,000/yr.")


async def s_send(r: _Run, text: str) -> str:
    if r.a.stage < 2:
        return await r.model("I can't send email: I have no tools at this stage. Here's a draft you could send yourself.")
    await _draft(r)
    m = re.search(r"[\w.+-]+@[\w.-]+\w", text)
    to = m.group(0) if m else ACME["contact_email"]
    await r.model(f" Sending it to {to}" + ("; this one needs your approval." if r.a.stage >= 3 else "."))
    return await _send(r, to)


async def s_save(r: _Run, text: str) -> str:
    if "draft" in text.lower():
        await _draft(r)
    await r.model(" Saving it to the workspace.")
    await r.tool("write_workspace_file", {"path": "acme-proposal.md", "content": "# Proposal: Acme Robotics\n\n" + PROPOSAL},
                 "Saved 1284 characters to workspace/acme-proposal.md")
    return await r.model("Saved: **workspace/acme-proposal.md**. This conversation is checkpointed too, so we can pick it up tomorrow.")


async def s_protected(r: _Run, text: str) -> str:
    await r.model("I'll make that edit.")
    await r.tool("write_workspace_file", {"path": "../company/AGENTS.md", "content": "# Kestrel Software\n(updated)"},
                 deny="'../company/AGENTS.md' is under protected path company/.")
    return await r.model("I can't write there: the harness only allows writes inside `workspace/`, and `company/AGENTS.md` "
                         "is protected. I can save the proposed change as `workspace/AGENTS-proposed.md` for review.")


async def s_resume(r: _Run, text: str) -> str:
    if len(r.a.messages) < 3:
        return await r.model("I don't see an earlier conversation in this session. Resume one from the Sessions list.")
    await compact(r.a, r.emit)
    return await r.model("Earlier we saved **workspace/acme-proposal.md**: the Kestrel Enterprise proposal for Acme Robotics.\n\n"
                         "- 40 seats on Enterprise, SAML SSO, audit log export\n- $72,000/yr\n"
                         "- Next step: security review call with procurement\n\n"
                         "I answered from the saved conversation; I didn't need to re-read the file.")


async def s_generic(r: _Run, text: str) -> str:
    if "/error" in text:
        await _pause(0.6)
        raise RuntimeError("Error code: 529 - upstream overloaded (scripted failure)")
    if r.a.stage == 0:
        return await r.model("I'm a plain chatbot at this stage: one prompt, one call, no tools and no company context. "
                             "I'll do my best from general knowledge, but I can't look anything up.")
    return await r.model("Rehearsal mode has scripted answers for the scenario prompts. Free-form questions get this "
                         f"placeholder; with a live model, stage {r.a.stage} would answer using its "
                         f"{HARNESS_STAGES[r.a.stage]['name'].lower()} components.")


# prompt -> (script, first stage whose tools the script needs)
SCRIPTS = {P_KNOW: (s_know, 0), P_SKILL: (s_skill, 1), P_LOOKUP: (s_lookup, 2), P_RUNAWAY: (s_runaway, 2),
           P_REVENUE: (s_revenue, 2), P_SEND: (s_send, 0), P_SAVE: (s_save, 4), P_RESUME: (s_resume, 4)}


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _pick(stage: int, text: str):
    t = _norm(text)
    for prompt, (fn, min_stage) in SCRIPTS.items():  # scenario prompts arrive verbatim from the drawer
        if _norm(prompt) == t:
            return fn if stage >= min_stage else s_generic
    if stage >= 4 and "agents.md" in t:  # free-text variants the presenter may type
        return s_protected
    if stage >= 2 and "send" in t and "@" in t:
        return s_send
    if stage >= 4 and "save" in t:
        return s_save
    if stage >= 2 and "revenue" in t:
        return s_revenue
    return s_generic


async def compact(agent: "MockAgent", emit) -> dict:
    """The Compactor's visible effect: older turns become one summary message."""
    before = len(agent.messages)
    keep = min(2, len(agent.messages))
    agent.messages[:] = [{"role": "user", "content": SUMMARY}] + agent.messages[len(agent.messages) - keep:]
    await emit("compaction", {"before": before, "after": len(agent.messages), "summarized": before - keep,
                              "summary_preview": SUMMARY[len("[Conversation summary]\n"):][:400]}, "persistence")
    if agent.stage >= 4:
        await emit("checkpoint", {"session_id": agent.session_id, "messages": len(agent.messages)}, "persistence")
    return {"before": before, "after": len(agent.messages)}


class MockAgent:
    """Quacks like harness.loop.Agent: .messages, .resumed and async-iterator .run(text)."""
    def __init__(self, backend: "MockBackend", stage: int, role: str, session_id: str, messages: list[dict]):
        self.backend, self.stage, self.role, self.session_id = backend, stage, role, session_id
        self.messages = messages
        self.resumed = bool(messages)
        self.base_tokens = [40, 1850, 2600, 2900, 3300][stage]

    async def run(self, text: str):
        q: asyncio.Queue = asyncio.Queue()
        r = _Run(self, q)

        async def script():
            await r.emit("run_start", {"session_id": self.session_id, "stage": self.stage, "role": self.role, "text": text})
            self.messages.append({"role": "user", "content": text})
            await r.checkpoint()
            err = None
            try:
                final = await _pick(self.stage, text)(r, text)
                self.messages.append({"role": "assistant", "content": final})
                await r.checkpoint()
                await r.emit("text_done", {"text": final}, "model")
            except Exception as exc:  # scripted failures surface exactly like real ones
                err = str(exc)
                await r.emit("error", {"message": err, "type": type(exc).__name__, "status": 529})
            self.backend.touch(self)
            await r.emit("run_end", {"session_id": self.session_id, "model_calls": r.model_calls, "tool_calls": r.tool_calls,
                                     "prompt_tokens": r.prompt_tokens, "completion_tokens": r.completion_tokens,
                                     "error": bool(err), "stopped": False})
            await q.put(None)

        task = asyncio.create_task(script())
        try:
            while (ev := await q.get()) is not None:
                yield ev
        finally:
            task.cancel()


class MockBackend:
    """Everything server.py needs, without `harness`."""
    mock = True

    def __init__(self) -> None:
        self.approver = MockApprover()
        self.roles = list(ROLES)
        self.audit_lines: list[dict] = []
        self.outbox_files: list[dict] = []
        now = time.time()
        convo = [P_LOOKUP, "Here's the reviewed Acme proposal ...", "Tighten the pricing section.", "Updated pricing ...",
                 P_SAVE, "Saved: workspace/acme-proposal.md", "Add the renewal date to next steps.", "Added 2027-03-31."]
        self.sessions: dict[str, dict] = {"7f3a9c21b0de": {
            "session_id": "7f3a9c21b0de", "stage": 4, "role": "sales", "title": P_LOOKUP[:60],
            "created_at": now - 86400, "updated_at": now - 85000,
            "messages": [{"role": "user" if i % 2 == 0 else "assistant", "content": c} for i, c in enumerate(convo)]}}

    def meta(self) -> dict:
        return {"model": "claude-sonnet-5-5", "base_url_host": "offline rehearsal", "mock": True,
                "stages": HARNESS_STAGES, "roles": ROLES, "scenarios": SCENARIOS, "snippets": SNIPPETS}

    def new_agent(self, stage: int, role: str, session_id: str, resume: bool):
        rec = self.sessions.get(session_id) if stage >= 4 else None
        msgs = rec["messages"] if rec else []
        if stage >= 4 and rec is None:
            self.sessions[session_id] = {"session_id": session_id, "stage": stage, "role": role, "title": "",
                                         "created_at": time.time(), "updated_at": time.time(), "messages": msgs}
        agent = MockAgent(self, stage, role, session_id, msgs)
        return agent, list(msgs), agent.resumed

    def touch(self, agent: MockAgent) -> None:
        rec = self.sessions.get(agent.session_id)
        if rec is not None:
            rec["updated_at"] = time.time()
            if not rec["title"] and agent.messages:
                rec["title"] = str(agent.messages[0]["content"])[:60]

    def list_sessions(self) -> list[dict]:
        rows = [{k: v for k, v in s.items() if k != "messages"} | {"message_count": len(s["messages"])}
                for s in self.sessions.values() if s["messages"]]
        return sorted(rows, key=lambda s: s["updated_at"], reverse=True)

    def audit(self, limit: int) -> list[dict]:
        return self.audit_lines[-limit:]

    def outbox(self) -> list[dict]:
        return self.outbox_files

    async def compact(self, agent: MockAgent, put) -> dict:
        async def emit(kind, data=None, component=None, sub=None):
            put(MockEvent(kind, data or {}, component, sub).to_json())
        if len(agent.messages) < 3:
            return {"compacted": False, "reason": "Not enough history to compact yet."}
        return {"compacted": True, **await compact(agent, emit)}
