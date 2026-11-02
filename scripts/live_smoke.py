"""Live smoke test: run every talk scenario against the real model and check what the
audience is supposed to see. Costs real tokens. Usage:

    .venv/Scripts/python scripts/live_smoke.py            # all stages
    .venv/Scripts/python scripts/live_smoke.py 3 4        # only these stages
"""
from __future__ import annotations

import asyncio
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.approvals import AutoApprove  # noqa: E402
from harness.stages import build_agent, scenarios  # noqa: E402

PREVIEW = 90


def short(s: str, n: int = PREVIEW) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


async def run_one(stage: int, sc, session_id: str | None = None) -> dict:
    agent = build_agent(stage, sc.role, session_id=session_id, approvals=AutoApprove())
    kinds: Counter[str] = Counter()
    denies, approvals, tools, text = [], [], [], []
    t0 = time.time()
    async for ev in agent.run(sc.prompt):
        kinds[ev.kind] += 1
        tag = f"[{ev.subagent}] " if ev.subagent else ""
        if ev.kind == "tool_call":
            tools.append(ev.data.get("name"))
            print(f"    {tag}tool_call   {ev.data.get('name')} {short(ev.data.get('input') or ev.data.get('arguments', ''), 70)}")
        elif ev.kind == "decision" and ev.data.get("action") != "allow":
            denies.append(ev.data)
            print(f"    {tag}decision    {ev.data.get('action')} {short(ev.data.get('reason', ''), 90)}")
        elif ev.kind == "approval_request":
            approvals.append(ev.data)
            print(f"    {tag}approval    {ev.data.get('tool')}")
        elif ev.kind == "tool_result":
            print(f"    {tag}tool_result {ev.data.get('name')} ok={ev.data.get('ok')} {short(ev.data.get('preview', ''), 70)}")
        elif ev.kind in ("subagent_start", "subagent_end", "compaction", "checkpoint", "todo_update", "error"):
            print(f"    {tag}{ev.kind:<11} {short(ev.data, 90)}")
        elif ev.kind == "text_done":
            text.append(ev.data.get("text", ""))
        elif ev.kind == "run_end":
            d = ev.data
            print(f"    run_end     calls={d.get('model_calls')} tools={d.get('tool_calls')} "
                  f"tokens={d.get('prompt_tokens')}/{d.get('completion_tokens')} error={d.get('error')} "
                  f"{time.time() - t0:.1f}s")
    final = " ".join(text)
    print(f"    reply       {short(final, 160)}")
    return {"kinds": kinds, "denies": denies, "approvals": approvals, "tools": tools,
            "text": final, "session_id": agent.session_id}


def expect(cond: bool, what: str, results: list[str]) -> None:
    results.append(("PASS  " if cond else "FAIL  ") + what)


async def main() -> int:
    stages = [int(a) for a in sys.argv[1:]] or [0, 1, 2, 3, 4]
    results: list[str] = []
    saved_session = None
    for stage in stages:
        for sc in scenarios(stage):
            print(f"\n== stage {stage} · {sc.title} · role={sc.role}\n   prompt: {short(sc.prompt, 110)}")
            resume = saved_session if (stage == 4 and sc.title.startswith("Come back")) else None
            r = await run_one(stage, sc, session_id=resume)
            k, name = r["kinds"], f"s{stage} {sc.title}"
            expect(k["error"] == 0, f"{name}: no error events", results)
            if stage == 0:
                expect(k["tool_call"] == 0, f"{name}: no tools at stage 0", results)
            if stage == 1:
                expect("load_skill" in r["tools"], f"{name}: load_skill was called", results)
            if stage == 2 and sc.title.startswith("Look"):
                expect("lookup_customer" in r["tools"], f"{name}: lookup_customer called", results)
                expect(k["subagent_start"] >= 1, f"{name}: subagent ran", results)
            if stage == 2 and sc.title.startswith("Runaway"):
                expect(any("limit" in str(d.get("reason", "")).lower() for d in r["denies"]), f"{name}: CallLimit stopped it", results)
            if stage == 3 and sc.title == "Wrong role":
                expect(any("role" in str(d.get("reason", "")).lower() for d in r["denies"]), f"{name}: RoleGate denied", results)
            if stage == 3 and sc.title == "Right role":
                expect("get_revenue" in r["tools"] and not r["denies"], f"{name}: get_revenue allowed", results)
            if stage == 3 and sc.title.startswith("Needs"):
                expect(len(r["approvals"]) >= 1, f"{name}: approval requested", results)
            if stage == 4 and sc.title.startswith("Save"):
                expect("write_workspace_file" in r["tools"], f"{name}: write_workspace_file called", results)
                saved_session = r["session_id"]
            if stage == 4 and resume:
                expect(bool(r["text"]), f"{name}: resumed session answered", results)
    print("\n" + "\n".join(results))
    return 1 if any(x.startswith("FAIL") for x in results) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
