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


# [stage:2] A tool is a typed, documented function
@tool(component="actions")
async def lookup_customer(name: str, ctx: RunContext) -> str:
    """Look up a Kestrel customer by (partial) company name.
    Returns the customer record: plan, seats, ARR, contact, renewal date and notes."""
    query = name.strip().lower()
    customers = _customers()
    exact = [c for c in customers if c["name"].lower() == query]
    matches = exact or [c for c in customers if query in c["name"].lower()]
    if not matches:
        raise ToolError(f"No customer matches '{name}'. Known: {', '.join(c['name'] for c in customers)}")
    return _pretty(matches[0] if len(matches) == 1 else matches)
# [/stage:2]


@tool(component="actions")
async def lookup_issue(query: str, ctx: RunContext) -> str:
    """Find customer issues by issue id (e.g. ISS-1043), or by text in the title or customer name.
    Use "open" to list every issue that is not resolved."""
    q = query.strip().lower()
    names = {c["id"]: c["name"] for c in _customers()}
    issues = _load("issues.json")
    if q == "open":
        hits = [i for i in issues if i["status"] != "resolved"]
    else:
        hits = [i for i in issues if i["id"].lower() == q] or [
            i for i in issues if q in i["title"].lower() or q in names.get(i["customer_id"], "").lower()]
    if not hits:
        raise ToolError(f"No issues match '{query}'.")
    return _pretty([{**i, "customer_name": names.get(i["customer_id"], "?")} for i in hits])


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


COMPANY_TOOLS = [lookup_customer, lookup_issue, get_revenue, send_proposal]
