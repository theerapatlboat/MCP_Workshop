"""Tests for agent/run_agents.py — CLI runner and ConsoleTraceProcessor."""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "agent"))

from agent.run_agents import ConsoleTraceProcessor


# ════════════════════════════════════════════════════════════
#  ConsoleTraceProcessor
# ════════════════════════════════════════════════════════════

@pytest.fixture
def processor():
    return ConsoleTraceProcessor()


@pytest.fixture
def mock_trace():
    t = MagicMock()
    t.name = "Test Trace"
    t.trace_id = "trace-abc-123"
    return t


def _make_span(data_cls_name, **attrs):
    """Create a mock span with the given span_data class."""
    from agents import (
        AgentSpanData, FunctionSpanData, GenerationSpanData,
        MCPListToolsSpanData, HandoffSpanData, GuardrailSpanData,
    )
    cls_map = {
        "AgentSpanData": AgentSpanData,
        "FunctionSpanData": FunctionSpanData,
        "GenerationSpanData": GenerationSpanData,
        "MCPListToolsSpanData": MCPListToolsSpanData,
        "HandoffSpanData": HandoffSpanData,
        "GuardrailSpanData": GuardrailSpanData,
    }

    span = MagicMock()
    span.span_id = f"span-{time.time()}"

    data = MagicMock(spec=cls_map.get(data_cls_name, MagicMock))
    # Make isinstance checks work
    data.__class__ = cls_map.get(data_cls_name, type(data))
    for k, v in attrs.items():
        setattr(data, k, v)
    span.span_data = data
    return span


def test_trace_start(processor, mock_trace, capsys):
    processor.on_trace_start(mock_trace)
    captured = capsys.readouterr()
    assert "TRACE START" in captured.err
    assert "Test Trace" in captured.err


def test_trace_end(processor, mock_trace, capsys):
    processor.on_trace_end(mock_trace)
    captured = capsys.readouterr()
    assert "TRACE END" in captured.err


def test_agent_span_start(processor, capsys):
    span = _make_span("AgentSpanData", name="TestAgent", tools=["search", "memory"])
    processor.on_span_start(span)
    captured = capsys.readouterr()
    assert "AGENT" in captured.err
    assert "TestAgent" in captured.err


def test_agent_span_end(processor, capsys):
    span = _make_span("AgentSpanData", name="TestAgent", tools=[])
    processor.on_span_start(span)  # record start time
    processor.on_span_end(span)
    captured = capsys.readouterr()
    assert "AGENT DONE" in captured.err


def test_function_span_start_with_input(processor, capsys):
    span = _make_span("FunctionSpanData", name="knowledge_search", input='{"query": "test"}')
    processor.on_span_start(span)
    captured = capsys.readouterr()
    assert "TOOL CALL" in captured.err
    assert "knowledge_search" in captured.err


def test_function_span_end_with_output(processor, capsys):
    span = _make_span("FunctionSpanData", name="search", input="", output="some result data")
    processor.on_span_start(span)
    processor.on_span_end(span)
    captured = capsys.readouterr()
    assert "TOOL DONE" in captured.err


def test_generation_span_start(processor, capsys):
    span = _make_span("GenerationSpanData", model="gpt-4o-mini")
    processor.on_span_start(span)
    captured = capsys.readouterr()
    assert "LLM GENERATION" in captured.err
    assert "gpt-4o-mini" in captured.err


def test_generation_span_end_with_usage(processor, capsys):
    span = _make_span("GenerationSpanData", model="gpt-4o-mini",
                       usage={"input_tokens": 100, "output_tokens": 50})
    processor.on_span_start(span)
    processor.on_span_end(span)
    captured = capsys.readouterr()
    assert "LLM DONE" in captured.err
    assert "100" in captured.err


def test_generation_span_end_no_usage(processor, capsys):
    span = _make_span("GenerationSpanData", model="gpt-4o-mini", usage=None)
    processor.on_span_start(span)
    processor.on_span_end(span)
    captured = capsys.readouterr()
    assert "LLM DONE" in captured.err


def test_mcp_list_tools_span(processor, capsys):
    span = _make_span("MCPListToolsSpanData", server="GoSaaS MCP", result=[MagicMock(), MagicMock()])
    processor.on_span_start(span)
    captured = capsys.readouterr()
    assert "MCP LIST TOOLS" in captured.err


def test_handoff_span(processor, capsys):
    span = _make_span("HandoffSpanData", from_agent="Agent A", to_agent="Agent B")
    processor.on_span_start(span)
    captured = capsys.readouterr()
    assert "HANDOFF" in captured.err


def test_guardrail_span_triggered(processor, capsys):
    span = _make_span("GuardrailSpanData", name="ContentGuard", triggered=True)
    processor.on_span_start(span)
    processor.on_span_end(span)
    captured = capsys.readouterr()
    assert "TRIGGERED" in captured.err


def test_guardrail_span_passed(processor, capsys):
    span = _make_span("GuardrailSpanData", name="ContentGuard", triggered=False)
    processor.on_span_start(span)
    processor.on_span_end(span)
    captured = capsys.readouterr()
    assert "passed" in captured.err


def test_unknown_span(processor, capsys):
    span = MagicMock()
    span.span_id = "unknown-1"
    span.span_data = MagicMock()
    type(span.span_data).__name__ = "CustomSpanData"
    processor.on_span_start(span)
    captured = capsys.readouterr()
    assert "CustomSpanData" in captured.err


def test_truncate_long_text():
    result = ConsoleTraceProcessor._truncate("a" * 200, 120)
    assert len(result) == 121  # 120 + "…"
    assert result.endswith("…")


def test_truncate_short_text():
    result = ConsoleTraceProcessor._truncate("short", 120)
    assert result == "short"


def test_truncate_newlines():
    result = ConsoleTraceProcessor._truncate("line1\nline2\nline3", 120)
    assert "\n" not in result
    assert "line1 line2 line3" == result


def test_shutdown_no_error(processor):
    processor.shutdown()  # Should not raise


def test_force_flush_no_error(processor):
    processor.force_flush()  # Should not raise
