"""Company tools: the agent's hands on Kestrel's (synthetic) records.

Tools return text the model reads. They check facts the model might get wrong (an email
address, an unknown id) and raise ToolError with a message the model can act on.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from . import config
from .tooling import ToolError, tool

if TYPE_CHECKING:
    from .events import RunContext


def _load(name: str):
    return json.loads((config.DATA_DIR / name).read_text(encoding="utf-8"))


def _customers() -> list[dict]:
    return _load("customers.json")


def _customer_by_id(customer_id: str) -> dict:
    for c in _customers():
        if c["id"] == customer_id:
            return c
    raise ToolError(f"No customer with id '{customer_id}'. Use lookup_customer to find the id.")


def _pretty(value) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)


def _match_customers(query: str) -> list[dict]:
    """An exact id or name wins; otherwise a substring of the id or the name."""
    q = query.strip().lower()
    customers = _customers()
    exact = [c for c in customers if q in (c["id"].lower(), c["name"].lower())]
    return exact or [c for c in customers if q in c["id"].lower() or q in c["name"].lower()]


MAX_ISSUES = 10


@tool(component="actions")
async def list_customers(ctx: RunContext) -> str:
    """List every Kestrel customer: id, name and plan, one per line. Use lookup_customer for a full record."""
    return "\n".join(f"{c['id']}: {c['name']} ({c['plan']})" for c in _customers())


# [stage:2] A tool is a typed, documented function
@tool(component="actions")
async def lookup_customer(name: str, ctx: RunContext) -> str:
    """Get ONE customer's full record by id (cust_acme) or company name (partial is fine):
    plan, seats, ARR, contact, renewal date and notes."""
    if len(name.strip()) < 2:
        raise ToolError("Give at least 2 characters of a customer id or name.")
    matches = _match_customers(name)
    if not matches:
        raise ToolError(f"No customer matches '{name}'. list_customers shows every customer.")
    if len(matches) > 1:  # like a real CRM: a vague query gets a pick-list, never every record
        picks = "\n".join(f"- {c['id']}: {c['name']}" for c in matches)
        return f"{len(matches)} customers match '{name}'; be more specific:\n{picks}"
    return _pretty(matches[0])
# [/stage:2]


@tool(component="actions")
async def lookup_issue(query: str, ctx: RunContext) -> str:
    """Find customer issues by issue id (ISS-1043), by ONE customer's id or name, or by words
    from an issue title. Returns at most 10 issues with their status and severity."""
    q = query.strip().lower()
    if not q:
        raise ToolError("Give an issue id, a customer id or name, or words from an issue title.")
    names = {c["id"]: c["name"] for c in _customers()}
    issues = _load("issues.json")
    customers = _match_customers(q) if len(q) >= 2 else []
    hits = [i for i in issues if i["id"].lower() == q]
    if not hits and len(customers) == 1:  # one customer's issues
        c = customers[0]
        hits = [i for i in issues if i["customer_id"] == c["id"]]
        if not hits:
            return f"No issues on record for {c['name']} ({c['id']})."
    if not hits:  # words from a title
        hits = [i for i in issues if all(w in i["title"].lower() for w in q.split())]
    if not hits:
        raise ToolError(f"No issues match '{query}'.")
    return _pretty([{**i, "customer_name": names.get(i["customer_id"], "?")} for i in hits[:MAX_ISSUES]])


@tool(component="actions")
async def get_revenue(period: str, ctx: RunContext) -> str:
    """Get revenue records. period is a fiscal year ("FY2026"), a quarter ("FY2026-Q2"), or "ARR".
    Every record has an id to cite."""
    data = _load("revenue.json")
    p = period.strip().upper()
    if p == "ARR":
        records = data["arr_by_plan"]
    else:
        records = [q for q in data["quarters"] if q["period"] == p or q["period"].startswith(p + "-")]
        if not records:
            known = sorted({q["period"].split("-")[0] for q in data["quarters"]})
            raise ToolError(f"No revenue for '{period}'. Try one of {known}, a quarter like FY2026-Q2, or ARR.")
    return _pretty({"period": p, "currency": data["currency"], "records": records, "source": data["source"]})


# [stage:3] The tool checks what the model might get wrong
@tool(component="actions", read_only=False, requires_approval=True)
async def send_proposal(customer_id: str, to_email: str, subject: str, body_markdown: str,
                        ctx: RunContext) -> str:
    """Queue a proposal email to a customer's contact on record. A human must approve it first.
    Writes to the outbox; no real email is ever sent."""
    customer = _customer_by_id(customer_id)
    on_record = customer["contact_email"]
    if to_email.strip().lower() != on_record.lower():
        raise ToolError(f"Unverified address: {to_email} is not the contact on record ({on_record}).")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = config.OUTBOX_DIR / f"{stamp}_{customer_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f"To: {on_record}\nSubject: {subject}\nCustomer: {customer['name']} ({customer_id})\n\n"
    path.write_text(header + body_markdown, encoding="utf-8")
    return f"Queued to outbox: {path}"
# [/stage:3]


COMPANY_TOOLS = [list_customers, lookup_customer, lookup_issue, get_revenue, send_proposal]
