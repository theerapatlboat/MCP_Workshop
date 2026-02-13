"""Tests for agent/tui/trace_processor.py — TUI trace event processor."""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "agent"))

from agent.tui.trace_processor import TuiTraceProcessor, TraceEvent, MemoryChanged


# ════════════════════════════════════════════════════════════
#  Custom Messages
# ════════════════════════════════════════════════════════════

def test_trace_event_with_string():
    evt = TraceEvent("hello")
    assert evt.text == "hello"


def test_trace_event_with_rich_text():
    from rich.text import Text
    t = Text("styled")
    evt = TraceEvent(t)
    assert evt.text is t


def test_memory_changed_message():
    msg = MemoryChanged()
    assert isinstance(msg, MemoryChanged)


# ════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════

@pytest.fixture
def mock_app():
    app = MagicMock()
    app.post_message = MagicMock()
    return app


@pytest.fixture
def processor(mock_app):
    return TuiTraceProcessor(mock_app)


def _make_span(data_cls_name, **attrs):
    """Create a mock span with specific span_data type."""
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
    span.span_id = f"span-{id(attrs)}"

    data = MagicMock(spec=cls_map.get(data_cls_name, MagicMock))
    data.__class__ = cls_map.get(data_cls_name, type(data))
    for k, v in attrs.items():
        setattr(data, k, v)
    span.span_data = data
    return span


# ════════════════════════════════════════════════════════════
#  Trace lifecycle
# ════════════════════════════════════════════════════════════

def test_on_trace_start_increments_counter(processor, mock_app):
    trace = MagicMock()
    processor.on_trace_start(trace)
    assert processor._reply_counter == 1
    # Check a TraceEvent was posted
    mock_app.post_message.assert_called()
    evt = mock_app.post_message.call_args[0][0]
    assert isinstance(evt, TraceEvent)
    assert "Reply #1" in str(evt.text)


def test_on_trace_start_multiple(processor, mock_app):
    processor.on_trace_start(MagicMock())
    processor.on_trace_start(MagicMock())
    assert processor._reply_counter == 2


def test_on_trace_start_resets_llm_counter(processor, mock_app):
    processor._llm_counter = 5
    processor.on_trace_start(MagicMock())
    assert processor._llm_counter == 0


def test_on_trace_end_noop(processor, mock_app):
    mock_app.post_message.reset_mock()
    processor.on_trace_end(MagicMock())
    mock_app.post_message.assert_not_called()


# ════════════════════════════════════════════════════════════
#  Span start
# ════════════════════════════════════════════════════════════

def test_agent_span_start(processor, mock_app):
    span = _make_span("AgentSpanData", name="TestAgent")
    processor.on_span_start(span)
    evt = mock_app.post_message.call_args[0][0]
    assert "TestAgent" in str(evt.text)


def test_generation_span_start_increments_llm_counter(processor, mock_app):
    span = _make_span("GenerationSpanData", model="gpt-4o-mini")
    processor.on_span_start(span)
    assert processor._llm_counter == 1
    evt = mock_app.post_message.call_args[0][0]
    assert "LLM #1" in str(evt.text)


def test_function_span_start_with_input(processor, mock_app):
    span = _make_span("FunctionSpanData", name="knowledge_search", input='{"query": "test"}')
    processor.on_span_start(span)
    evt = mock_app.post_message.call_args[0][0]
    assert "TOOL CALL" in str(evt.text)
    assert "knowledge_search" in str(evt.text)


def test_function_span_start_no_input(processor, mock_app):
    span = _make_span("FunctionSpanData", name="list_product", input="")
    processor.on_span_start(span)
    evt = mock_app.post_message.call_args[0][0]
    assert "list_product" in str(evt.text)


def test_mcp_list_tools_span_start(processor, mock_app):
    span = _make_span("MCPListToolsSpanData", server="GoSaaS")
    processor.on_span_start(span)
    evt = mock_app.post_message.call_args[0][0]
    assert "GoSaaS" in str(evt.text)


def test_handoff_span_start(processor, mock_app):
    span = _make_span("HandoffSpanData", from_agent="A", to_agent="B")
    processor.on_span_start(span)
    evt = mock_app.post_message.call_args[0][0]
    assert "HANDOFF" in str(evt.text)


def test_guardrail_span_start(processor, mock_app):
    span = _make_span("GuardrailSpanData", name="SafetyGuard")
    processor.on_span_start(span)
    evt = mock_app.post_message.call_args[0][0]
    assert "GUARDRAIL" in str(evt.text)


def test_unknown_span_start(processor, mock_app):
    span = MagicMock()
    span.span_id = "unk-1"
    span.span_data = MagicMock()
    type(span.span_data).__name__ = "CustomData"
    processor.on_span_start(span)
    mock_app.post_message.assert_called()


# ════════════════════════════════════════════════════════════
#  Span end
# ════════════════════════════════════════════════════════════

def test_agent_span_end(processor, mock_app):
    span = _make_span("AgentSpanData", name="TestAgent")
    processor.on_span_start(span)
    mock_app.post_message.reset_mock()
    processor.on_span_end(span)
    evt = mock_app.post_message.call_args[0][0]
    assert "finished" in str(evt.text).lower() or "Agent" in str(evt.text)


def test_generation_span_end_with_usage(processor, mock_app):
    span = _make_span("GenerationSpanData", model="gpt-4o-mini",
                       usage={"input_tokens": 100, "output_tokens": 50, "cached_tokens": 20})
    processor.on_span_start(span)
    mock_app.post_message.reset_mock()
    processor.on_span_end(span)
    evt = mock_app.post_message.call_args[0][0]
    text = str(evt.text)
    assert "100" in text
    assert "50" in text


def test_generation_span_end_no_usage(processor, mock_app):
    span = _make_span("GenerationSpanData", model="gpt-4o-mini", usage=None)
    processor.on_span_start(span)
    mock_app.post_message.reset_mock()
    processor.on_span_end(span)
    mock_app.post_message.assert_called()


def test_function_span_end_memory_add_posts_memory_changed(processor, mock_app):
    span = _make_span("FunctionSpanData", name="memory_add", input="", output="stored")
    processor.on_span_start(span)
    mock_app.post_message.reset_mock()
    processor.on_span_end(span)
    # Should post both TraceEvent and MemoryChanged
    calls = mock_app.post_message.call_args_list
    types = [type(c[0][0]) for c in calls]
    assert MemoryChanged in types


def test_function_span_end_memory_delete_posts_memory_changed(processor, mock_app):
    span = _make_span("FunctionSpanData", name="memory_delete", input="", output="deleted")
    processor.on_span_start(span)
    mock_app.post_message.reset_mock()
    processor.on_span_end(span)
    calls = mock_app.post_message.call_args_list
    types = [type(c[0][0]) for c in calls]
    assert MemoryChanged in types


def test_function_span_end_memory_search_posts_memory_changed(processor, mock_app):
    span = _make_span("FunctionSpanData", name="memory_search", input="", output="results")
    processor.on_span_start(span)
    mock_app.post_message.reset_mock()
    processor.on_span_end(span)
    calls = mock_app.post_message.call_args_list
    types = [type(c[0][0]) for c in calls]
    assert MemoryChanged in types


def test_function_span_end_non_memory_tool_no_memory_changed(processor, mock_app):
    span = _make_span("FunctionSpanData", name="knowledge_search", input="", output="results")
    processor.on_span_start(span)
    mock_app.post_message.reset_mock()
    processor.on_span_end(span)
    calls = mock_app.post_message.call_args_list
    types = [type(c[0][0]) for c in calls]
    assert MemoryChanged not in types


def test_mcp_list_tools_span_end(processor, mock_app):
    span = _make_span("MCPListToolsSpanData", server="MCP", result=[MagicMock(), MagicMock(), MagicMock()])
    processor.on_span_start(span)
    mock_app.post_message.reset_mock()
    processor.on_span_end(span)
    evt = mock_app.post_message.call_args[0][0]
    assert "3" in str(evt.text)


def test_guardrail_span_end_triggered(processor, mock_app):
    span = _make_span("GuardrailSpanData", name="Guard", triggered=True)
    processor.on_span_start(span)
    mock_app.post_message.reset_mock()
    processor.on_span_end(span)
    evt = mock_app.post_message.call_args[0][0]
    assert "TRIGGERED" in str(evt.text)


def test_guardrail_span_end_passed(processor, mock_app):
    span = _make_span("GuardrailSpanData", name="Guard", triggered=False)
    processor.on_span_start(span)
    mock_app.post_message.reset_mock()
    processor.on_span_end(span)
    evt = mock_app.post_message.call_args[0][0]
    assert "passed" in str(evt.text)


# ════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════

def test_truncate_long_text():
    result = TuiTraceProcessor._truncate("a" * 200, 80)
    assert len(result) == 81  # 80 + "…"
    assert result.endswith("…")


def test_truncate_short_text():
    result = TuiTraceProcessor._truncate("short", 80)
    assert result == "short"


def test_truncate_newlines():
    result = TuiTraceProcessor._truncate("line1\nline2", 80)
    assert "\n" not in result


def test_shutdown_noop(processor):
    processor.shutdown()


def test_force_flush_noop(processor):
    processor.force_flush()
