# Prompt for the coding agent on the org laptop

Copy everything below the line into the agent's first message, after cloning the repository
(or let the agent clone it: the repo is https://github.com/shubham-t/kestrel-desk).

---

I need you to set up and rehearse a live demo on this laptop. The project is Kestrel Desk, a
teaching harness for my talk on agent harness engineering. Everything you need to know is in
`docs/HANDOFF.md`; read it completely before doing anything, then `README.md`.

Constraints on this machine: Anthropic models are not available. Use our internal
OpenAI-compatible endpoint: base URL `<FILL IN>`, model id `<FILL IN>`, key from `<FILL IN:
env var / secret store>`. If a cheaper model is available for subagents, use `<FILL IN>`,
otherwise the same id. Python 3.12 is at `<FILL IN or "on PATH">`. `<FILL IN: proxy / CA
bundle details, or "no proxy">`.

Do, in this order, and stop to tell me if any step fails:
1. Create the venv, install `requirements.txt`, copy `.env.example` to `.env` and fill it in
   as HANDOFF.md section 3 says. Clear `LLM_EXTRA_BODY`. Never print the key or commit `.env`.
2. Run `scripts/verify_offline.py`; every line must say PASS.
3. Run `python -m harness.cli --stage 0` and say hello, then `--stage 3 --role finance` and
   ask "What was our revenue in FY2026?". Show me both replies verbatim. If tool calling
   does not work, diagnose it in `harness/llm.py` only, per HANDOFF.md section 4, and tell me
   what the endpoint sends before changing anything.
4. Run `scripts/live_smoke.py` and show me the PASS/FAIL lines. Investigate any FAIL; do not
   change scenario titles, roles or what each scenario demonstrates.
5. Start the web app, confirm the top bar reads `LIVE · <our model>`, and open stage 3 in the
   browser to run "Wrong role" and "Send it" (approve it). Tell me what you saw.
6. Tell me the exact commands to start the demo on talk day and the one-line mock fallback.
7. Then the notebook version (HANDOFF.md section 5, "Alternative", and `notebooks/README.md`):
   install `requirements-notebook.txt` into the same venv, run `pytest -q tests/test_notebook.py
   tests/test_chatwin.py` (offline, fake model), then execute `notebooks/kestrel_desk.ipynb`
   top to bottom against our endpoint (`jupyter nbconvert --to notebook --execute --inplace`
   or open it in Jupyter Lab and Run All) and show me any cell that errors. Start the chat
   window with `python -m chatwin --stage 3`, open http://127.0.0.1:8777, run "Wrong role" as
   Engineering, and tell me what you saw. Give me the commands for both formats.

Do not change the UI design, the scenario script, the `Agent(...)` calls in
`harness/stages.py`, or the `# [stage:N]` marker comments. Report every deviation from
HANDOFF.md you had to make and why.
