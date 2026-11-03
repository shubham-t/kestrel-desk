# Kestrel Desk chat window: prompt cheat sheet

Every scenario from `harness/talk.py`, in talk order (the Acme Robotics renewal story). After each stage's `serve(...)` cell,
refresh the chat window (http://127.0.0.1:8777), pick the role, paste the prompt.

## Stage 0 · Chatbot (`model`)

1. **Who's Acme?** (Sales)
   `Who is Acme Robotics and when is their renewal due?`
   Watch: it can't know. Nothing is around the model.
2. **Price the renewal** (Sales)
   `Draft a renewal proposal for Acme Robotics: 40 seats on our Enterprise plan, with pricing.`
   Watch: it invents a price, or asks for one.

## Stage 1 · Context (`instructions`)

3. **Price the renewal, again** (Sales)
   `Draft a renewal proposal for Acme Robotics: 40 seats on our Enterprise plan, with pricing.`
   Watch: the plan-table price ($2,400 per seat per year), our tone and sections. We still had to say who Acme is.
4. **Can I discount?** (Sales)
   `Can I offer Acme 15% off to close this quarter?`
   Watch: "No: above 10% needs written approval from finance", straight from AGENTS.md.

## Stage 2 · Actions (`tools`, `middleware`, `skills`, `subagents`)

5. **Prepare the renewal** (Sales)
   `Prepare Acme Robotics' renewal proposal: check their record and open issues, then have the proposal-reviewer check it before you show it to me.`
   Watch: `load_skill`, `lookup_customer`, `lookup_issue`, then `run_subagent` with the reviewer's own calls indented underneath.
6. **Account health, every customer** (Engineering)
   `Give me an account health report for every customer: their record plus their open issues.`
   Watch: CallLimit denies the 11th tool call (red line); the model reports partial results.

## Stage 3 · Boundaries (`permissions`, `approve`, `audit`)

7. **Wrong role** (Engineering)
   `What was our revenue in FY2026?`
   Watch: `get_revenue` is denied in red, in code, before it runs.
8. **Right role** (Finance)
   `What was our revenue in FY2026?`
   Watch: same question, allowed, answered with record ids.
9. **Send it** (Sales)
   `Draft a short renewal proposal for Acme Robotics (40 seats, Enterprise, SSO and audit logs) and send it to procurement@acme-robotics.example with the subject "Kestrel renewal proposal".`
   Watch: the approval box appears and the run waits. Click **Approve**: the proposal lands in `.harness_state/outbox/`.
   Variant: send to `ceo@acme-robotics.example` and the tool rejects the address as not on record.

## Stage 4 · Persistence (`checkpointer`, `workspace`, `compaction`)

10. **Save the draft** (Sales)
    `Draft a short renewal proposal for Acme Robotics (40 seats, Enterprise, SSO and audit logs), save it as workspace/acme-renewal.md, and add a line to company/AGENTS.md saying the Acme draft is done.`
    Watch: `write_workspace_file` saves the draft; the AGENTS.md write is refused (outside workspace/).
11. **Pick up yesterday's work** (Sales)
    Click **New chat**, then click the "Save the draft" session under **Past sessions** (it resumes from SQLite), then:
    `Where did we leave off with Acme, and what did we save?`
12. **Long day**
    No prompt: click **Compact now** under the sessions list. A "Compacted: N → M messages" line appears with the summary.
