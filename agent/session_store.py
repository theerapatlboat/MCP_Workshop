"""SQLite-backed session store for short-term conversation memory.

Provides persistent conversation history with:
- Max message limit (truncates old messages)
- Session TTL (auto-expires inactive sessions)
- Lazy cleanup (no background thread needed)

Config via environment variables:
    MAX_HISTORY_MESSAGES  — max messages per session (default: 50)
    SESSION_TTL_HOURS     — session expiry in hours (default: 24)
"""

import json
import os
import sqlite3
import time
from pathlib import Path

MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "50"))
SESSION_TTL_HOURS = float(os.getenv("SESSION_TTL_HOURS", "24"))

DB_PATH = Path(__file__).parent / "sessions.db"


class SessionStore:
    """Persistent session store with max history limit and TTL."""

    def __init__(
        self,
        db_path: Path = DB_PATH,
        max_messages: int = MAX_HISTORY_MESSAGES,
        ttl_hours: float = SESSION_TTL_HOURS,
    ):
        self.db_path = str(db_path)
        self.max_messages = max_messages
        self.ttl_seconds = ttl_hours * 3600
        self._init_db()

    def _init_db(self) -> None:
        """Create sessions table if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    history    TEXT NOT NULL DEFAULT '[]',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.commit()

    def get(self, session_id: str) -> list:
        """Get conversation history. Returns [] if not found or expired."""
        self._cleanup_expired()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT history, updated_at FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return []
        if time.time() - row[1] > self.ttl_seconds:
            self.delete(session_id)
            return []
        return json.loads(row[0])

    def save(self, session_id: str, history: list) -> None:
        """Save history, truncating to max_messages (keep most recent)."""
        if len(history) > self.max_messages:
            history = history[-self.max_messages :]
        now = time.time()
        history_json = json.dumps(history, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, history, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    history = excluded.history,
                    updated_at = excluded.updated_at
                """,
                (session_id, history_json, now, now),
            )
            conn.commit()

    def delete(self, session_id: str) -> None:
        """Delete a session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM sessions WHERE session_id = ?", (session_id,)
            )
            conn.commit()

    def _cleanup_expired(self) -> None:
        """Delete sessions older than TTL."""
        cutoff = time.time() - self.ttl_seconds
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM sessions WHERE updated_at < ?", (cutoff,))
            conn.commit()

    def count(self, session_id: str) -> int:
        """Return message count for a session."""
        history = self.get(session_id)
        return len(history)

    def list_all(self) -> list[dict]:
        """Return all non-expired sessions with metadata."""
        self._cleanup_expired()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT session_id, history, created_at, updated_at "
                "FROM sessions ORDER BY updated_at DESC"
            ).fetchall()
        result = []
        for session_id, history_json, created_at, updated_at in rows:
            try:
                msg_count = len(json.loads(history_json))
            except (json.JSONDecodeError, TypeError):
                msg_count = 0
            result.append({
                "session_id": session_id,
                "message_count": msg_count,
                "created_at": created_at,
                "updated_at": updated_at,
            })
        return result
