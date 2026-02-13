"""Tests for agent/agent_config.py — configuration constants."""

import importlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "agent"))


def test_default_mcp_server_url(monkeypatch):
    monkeypatch.delenv("MCP_SERVER_URL", raising=False)
    import agent.agent_config as cfg
    importlib.reload(cfg)
    assert cfg.MCP_SERVER_URL == "http://localhost:8000/mcp"


def test_custom_mcp_server_url(monkeypatch):
    monkeypatch.setenv("MCP_SERVER_URL", "http://custom:9000/mcp")
    import agent.agent_config as cfg
    importlib.reload(cfg)
    assert cfg.MCP_SERVER_URL == "http://custom:9000/mcp"


def test_default_agent_model(monkeypatch):
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    import agent.agent_config as cfg
    importlib.reload(cfg)
    assert cfg.AGENT_MODEL == "gpt-4o-mini"


def test_agent_instructions_not_empty():
    from agent.agent_config import AGENT_INSTRUCTIONS
    assert isinstance(AGENT_INSTRUCTIONS, str)
    assert len(AGENT_INSTRUCTIONS) > 100


def test_agent_instructions_contains_key_rules():
    from agent.agent_config import AGENT_INSTRUCTIONS
    assert "knowledge_search" in AGENT_INSTRUCTIONS
    assert "<<IMG:" in AGENT_INSTRUCTIONS
    assert "memory_add" in AGENT_INSTRUCTIONS
    assert "memory_search" in AGENT_INSTRUCTIONS
