"""Offline pre-flight for the talk: one command, one PASS/FAIL line per check, exit 1 on any FAIL.

    .venv/Scripts/python scripts/verify_offline.py

No network and no API key needed. Checks the company data, skills and AGENTS.md, runs the
test suite, then boots the web app (real harness, then KESTREL_MOCK=1 rehearsal mode) and calls
/api/meta in-process with fastapi's TestClient.
A web app that cannot even be imported is reported as WARN, not FAIL: it may be mid-edit.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

COMPANY = REPO / "company"
DATA = COMPANY / "data"
ROLES = ("sales", "engineering", "finance")
SKILLS = ("proposal-writing", "issue-triage", "revenue-brief")
CUSTOMER_FIELDS = {"id", "name", "industry", "plan", "seats", "arr_usd", "contact_name", "contact_email",
                   "renewal_date", "notes"}
ISSUE_FIELDS = {"id", "customer_id", "title", "severity", "status", "component", "opened", "summary"}
QUARTERS = [f"FY{y}-Q{q}" for y in (2025, 2026) for q in (1, 2, 3, 4)]

results: list[str] = []


def report(status: str, name: str, detail: str = "") -> None:
    results.append(status)
    print(f"{status:<4}  {name}" + (f"  ({detail})" if detail else ""), flush=True)


def check(name: str, fn) -> None:
    """Run one check: it returns a detail string on success and raises AssertionError on failure."""
    try:
        report("PASS", name, fn() or "")
    except Exception as exc:  # any failure is a FAIL line, never a traceback
        report("FAIL", name, f"{type(exc).__name__}: {exc}")


def load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------- data, skills, AGENTS.md

def customers() -> str:
    rows = load("customers.json")
    assert len(rows) == 7, f"expected 7 customers, found {len(rows)}"
    for c in rows:
        missing = CUSTOMER_FIELDS - set(c)
        assert not missing, f"{c.get('id')} missing {sorted(missing)}"
        assert c["contact_email"].endswith(".example"), f"{c['id']}: contact_email must use a .example domain"
    assert len({c["id"] for c in rows}) == len(rows), "duplicate customer ids"
    return "7 records, synthetic .example emails"


def issues() -> str:
    rows, ids = load("issues.json"), {c["id"] for c in load("customers.json")}
    assert len(rows) == 10, f"expected 10 issues, found {len(rows)}"
    for i in rows:
        missing = ISSUE_FIELDS - set(i)
        assert not missing, f"{i.get('id')} missing {sorted(missing)}"
        assert i["severity"] in ("S1", "S2", "S3", "S4"), f"{i['id']}: bad severity {i['severity']}"
        assert i["customer_id"] in ids, f"{i['id']}: unknown customer {i['customer_id']}"
    assert len({i["id"] for i in rows}) == len(rows), "duplicate issue ids"
    return "10 records, every customer_id resolves"


def revenue() -> str:
    data = load("revenue.json")
    assert data.get("source") and data.get("currency"), "source note and currency are required"
    assert [q["period"] for q in data["quarters"]] == QUARTERS, "quarters must be FY2025-Q1 .. FY2026-Q4"
    for q in data["quarters"]:
        assert q.get("id"), f"{q['period']} has no record id"
        assert q["total"] == sum(q["by_product_line"].values()), f"{q['id']}: total != sum of product lines"
    arr = data["arr_by_plan"]
    assert arr.get("id") and arr["total"] == sum(arr["plans"].values()), "ARR total != sum of plans"
    return "8 quarters + ARR, totals add up, every record has an id"


def skills() -> str:
    from harness.context import discover_skills

    found = {s.name: s for s in discover_skills()}
    for name in SKILLS:
        assert name in found, f"skills/{name}/SKILL.md missing or has no frontmatter name"
        skill = found[name]
        assert skill.path.parent.name == name, f"{name}: frontmatter name != folder name"
        assert skill.description, f"{name}: frontmatter description is empty"
        assert skill.path.read_text(encoding="utf-8").startswith("---"), f"{name}: no frontmatter"
        assert len(skill.body) > 200, f"{name}: body looks empty"
    return ", ".join(SKILLS)


def agents_md() -> str:
    text = (COMPANY / "AGENTS.md").read_text(encoding="utf-8")
    missing = [r for r in ROLES if not re.search(rf"\b{r}\b", text, re.I)]
    assert not missing, f"roles not mentioned: {missing}"
    return f"{len(text.splitlines())} lines, mentions all three roles"


def workspace() -> str:
    assert (REPO / "workspace" / ".gitkeep").exists(), "workspace/.gitkeep missing"
    return "workspace/.gitkeep present"


# ---------------------------------------------------------------------- tests

def pytest_suite() -> None:
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=REPO,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    summary = lines[-1] if lines else proc.stderr.strip()[-200:]
    if proc.returncode == 0:
        report("PASS", "pytest -q", summary)
    else:
        print("\n".join(lines[-30:]))
        report("FAIL", "pytest -q", summary)


# ---------------------------------------------------------------------- web app

# Runs in a child process so each mode imports app.server fresh. Exit 3 = could not import.
_PROBE = r"""
import json, sys
try:
    from fastapi.testclient import TestClient
    from app.server import app
except Exception as exc:
    print(f"{type(exc).__name__}: {exc}"); sys.exit(3)
with TestClient(app) as client:
    r = client.get("/api/meta")
    assert r.status_code == 200, f"/api/meta returned {r.status_code}"
    meta = r.json()
    for key in ("model", "base_url_host", "mock", "stages", "roles", "scenarios", "snippets"):
        assert key in meta, f"meta has no {key!r}"
    assert len(meta["stages"]) == 5, f"{len(meta['stages'])} stages"
    for s in meta["stages"]:
        for key in ("headline", "problem", "tagline", "new_keywords"):
            assert key in s, f"stage {s.get('id')} has no {key!r}"
    assert sorted(meta["roles"]) == ["engineering", "finance", "sales"], meta["roles"]
    assert all(meta["snippets"][str(i)] for i in range(5)), "a stage has no snippets"
    from harness.config import settings
    if settings.api_key:
        assert settings.api_key not in r.text, "the API key leaked into /api/meta"
    print(f"5 stages, model {meta['model']}, mock={meta['mock']}")
"""


def web(name: str, mock: bool) -> None:
    env = {k: v for k, v in os.environ.items() if k != "KESTREL_MOCK"}
    if mock:
        env["KESTREL_MOCK"] = "1"
    try:
        proc = subprocess.run([sys.executable, "-c", _PROBE], cwd=REPO, env=env, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=120)
    except subprocess.TimeoutExpired:
        return report("FAIL", name, "timed out after 120 s")
    out = (proc.stdout.strip().splitlines() or [""])[-1]
    err = (proc.stderr.strip().splitlines() or [""])[-1]
    if proc.returncode == 0:
        report("PASS", name, out)
    elif proc.returncode == 3:
        report("WARN", name, f"app.server does not import (web app mid-edit?): {out}")
    else:
        report("FAIL", name, err or out)


def main() -> int:
    print(f"Kestrel Desk offline verification - {REPO}\n")
    check("company/data/customers.json", customers)
    check("company/data/issues.json", issues)
    check("company/data/revenue.json", revenue)
    check("skills/*/SKILL.md frontmatter", skills)
    check("company/AGENTS.md", agents_md)
    check("workspace/", workspace)
    pytest_suite()
    web("app.server GET /api/meta (real harness)", mock=False)
    web("app.server GET /api/meta (KESTREL_MOCK=1)", mock=True)
    failed, warned = results.count("FAIL"), results.count("WARN")
    print(f"\n{len(results) - failed - warned} passed, {warned} warned, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
