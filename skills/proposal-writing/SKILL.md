---
name: proposal-writing
description: Company-wide guide for drafting customer proposals — required sections, tone, and what never to promise.
---
# Proposal writing (company-wide)

Use this whenever you draft a proposal, quote or upgrade offer for a customer.

## Before you write

1. If a customer lookup tool is available, use it and cite the customer id: plan, seats,
   renewal date, contact and notes. If it is not, work from what the user told you and say
   which facts you could not verify; do not stop to complain about missing tools.
2. Check open issues for the customer if you have access; do not hide a known S1/S2.

## Required sections (in this order)

1. **Summary** — two sentences: what we propose and why it fits them.
2. **Their goals** — bullets taken from the record or the request. No invented goals.
3. **Proposed plan** — plan name, seat count, list price per seat, annual total
   (seats x list price). Show the arithmetic.
4. **What is included** — only features listed for that plan in AGENTS.md.
5. **Open items** — anything that needs finance approval, a security review, or an
   engineering fix. Name the issue id if one exists.
6. **Next steps** — who does what next. The contact on record is the recipient.

## Tone

Plain and specific. Short paragraphs. No superlatives, no exclamation marks.

## Never promise

- Discounts, free months, or multi-year pricing without finance approval.
- Roadmap dates, custom features, or SLAs beyond the plan.
- Fixes for open issues by a date.

## Output format

Markdown with the six section headings above, under a title
`# Proposal: <Customer> — <Plan>`. End with a line `Prepared by Kestrel Desk for review.`
