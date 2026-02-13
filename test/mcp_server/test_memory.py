"""Tests for mcp-server/tools/memory.py — 4 memory CRUD tools."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MCP_SERVER_DIR = PROJECT_ROOT / "mcp-server"
for p in [str(PROJECT_ROOT), str(MCP_SERVER_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestMemoryRegistration:

    def test_all_four_tools_registered(self, memory_tools):
        expected = {"memory_add", "memory_search", "memory_get_all", "memory_delete"}
        assert set(memory_tools.keys()) == expected


# ---------------------------------------------------------------------------
# memory_add
# ---------------------------------------------------------------------------

class TestMemoryAdd:

    def test_add_with_valid_json_messages(self, memory_tools, mock_mem0):
        mock_mem0.add.return_value = {"results": [{"id": "mem_001"}]}

        messages_json = json.dumps([
            {"role": "user", "content": "My name is John"},
        ])
        result = memory_tools["memory_add"](
            messages=messages_json, user_id="user_123"
        )

        assert result["success"] is True
        assert result["result"] == {"results": [{"id": "mem_001"}]}
        mock_mem0.add.assert_called_once()
        call_args = mock_mem0.add.call_args
        assert call_args[0][0] == [{"role": "user", "content": "My name is John"}]
        assert call_args[1]["user_id"] == "user_123"

    def test_add_with_invalid_json_falls_back_to_plain_text(self, memory_tools, mock_mem0):
        mock_mem0.add.return_value = {"results": []}

        result = memory_tools["memory_add"](
            messages="not valid json", user_id="user_456"
        )

        assert result["success"] is True
        call_args = mock_mem0.add.call_args
        assert call_args[0][0] == [{"role": "user", "content": "not valid json"}]

    def test_add_with_multiple_messages(self, memory_tools, mock_mem0):
        mock_mem0.add.return_value = {"results": []}

        messages_json = json.dumps([
            {"role": "user", "content": "I like iPhone"},
            {"role": "assistant", "content": "Noted!"},
            {"role": "user", "content": "My budget is 30000 THB"},
        ])
        memory_tools["memory_add"](messages=messages_json, user_id="u1")

        parsed = mock_mem0.add.call_args[0][0]
        assert len(parsed) == 3
        assert parsed[2]["content"] == "My budget is 30000 THB"

    def test_add_exception_returns_error(self, memory_tools, mock_mem0):
        mock_mem0.add.side_effect = RuntimeError("mem0 failed")

        result = memory_tools["memory_add"](
            messages='[{"role":"user","content":"test"}]', user_id="u1"
        )

        assert result["success"] is False
        assert "mem0 failed" in result["error"]

    def test_add_preserves_user_id(self, memory_tools, mock_mem0):
        mock_mem0.add.return_value = {}

        memory_tools["memory_add"](
            messages='[{"role":"user","content":"hi"}]', user_id="fb_12345"
        )

        assert mock_mem0.add.call_args[1]["user_id"] == "fb_12345"


# ---------------------------------------------------------------------------
# memory_search
# ---------------------------------------------------------------------------

class TestMemorySearch:

    def test_search_returns_memories(self, memory_tools, mock_mem0):
        mock_mem0.search.return_value = [
            {"id": "m1", "memory": "User likes iPhone", "score": 0.9},
        ]

        result = memory_tools["memory_search"](
            query="favorite brand", user_id="user_123"
        )

        assert result["success"] is True
        assert len(result["memories"]) == 1
        assert result["memories"][0]["memory"] == "User likes iPhone"

    def test_search_with_custom_limit(self, memory_tools, mock_mem0):
        mock_mem0.search.return_value = []

        memory_tools["memory_search"](
            query="budget", user_id="u1", limit=10
        )

        call_kwargs = mock_mem0.search.call_args
        assert call_kwargs[1]["limit"] == 10

    def test_search_default_limit_is_5(self, memory_tools, mock_mem0):
        mock_mem0.search.return_value = []

        memory_tools["memory_search"](query="test", user_id="u1")

        call_kwargs = mock_mem0.search.call_args
        assert call_kwargs[1]["limit"] == 5

    def test_search_passes_correct_query(self, memory_tools, mock_mem0):
        mock_mem0.search.return_value = []

        memory_tools["memory_search"](query="favorite color", user_id="u1")

        assert mock_mem0.search.call_args[0][0] == "favorite color"

    def test_search_exception_returns_error(self, memory_tools, mock_mem0):
        mock_mem0.search.side_effect = ConnectionError("DB down")

        result = memory_tools["memory_search"](
            query="test", user_id="u1"
        )

        assert result["success"] is False
        assert "DB down" in result["error"]

    def test_search_empty_results(self, memory_tools, mock_mem0):
        mock_mem0.search.return_value = []

        result = memory_tools["memory_search"](query="xyz", user_id="u1")

        assert result["success"] is True
        assert result["memories"] == []


# ---------------------------------------------------------------------------
# memory_get_all
# ---------------------------------------------------------------------------

class TestMemoryGetAll:

    def test_get_all_returns_memories(self, memory_tools, mock_mem0):
        mock_mem0.get_all.return_value = [
            {"id": "m1", "memory": "Name is John"},
            {"id": "m2", "memory": "Budget is 5000"},
        ]

        result = memory_tools["memory_get_all"](user_id="user_789")

        assert result["success"] is True
        assert len(result["memories"]) == 2
        mock_mem0.get_all.assert_called_once_with(user_id="user_789")

    def test_get_all_empty(self, memory_tools, mock_mem0):
        mock_mem0.get_all.return_value = []

        result = memory_tools["memory_get_all"](user_id="new_user")

        assert result["success"] is True
        assert result["memories"] == []

    def test_get_all_exception_returns_error(self, memory_tools, mock_mem0):
        mock_mem0.get_all.side_effect = Exception("Storage error")

        result = memory_tools["memory_get_all"](user_id="u1")

        assert result["success"] is False
        assert "Storage error" in result["error"]


# ---------------------------------------------------------------------------
# memory_delete
# ---------------------------------------------------------------------------

class TestMemoryDelete:

    def test_delete_succeeds(self, memory_tools, mock_mem0):
        mock_mem0.delete.return_value = None

        result = memory_tools["memory_delete"](memory_id="mem_001")

        assert result["success"] is True
        assert "mem_001" in result["message"]
        mock_mem0.delete.assert_called_once_with(memory_id="mem_001")

    def test_delete_different_id(self, memory_tools, mock_mem0):
        mock_mem0.delete.return_value = None

        result = memory_tools["memory_delete"](memory_id="abc-def-ghi")

        assert result["success"] is True
        assert "abc-def-ghi" in result["message"]

    def test_delete_exception_returns_error(self, memory_tools, mock_mem0):
        mock_mem0.delete.side_effect = KeyError("Not found")

        result = memory_tools["memory_delete"](memory_id="nonexistent")

        assert result["success"] is False
        assert "Not found" in result["error"]

    def test_delete_passes_memory_id_as_kwarg(self, memory_tools, mock_mem0):
        mock_mem0.delete.return_value = None

        memory_tools["memory_delete"](memory_id="xyz")

        assert mock_mem0.delete.call_args[1]["memory_id"] == "xyz"
