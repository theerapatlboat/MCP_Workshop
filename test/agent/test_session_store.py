"""Tests for agent/session_store.py — SQLite session management."""

import json
import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "agent"))

from agent.session_store import SessionStore


@pytest.fixture
def store(tmp_path):
    """Create SessionStore with small limits for easy testing."""
    return SessionStore(db_path=tmp_path / "test.db", max_messages=10, ttl_hours=1)


@pytest.fixture
def short_ttl_store(tmp_path):
    """SessionStore with very short TTL for expiry testing."""
    return SessionStore(
        db_path=tmp_path / "ttl_test.db", max_messages=50, ttl_hours=0.0001
    )


# --- _init_db ---

def test_init_db_creates_table(tmp_path):
    db_path = tmp_path / "new.db"
    SessionStore(db_path=db_path)
    with sqlite3.connect(str(db_path)) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
        ).fetchall()
    assert len(tables) == 1


def test_init_db_idempotent(tmp_path):
    db_path = tmp_path / "idem.db"
    SessionStore(db_path=db_path)
    SessionStore(db_path=db_path)  # Should not raise


# --- get / save ---

def test_get_empty_session(store):
    assert store.get("nonexistent") == []


def test_save_and_get(store):
    history = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
    store.save("s1", history)
    result = store.get("s1")
    assert result == history


def test_save_overwrites_existing(store):
    store.save("s1", [{"role": "user", "content": "first"}])
    store.save("s1", [{"role": "user", "content": "second"}])
    result = store.get("s1")
    assert len(result) == 1
    assert result[0]["content"] == "second"


def test_save_truncates_to_max_messages(tmp_path):
    store = SessionStore(db_path=tmp_path / "trunc.db", max_messages=5)
    history = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
    store.save("s1", history)
    result = store.get("s1")
    assert len(result) == 5
    assert result[0]["content"] == "msg5"  # kept last 5


def test_save_at_max_boundary(tmp_path):
    store = SessionStore(db_path=tmp_path / "bound.db", max_messages=5)
    history = [{"role": "user", "content": f"msg{i}"} for i in range(5)]
    store.save("s1", history)
    result = store.get("s1")
    assert len(result) == 5


def test_save_empty_history(store):
    store.save("s1", [])
    assert store.get("s1") == []


def test_save_unicode_content(store):
    history = [{"role": "user", "content": "สวัสดีครับ ทดสอบภาษาไทย"}]
    store.save("s1", history)
    result = store.get("s1")
    assert result[0]["content"] == "สวัสดีครับ ทดสอบภาษาไทย"


# --- delete ---

def test_delete_session(store):
    store.save("s1", [{"role": "user", "content": "hi"}])
    store.delete("s1")
    assert store.get("s1") == []


def test_delete_nonexistent_session(store):
    store.delete("nonexistent")  # Should not raise


# --- TTL ---

def test_get_expired_session(tmp_path):
    store = SessionStore(db_path=tmp_path / "exp.db", max_messages=50, ttl_hours=1)
    # Save with past timestamp by manipulating DB directly
    now = time.time()
    old_time = now - 7200  # 2 hours ago (TTL is 1 hour)
    with sqlite3.connect(str(tmp_path / "exp.db")) as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, history, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("s1", '[{"role":"user","content":"old"}]', old_time, old_time),
        )
        conn.commit()
    assert store.get("s1") == []


def test_get_non_expired_session(store):
    store.save("s1", [{"role": "user", "content": "fresh"}])
    result = store.get("s1")
    assert len(result) == 1


# --- count ---

def test_count_existing_session(store):
    store.save("s1", [{"role": "user", "content": "a"}, {"role": "user", "content": "b"}])
    assert store.count("s1") == 2


def test_count_nonexistent_session(store):
    assert store.count("nonexistent") == 0


def test_count_empty_session(store):
    store.save("s1", [])
    assert store.count("s1") == 0


# --- list_all ---

def test_list_all_no_sessions(store):
    assert store.list_all() == []


def test_list_all_with_sessions(store):
    store.save("s1", [{"role": "user", "content": "a"}])
    store.save("s2", [{"role": "user", "content": "b"}, {"role": "user", "content": "c"}])
    result = store.list_all()
    assert len(result) == 2
    ids = [r["session_id"] for r in result]
    assert "s1" in ids
    assert "s2" in ids


def test_list_all_returns_metadata(store):
    store.save("s1", [{"role": "user", "content": "a"}])
    result = store.list_all()
    entry = result[0]
    assert "session_id" in entry
    assert "message_count" in entry
    assert "created_at" in entry
    assert "updated_at" in entry
    assert entry["message_count"] == 1


def test_list_all_excludes_expired(tmp_path):
    store = SessionStore(db_path=tmp_path / "listexp.db", max_messages=50, ttl_hours=1)
    old_time = time.time() - 7200
    with sqlite3.connect(str(tmp_path / "listexp.db")) as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, history, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("old_session", "[]", old_time, old_time),
        )
        conn.commit()
    store.save("fresh_session", [{"role": "user", "content": "hi"}])
    result = store.list_all()
    ids = [r["session_id"] for r in result]
    assert "old_session" not in ids
    assert "fresh_session" in ids


def test_list_all_handles_corrupt_json(tmp_path):
    store = SessionStore(db_path=tmp_path / "corrupt.db", max_messages=50, ttl_hours=1)
    now = time.time()
    with sqlite3.connect(str(tmp_path / "corrupt.db")) as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, history, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("corrupt", "not-valid-json", now, now),
        )
        conn.commit()
    result = store.list_all()
    assert len(result) == 1
    assert result[0]["message_count"] == 0


# --- cleanup ---

def test_cleanup_expired_removes_old_sessions(tmp_path):
    store = SessionStore(db_path=tmp_path / "clean.db", max_messages=50, ttl_hours=1)
    old_time = time.time() - 7200
    with sqlite3.connect(str(tmp_path / "clean.db")) as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, history, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("old", "[]", old_time, old_time),
        )
        conn.commit()
    store._cleanup_expired()
    with sqlite3.connect(str(tmp_path / "clean.db")) as conn:
        rows = conn.execute("SELECT session_id FROM sessions").fetchall()
    assert len(rows) == 0
