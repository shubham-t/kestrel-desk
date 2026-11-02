---
name: issue-triage
description: Engineering guide for triaging customer issues — severity rubric, triage steps, and the output format.
---
# Issue triage (engineering)

Use this when asked to triage, prioritize or summarize customer issues.

## Severity rubric

| Severity | Meaning | Response target |
|---|---|---|
| S1 | Outage or data exposure; many users blocked; no workaround | 1 hour, all hands |
| S2 | Major feature broken or a compliance gap; workaround is painful | 1 business day |
| S3 | Degraded behavior with a reasonable workaround | Next sprint |
| S4 | Cosmetic issue, question, or feature request | Backlog |

## Triage steps

1. Look up the issue (`lookup_issue`) and the customer (`lookup_customer`).
2. Check the severity against the rubric. If it looks wrong, say what it should be and why.
3. Note business context from the customer record: plan, renewal date, notes.
4. Name the owning component and the next concrete action.
5. Flag renewal risk when an S1/S2 is open within 90 days of the customer's renewal date.

## Output format

One block per issue:

```
ISS-#### · <title> · <severity> (<agree | suggest Sx>)
Customer: <name> (<customer id>), renewal <date>
Component: <component> · Status: <status>
Next action: <one sentence>
Risk: <none | renewal risk | compliance risk>
```

Finish with a one-line overall priority order, e.g. `Priority: ISS-1041 > ISS-1043 > ISS-1047`.
