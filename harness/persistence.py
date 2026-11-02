"""Checkpoints: every message is written to SQLite as it happens, so a session survives a restart.

Stages 0-3 keep history in memory only. Stage 4 passes a SessionStore and can resume.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY, stage INTEGER, role TEXT, title TEXT DEFAULT '',
    created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS messages (
    session_id TEXT, seq INTEGER, json TEXT, PRIMARY KEY (session_id, seq));
"""


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


class SessionStore:
    """One SQLite file (WAL mode), one row per message."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path or config.DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def create(self, session_id: str, stage: int, role: str, title: str = "") -> None:
        now = time.time()
        with closing(self._connect()) as db, db:
            db.execute("INSERT OR IGNORE INTO sessions VALUES (?, ?, ?, ?, ?, ?)",
                       (session_id, stage, role, title, now, now))

    def exists(self, session_id: str) -> bool:
        with closing(self._connect()) as db:
            return db.execute("SELECT 1 FROM sessions WHERE session_id=?", (session_id,)).fetchone() is not None

    def get_session(self, session_id: str) -> dict | None:
        """Metadata for one session (same shape as a list_sessions row), or None."""
        return next((s for s in self.list_sessions() if s["session_id"] == session_id), None)

    def append(self, session_id: str, message: dict) -> None:
        now = time.time()
        with closing(self._connect()) as db, db:
            db.execute("INSERT OR IGNORE INTO sessions VALUES (?, -1, '', '', ?, ?)", (session_id, now, now))
            seq = db.execute("SELECT COALESCE(MAX(seq), -1) + 1 FROM messages WHERE session_id=?",
                             (session_id,)).fetchone()[0]
            db.execute("INSERT INTO messages VALUES (?, ?, ?)", (session_id, seq, json.dumps(message)))
            db.execute("UPDATE sessions SET updated_at=? WHERE session_id=?", (now, session_id))
            if message.get("role") == "user" and isinstance(message.get("content"), str):
                db.execute("UPDATE sessions SET title=? WHERE session_id=? AND title=''",
                           (message["content"].strip().replace("\n", " ")[:60], session_id))

    def replace_all(self, session_id: str, messages: list[dict]) -> None:
        """Rewrite a session's history in one transaction (used after compaction)."""
        with closing(self._connect()) as db, db:
            db.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
            db.executemany("INSERT INTO messages VALUES (?, ?, ?)",
                           [(session_id, i, json.dumps(m)) for i, m in enumerate(messages)])
            db.execute("UPDATE sessions SET updated_at=? WHERE session_id=?", (time.time(), session_id))

    def load(self, session_id: str) -> list[dict]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT json FROM messages WHERE session_id=? ORDER BY seq", (session_id,))
            return [json.loads(r["json"]) for r in rows]

    def list_sessions(self) -> list[dict]:
        """Newest first."""
        with closing(self._connect()) as db:
            rows = db.execute("""
                SELECT s.*, (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.session_id) AS n
                FROM sessions s ORDER BY s.updated_at DESC, s.rowid DESC""").fetchall()
        return [{"session_id": r["session_id"], "stage": r["stage"], "role": r["role"], "title": r["title"],
                 "created_at": _iso(r["created_at"]), "updated_at": _iso(r["updated_at"]),
                 "message_count": r["n"]} for r in rows]

    def set_title(self, session_id: str, title: str) -> None:
        with closing(self._connect()) as db, db:
            db.execute("UPDATE sessions SET title=? WHERE session_id=?", (title[:60], session_id))

    def delete(self, session_id: str) -> None:
        with closing(self._connect()) as db, db:
            db.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
            db.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
