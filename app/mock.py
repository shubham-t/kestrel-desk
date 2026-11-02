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
ROLE_TOOLS = {"sales": {"list_customers", "lookup_customer", "send_proposal"},
              "engineering": {"list_customers", "lookup_customer", "lookup_issue"},
              "finance": {"list_customers", "lookup_customer", "get_revenue"}}
TOOL_COMPONENT = {"load_skill": "context", "write_workspace_file": "persistence",
                  "read_workspace_file": "persistence", "list_workspace_files": "persistence"}
KEEP_LAST = 6  # KESTREL_KEEP_LAST_MESSAGES default


def _prompt(stage: int, title: str, default: str) -> str:
    """The scenario prompt as the harness wrote it (falls back to SPEC.md's wording)."""
    return next((s["prompt"] for s in SCENARIOS.get(stage, []) if s["title"] == title), default)


P_WHO = _prompt(0, "Who's Acme?", "Who is Acme Robotics and when is their renewal due?")
P_PRICE = _prompt(0, "Price the renewal",
                  "Draft a renewal proposal for Acme Robotics: 40 seats on our Enterprise plan, with pricing.")
P_DISCOUNT = _prompt(1, "Can I discount?", "Can I offer Acme 15% off to close this quarter?")
P_PREPARE = _prompt(2, "Prepare the renewal",
                    "Prepare Acme Robotics' renewal proposal: check their record and open issues, then have the "
                    "proposal-reviewer check it before you show it to me.")
P_HEALTH = _prompt(2, "Account health, every customer",
                   "Give me an account health report for every customer: their record plus their open issues.")
P_REVENUE = _prompt(3, "Wrong role", "What was our revenue in FY2026?")
P_SEND = _prompt(3, "Send it",
                 "Draft a short renewal proposal for Acme Robotics (40 seats, Enterprise, SSO and audit logs) and send "
                 'it to procurement@acme-robotics.example with the subject "Kestrel renewal proposal".')
P_SAVE = _prompt(4, "Save the draft",
                 "Draft a short renewal proposal for Acme Robotics (40 seats, Enterprise, SSO and audit logs), save it "
                 "as workspace/acme-renewal.md, and add a line to company/AGENTS.md saying the Acme draft is done.")
P_RESUME = _prompt(4, "Pick up yesterday's work", "Where did we leave off with Acme, and what did we save?")

# Synthetic records, matching company/data/*.json so rehearsal answers look like live ones.
ACME = {"id": "cust_acme", "name": "Acme Robotics", "industry": "Industrial automation", "plan": "Growth",
        "seats": 25, "arr_usd": 54000, "contact_name": "Dana Whitfield",
        "contact_email": "procurement@acme-robotics.example", "renewal_date": "2027-03-31",
        "notes": "Evaluating an upgrade to the Enterprise plan for 40 seats. Security review requires SAML SSO "
                 "and exportable audit logs. Asked about a multi-year discount (not approved). Procurement is "
                 "the contact for all proposals."}
CUSTOMERS = [("cust_acme", "Acme Robotics", "Growth"), ("cust_northwind", "Northwind Freight", "Enterprise"),
             ("cust_blueharbor", "Blue Harbor Health", "Enterprise"), ("cust_lumen", "Lumen Grove Education", "Starter"),
             ("cust_ironbark", "Ironbark Mining Co", "Growth"), ("cust_pinecrest", "Pinecrest Credit Union", "Growth"),
             ("cust_tidewater", "Tidewater Studios", "Starter")]
ACME_ISSUES = [{"id": "ISS-1043", "customer_id": "cust_acme", "title": "Audit log export missing actor IP",
                "severity": "S2", "status": "open"},
               {"id": "ISS-1044", "customer_id": "cust_acme", "title": "Robot fleet dashboard slow to load",
                "severity": "S3", "status": "resolved"}]
SKILL_BODY = ("# Proposal writing (company-wide)\n\nRequired sections: Summary, Their goals, Proposed plan, "
              "What is included, Open items, Next steps.\nTone: plain and specific, no superlatives.\n"
              "Never promise: discounts finance has not approved, roadmap dates, fixes by a date.")
PROPOSAL = ("## Summary\nUpgrade Acme Robotics (cust_acme) from Growth to **Enterprise** at 40 seats, which covers "
            "the SAML SSO and audit log export their security review requires.\n\n## Their goals\n"
            "- Pass the security review (SAML SSO, exportable audit logs)\n- Grow from 25 to 40 seats\n\n"
            "## Proposed plan\nEnterprise, 40 seats × $2,400 per seat per year = **$96,000 per year**.\n\n"
            "## What is included\nSAML SSO, audit log export, US/EU data residency, 99.9% SLA, a named CSM.\n\n"
            "## Open items\n- ISS-1043 (S2, open): audit log export is missing the actor IP\n"
            "- The multi-year discount they asked about is not approved\n\n"
            "## Next steps\nProcurement (procurement@acme-robotics.example) reviews before the 2027-03-31 renewal.\n\n"
            "Prepared by Kestrel Desk for review.")
REVIEW = ("**Supported**\n- Enterprise, 40 seats: the record (cust_acme) notes the evaluation\n"
          "- SAML SSO and audit export: required by their security review\n\n"
          "**Unsupported**\n- \"Multi-year discount\": the record says it was not approved\n\n"
          "**Missing**\n- ISS-1043 (S2, open) should be named under Open items")
SUMMARY = ("[Conversation summary]\n- Drafted a Kestrel Enterprise renewal proposal for Acme Robotics (cust_acme): "
           "40 seats × $2,400 = $96,000/yr, SAML SSO, audit log export\n- Saved it as workspace/acme-renewal.md\n"
           "- The edit to company/AGENTS.md was refused: only workspace/ is writable\n"
           "- Open items: ISS-1043 (S2), send to procurement once approved")
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
    """Helpers that emit the real loop's event sequences for one scripted run, and keep the history
    shaped like the real one (assistant message with tool_calls, then one tool message per call)."""
    def __init__(self, agent: "MockAgent", queue: asyncio.Queue, sub: str | None = None) -> None:
        self.a, self.q, self.sub = agent, queue, sub
        self.model_calls = self.tool_calls = self.prompt_tokens = self.completion_tokens = 0
        self.last: dict | None = None  # the assistant message tool calls attach to

    def _append(self, msg: dict) -> None:
        if not self.sub:  # a subagent has its own message list
            self.a.messages.append(msg)

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
        self.last = {"role": "assistant", "content": text}
        self._append(self.last)
        await self.checkpoint()
        return text

    async def call(self, name, args, gap=(0.35, 0.6)) -> str:
        self.tool_calls += 1
        cid = f"call_{uuid.uuid4().hex[:6]}"
        if self.last is None:
            self.last = {"role": "assistant", "content": ""}
            self._append(self.last)
        self.last.setdefault("tool_calls", []).append(
            {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}})
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
        self._append({"role": "tool", "tool_call_id": cid, "content": result})
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

    async def checkpoint(self):
        if self.a.stage >= 4 and not self.sub:
            await self.emit("checkpoint", {"session_id": self.a.session_id, "messages": len(self.a.messages)},
                            "persistence")


# ---------------------------------------------------------------- scripts (one per scenario prompt)
async def s_who(r: _Run, text: str) -> str:
    if r.a.stage >= 2:
        await r.model()
        await r.tool("lookup_customer", {"name": "Acme Robotics"}, json.dumps(ACME, indent=2))
        return await r.model("**Acme Robotics** (cust_acme) is an industrial automation customer on Growth with 25 seats "
                             "($54,000 ARR). Their renewal is due **2027-03-31**; they're evaluating Enterprise at 40 seats.")
    if r.a.stage == 1:
        return await r.model("Our company instructions cover Kestrel's plans, prices and rules, but not individual "
                             "customer records. I can't tell you who Acme Robotics is or when they renew without a "
                             "lookup tool or you telling me.")
    return await r.model("I don't have any information about a company called Acme Robotics or its contracts. I'm not "
                         "connected to your CRM or any internal records, so I can't tell you when their renewal is due.\n\n"
                         "If you share their account details, I can help you plan the renewal.")


async def s_price(r: _Run, text: str) -> str:
    if r.a.stage == 0:
        return await r.model(
            "# Renewal proposal: Acme Robotics\n\n**Plan:** Enterprise, 40 seats\n\n**Pricing:** Enterprise plans "
            "typically run **$50–$100 per seat per month**. At $75/seat/month, 40 seats comes to **$36,000 per year**. "
            "_(Please confirm your actual list price; I don't know your pricing.)_\n\n**Why renew:** continued support, "
            "new features, priority onboarding.\n\nI can add a 15% multi-year discount to make it more compelling.")
    if r.a.stage >= 2:
        await r.tool("load_skill", {"name": "proposal-writing"}, SKILL_BODY)
        await r.tool("lookup_customer", {"name": "Acme Robotics"}, json.dumps(ACME, indent=2))
        return await r.model("# Proposal: Acme Robotics — Enterprise\n\n" + PROPOSAL)
    return await r.model(
        "# Proposal: Acme Robotics — Enterprise\n\n## Summary\nMove Acme Robotics to Kestrel **Enterprise** for 40 seats.\n\n"
        "## Proposed plan\nEnterprise, 40 seats × $2,400 per seat per year = **$96,000 per year** (25-seat minimum met).\n\n"
        "## What is included\nSAML SSO, audit log export, US/EU data residency, 99.9% SLA, a named CSM.\n\n"
        "## Open items\nNo discount is included: anything above 10% needs written approval from finance.\n\n"
        "## Next steps\nConfirm Acme's current plan, contact and renewal date; I have no customer record to check them.\n\n"
        "Prepared by Kestrel Desk for review.")


async def s_discount(r: _Run, text: str) -> str:
    if r.a.stage == 0:
        return await r.model("15% to close this quarter is a common lever. If the deal is strategic and the customer is "
                             "ready to sign, it's usually reasonable; just make it time-bound and tie it to a signed "
                             "order by quarter end.")
    return await r.model("**No, not on your own.** Our rule is that discounts above 10% need written approval from "
                         "finance, and we never offer one without it.\n\nIf you want to pursue 15%, get finance's written "
                         "approval first; until then, the proposal stays at list price.")


async def subagent_review(r: _Run, task: str, read_path: str = "", body: str = "") -> str:
    sub = "proposal-reviewer"
    cid = await r.call("run_subagent", {"name": sub, "task": task})
    await r.emit("decision", {"id": cid, "tool": "run_subagent", "action": "allow", "reason": "", "silent": True}, "actions")
    await r.emit("subagent_start", {"name": sub, "task": task}, "actions")
    child = _Run(r.a, r.q, sub)
    await child.emit("run_start", {"session_id": f"{r.a.session_id}:{sub}", "stage": r.a.stage, "role": r.a.role,
                                   "text": task})
    await child.model("Checking the draft against the record.")
    if read_path:  # stage 4: the reviewer reads the saved draft itself
        await child.tool("read_workspace_file", {"path": read_path}, body)
    await child.tool("lookup_customer", {"name": "cust_acme"}, json.dumps(ACME, indent=2))
    await child.model("\n\n" + REVIEW)
    await child.emit("text_done", {"text": REVIEW}, "model")
    await child.emit("run_end", {"session_id": f"{r.a.session_id}:{sub}", "model_calls": child.model_calls,
                                 "tool_calls": child.tool_calls, "prompt_tokens": child.prompt_tokens,
                                 "completion_tokens": child.completion_tokens, "error": False, "stopped": False})
    await r.emit("subagent_end", {"name": sub, "ok": True, "preview": REVIEW[:400]}, "actions")
    await r.result(cid, "run_subagent", REVIEW, True, {"name": sub, "task": task})
    return REVIEW


async def s_prepare(r: _Run, text: str) -> str:
    await r.model("I'll pull our proposal playbook, then Acme's record and open issues.")
    await r.tool("load_skill", {"name": "proposal-writing"}, SKILL_BODY)
    await r.model()
    await r.tool("lookup_customer", {"name": "cust_acme"}, json.dumps(ACME, indent=2))
    await r.tool("lookup_issue", {"query": "cust_acme"}, json.dumps(ACME_ISSUES, indent=2))
    await r.model("Draft ready. Sending it to proposal-reviewer before I show you.")
    await subagent_review(r, "Review this Acme Robotics renewal draft against the customer record and flag "
                             "unsupported commitments.")
    return await r.model("\n\nThe reviewer flagged an unapproved multi-year discount, so it stays out.\n\n"
                         "# Proposal: Acme Robotics — Enterprise\n\n" + PROPOSAL)


async def s_health(r: _Run, text: str) -> str:
    await r.model("I'll list every customer, then pull each record and its open issues.")
    await r.tool("list_customers", {}, "\n".join(f"{c}: {n} ({p})" for c, n, p in CUSTOMERS))
    for i in range(10):  # CallLimit: 10 tool calls per run; list_customers was the 1st, so the 11th is denied
        cid, name, _ = CUSTOMERS[i // 2]
        if i % 2 == 0:
            await r.model(think=(0.12, 0.22))
            await r.tool("lookup_customer", {"name": cid}, json.dumps({"id": cid, "name": name}), gap=(0.2, 0.3))
        elif i < 9:
            await r.tool("lookup_issue", {"query": cid}, f'[{{"customer_id": "{cid}", "status": "open"}}]', gap=(0.2, 0.3))
        else:
            await r.tool("lookup_issue", {"query": cid}, deny_component="actions",
                         deny="Tool call limit reached (10 per run). Stop calling tools and answer with what you have.")
    return await r.model("The harness stopped me at its limit of 10 tool calls per run, so this report is partial.\n\n"
                         "| Customer | Plan | Open issues |\n|---|---|---|\n| Acme Robotics | Growth | ISS-1043 (S2) |\n"
                         "| Northwind Freight | Enterprise | **ISS-1041 (S1)** |\n| Blue Harbor Health | Enterprise | ISS-1046 (S4) |\n"
                         "| Lumen Grove Education | Starter | ISS-1049 (S4) |\n| Ironbark Mining Co | Growth | not checked |\n\n"
                         "Not covered: Ironbark's issues, Pinecrest Credit Union, Tidewater Studios. Ask for those and I'll finish.")


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


async def _draft(r: _Run) -> None:
    await r.model("I'll check Acme's record and our proposal format, then draft.")
    await r.tool("lookup_customer", {"name": "Acme Robotics"}, json.dumps(ACME, indent=2))
    await r.tool("load_skill", {"name": "proposal-writing"}, SKILL_BODY)


async def s_send(r: _Run, text: str) -> str:
    if r.a.stage < 2:
        return await r.model("I can't send email: I have no tools at this stage. Here's a draft you could send yourself.")
    await _draft(r)
    to = (re.search(r"[\w.+-]+@[\w.-]+\w", text) or [ACME["contact_email"]])[0]
    m = re.search(r'subject\s+"([^"]+)"', text)
    args = {"customer_id": "cust_acme", "to_email": to, "subject": m.group(1) if m else "Kestrel renewal proposal",
            "body_markdown": "# Proposal: Acme Robotics — Enterprise\n\n" + PROPOSAL}
    if r.a.stage >= 3 and "send_proposal" not in ROLE_TOOLS.get(r.a.role, set()):
        await r.model()
        await r.tool("send_proposal", args, deny=f"Role '{r.a.role}' is not allowed to use send_proposal. Allowed: "
                     + ", ".join(sorted(ROLE_TOOLS[r.a.role])) + ".")
        return await r.model("Your role can't send proposals; the harness blocked it. Ask someone in sales.")
    await r.model(f"Drafted the renewal: Enterprise, 40 seats, $96,000/yr. Sending it to {to}"
                  + ("; this one needs your approval." if r.a.stage >= 3 else "."))
    if r.a.stage < 3:  # no ApprovalGate yet: it just runs
        cid, approved = await r.call("send_proposal", args), True
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
                             f"Proposals go to **{ACME['contact_email']}**. Two layers, two checks.")
    name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_cust_acme.md"
    path = f".harness_state/outbox/{name}"
    r.a.backend.outbox_files.insert(0, {"name": name, "path": path, "size": 1284, "modified": time.time(),
                                        "preview": f"To: {to}\nSubject: {args['subject']}"})
    await r.result(cid, "send_proposal", f"Queued to outbox: {path}", True, args, outcome)
    return await r.model(f"Done: queued to the outbox at `{path}`. Nothing leaves the building; the outbox is a folder.")


async def s_save(r: _Run, text: str) -> str:
    # History stays 7 messages (user, write, result, write + reviewer, 2 results, answer), so with
    # Pick up yesterday's work the session is 9 messages and Long day compacts it to 7.
    await r.model("Drafted from what you gave me. Saving it first.")
    body = "# Proposal: Acme Robotics — Enterprise\n\n" + PROPOSAL
    await r.tool("write_workspace_file", {"path": "acme-renewal.md", "content": body},
                 f"Saved {len(body)} characters to workspace/acme-renewal.md")
    await r.model("Now the AGENTS.md note, and a reviewer check of the saved file.")
    await r.tool("write_workspace_file", {"path": "company/AGENTS.md", "content": "- The Acme renewal draft is done."},
                 "Tool error: Path 'company/AGENTS.md' is outside workspace/. Only workspace/ is writable.", ok=False)
    await subagent_review(r, "Review workspace/acme-renewal.md against Acme's customer record.", "acme-renewal.md", body)
    return await r.model("Saved the draft to **workspace/acme-renewal.md** (Enterprise, 40 seats, $96,000/yr); the "
                         "proposal-reviewer read it back and flagged only the unapproved multi-year discount, which "
                         "the draft already leaves out.\n\nI could not add the line to `company/AGENTS.md`: the file "
                         "tool refuses any path outside `workspace/`. Someone with repo access can add it, or I can "
                         "save the note under workspace/.")


async def s_protected(r: _Run, text: str) -> str:
    await r.model("I'll make that edit.")
    await r.tool("write_workspace_file", {"path": "company/AGENTS.md", "content": "# Kestrel Software\n(updated)"},
                 "Tool error: Path 'company/AGENTS.md' is outside workspace/. Only workspace/ is writable.", ok=False)
    return await r.model("I can't write there: the file tools only write inside `workspace/`. I can save the proposed "
                         "change as `workspace/AGENTS-proposed.md` for review.")


async def s_resume(r: _Run, text: str) -> str:
    if len(r.a.messages) < 3:
        return await r.model("I don't see an earlier conversation in this session. Pick one from the Sessions list, "
                             "or run 'Save the draft' first.")
    return await r.model("We left off with Acme's renewal draft:\n\n- Saved **workspace/acme-renewal.md**: Enterprise, "
                         "40 seats × $2,400 = $96,000/yr, SAML SSO and audit log export\n- The note in "
                         "`company/AGENTS.md` was refused (outside workspace/), so it still needs adding\n"
                         "- Open: ISS-1043 (S2) and sending it to procurement\n\n"
                         "I answered from this session's saved history, without re-reading the file.")


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


# prompt -> script (scripts adapt to the stage they run at)
SCRIPTS = {P_WHO: s_who, P_PRICE: s_price, P_DISCOUNT: s_discount, P_PREPARE: s_prepare, P_HEALTH: s_health,
           P_REVENUE: s_revenue, P_SEND: s_send, P_SAVE: s_save, P_RESUME: s_resume}
MIN_STAGE = {s_prepare: 2, s_health: 2, s_save: 4, s_resume: 4}


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _pick(stage: int, text: str):
    t = _norm(text)
    for prompt, fn in SCRIPTS.items():  # scenario prompts arrive verbatim from the drawer: match the whole text
        if _norm(prompt) == t:
            return fn if stage >= MIN_STAGE.get(fn, 0) else s_generic
    if stage >= 4 and "agents.md" in t:  # free-text variants the presenter may type
        return s_protected
    if stage >= 2 and "send" in t and "@" in t:
        return s_send
    if stage >= 2 and "revenue" in t:
        return s_revenue
    return s_generic


async def compact(agent: "MockAgent", emit) -> dict:
    """The Compactor's visible effect: older turns become one summary message, the last KEEP_LAST stay."""
    before = len(agent.messages)
    cut = before - KEEP_LAST
    while 0 < cut < before and agent.messages[cut].get("role") == "tool":  # never orphan a tool result
        cut -= 1
    agent.messages[:] = [{"role": "user", "content": SUMMARY}] + agent.messages[cut:]
    await emit("compaction", {"before": before, "after": len(agent.messages), "summarized": cut,
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
        self.base_tokens = [40, 1850, 2600, 2900, 3300][min(stage, 4)]

    async def run(self, text: str):
        q: asyncio.Queue = asyncio.Queue()
        r = _Run(self, q)

        async def script():
            await r.emit("run_start", {"session_id": self.session_id, "stage": self.stage, "role": self.role, "text": text})
            self.messages.append({"role": "user", "content": text})
            self.backend.touch(self)
            await r.checkpoint()
            err = None
            try:
                final = await _pick(self.stage, text)(r, text)  # the last model() call appended the answer
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
    """Everything server.py needs, without `harness`. Sessions start empty, like a fresh SQLite file."""
    mock = True

    def __init__(self) -> None:
        self.approver = MockApprover()
        self.roles = list(ROLES)
        self.audit_lines: list[dict] = []
        self.outbox_files: list[dict] = []
        self.sessions: dict[str, dict] = {}

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
            first = next((m["content"] for m in agent.messages if m.get("role") == "user"
                          and not str(m.get("content", "")).startswith("[Conversation summary]")), "")
            if not rec["title"] and first:
                rec["title"] = str(first)[:60]

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
        if len(agent.messages) <= KEEP_LAST + 2:
            return {"compacted": False, "reason": f"Not enough history to compact yet ({len(agent.messages)} messages)."}
        await _pause(0.8, 1.2)  # the real Compactor makes one summarizing model call
        self.touch(agent)
        return {"compacted": True, **await compact(agent, emit)}
