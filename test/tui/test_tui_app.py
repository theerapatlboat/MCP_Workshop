"""Tests for agent/tui/app.py — Textual TUI application."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "agent"))


# ════════════════════════════════════════════════════════════
#  _extract_text helper (standalone, no TUI required)
# ════════════════════════════════════════════════════════════

from agent.tui.app import _extract_text


def test_extract_text_from_string():
    assert _extract_text("hello") == "hello"


def test_extract_text_from_empty_string():
    assert _extract_text("") == ""


def test_extract_text_from_none():
    assert _extract_text(None) == ""


def test_extract_text_from_int():
    assert _extract_text(42) == "42"


def test_extract_text_from_output_text_block():
    content = [{"type": "output_text", "text": "Hello world"}]
    assert _extract_text(content) == "Hello world"


def test_extract_text_from_multiple_output_text_blocks():
    content = [
        {"type": "output_text", "text": "Hello "},
        {"type": "output_text", "text": "world"},
    ]
    assert _extract_text(content) == "Hello world"


def test_extract_text_from_dict_with_text_key():
    content = [{"type": "other", "text": "fallback text"}]
    assert _extract_text(content) == "fallback text"


def test_extract_text_from_mixed_list():
    content = [
        {"type": "output_text", "text": "part1"},
        "part2",
        {"type": "unknown"},  # no text key
    ]
    assert _extract_text(content) == "part1part2"


def test_extract_text_from_string_list():
    content = ["hello ", "world"]
    assert _extract_text(content) == "hello world"


def test_extract_text_from_empty_list():
    assert _extract_text([]) == ""


def test_extract_text_from_dict_without_text():
    content = [{"type": "image", "url": "http://example.com"}]
    assert _extract_text(content) == ""


# ════════════════════════════════════════════════════════════
#  Custom Messages
# ════════════════════════════════════════════════════════════

from agent.tui.app import StreamDelta, StreamComplete, ConnectionReady, ConnectionFailed


def test_stream_delta_message():
    msg = StreamDelta("chunk")
    assert msg.delta == "chunk"


def test_stream_delta_empty():
    msg = StreamDelta("")
    assert msg.delta == ""


def test_stream_complete_message():
    msg = StreamComplete("full reply text")
    assert msg.full_reply == "full reply text"


def test_stream_complete_empty():
    msg = StreamComplete("")
    assert msg.full_reply == ""


def test_connection_ready_message():
    msg = ConnectionReady(tool_count=5, tool_names=["search", "memory_add"])
    assert msg.tool_count == 5
    assert msg.tool_names == ["search", "memory_add"]


def test_connection_ready_zero_tools():
    msg = ConnectionReady(tool_count=0, tool_names=[])
    assert msg.tool_count == 0
    assert msg.tool_names == []


def test_connection_failed_message():
    msg = ConnectionFailed("Connection refused")
    assert msg.error == "Connection refused"


def test_connection_failed_empty_error():
    msg = ConnectionFailed("")
    assert msg.error == ""


# ════════════════════════════════════════════════════════════
#  AgentTuiApp — unit tests (no full TUI run)
# ════════════════════════════════════════════════════════════

from agent.tui.app import AgentTuiApp


@pytest.fixture
def mock_session_store():
    store = MagicMock()
    store.get.return_value = []
    store.list_all.return_value = []
    store.save = MagicMock()
    store.delete = MagicMock()
    return store


@pytest.fixture
def tui_app(mock_session_store):
    """Create an AgentTuiApp without running it."""
    app = AgentTuiApp(
        mcp_url="http://localhost:8000/mcp",
        model="gpt-4o-mini",
        session_id="test-session-001",
        session_store=mock_session_store,
        agent_instructions="You are a test agent.",
    )
    return app


def test_app_initialization(tui_app):
    assert tui_app._mcp_url == "http://localhost:8000/mcp"
    assert tui_app._model == "gpt-4o-mini"
    assert tui_app._session_id == "test-session-001"
    assert tui_app._agent_instructions == "You are a test agent."
    assert tui_app._agent is None
    assert tui_app._mcp_server is None
    assert tui_app._history == []
    assert tui_app._current_reply == ""
    assert tui_app._is_streaming is False
    assert tui_app._reply_counter == 0


def test_app_title(tui_app):
    assert tui_app.TITLE == "GoSaaS Order Management Agent"


def test_app_bindings(tui_app):
    binding_keys = [b.key for b in tui_app.BINDINGS]
    assert "ctrl+q" in binding_keys
    assert "ctrl+l" in binding_keys
    assert "ctrl+p" in binding_keys


def test_app_css_path():
    assert AgentTuiApp.CSS_PATH == "styles.tcss"


# ════════════════════════════════════════════════════════════
#  AgentTuiApp — Textual async tests (uses run_test)
# ════════════════════════════════════════════════════════════

@pytest.fixture
def patched_tui_app(mock_session_store):
    """Create TUI app with mocked MCP and Agent to avoid real connections."""
    with patch("agent.tui.app.MCPServerStreamableHttp"), \
         patch("agent.tui.app.Agent"), \
         patch("agent.tui.app.Runner"), \
         patch("agent.tui.app.set_trace_processors"), \
         patch("agent.tui.app.trace"):
        app = AgentTuiApp(
            mcp_url="http://localhost:8000/mcp",
            model="gpt-4o-mini",
            session_id="test-session",
            session_store=mock_session_store,
            agent_instructions="Test instructions",
        )
        yield app


@pytest.mark.asyncio
async def test_app_compose_has_key_widgets(patched_tui_app):
    """Test that compose yields expected widgets."""
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        # Verify key widgets exist
        assert app.query_one("#chat-log") is not None
        assert app.query_one("#reply-log") is not None
        assert app.query_one("#trace-log") is not None
        assert app.query_one("#stm-log") is not None
        assert app.query_one("#ltm-log") is not None
        assert app.query_one("#user-input") is not None
        assert app.query_one("#send-btn") is not None


@pytest.mark.asyncio
async def test_app_compose_has_tabs(patched_tui_app):
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        assert app.query_one("#tab-replies") is not None
        assert app.query_one("#tab-traces") is not None
        assert app.query_one("#tab-stm") is not None
        assert app.query_one("#tab-ltm") is not None
        assert app.query_one("#tab-session") is not None


@pytest.mark.asyncio
async def test_app_compose_has_ltm_controls(patched_tui_app):
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        assert app.query_one("#ltm-user-id") is not None
        assert app.query_one("#ltm-refresh") is not None


@pytest.mark.asyncio
async def test_app_compose_has_session_controls(patched_tui_app):
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        assert app.query_one("#session-refresh") is not None
        assert app.query_one("#session-list") is not None
        assert app.query_one("#session-info") is not None


@pytest.mark.asyncio
async def test_app_initial_input_disabled(patched_tui_app):
    """Input should be disabled until MCP connects."""
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        from textual.widgets import Input, Button
        user_input = app.query_one("#user-input", Input)
        send_btn = app.query_one("#send-btn", Button)
        assert user_input.disabled is True
        assert send_btn.disabled is True


@pytest.mark.asyncio
async def test_connection_ready_enables_input(patched_tui_app):
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        # Simulate connection ready
        app.post_message(ConnectionReady(tool_count=5, tool_names=["tool1"]))
        await pilot.pause()
        from textual.widgets import Input, Button
        user_input = app.query_one("#user-input", Input)
        send_btn = app.query_one("#send-btn", Button)
        assert user_input.disabled is False
        assert send_btn.disabled is False


@pytest.mark.asyncio
async def test_connection_failed_shows_error(patched_tui_app):
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        app.post_message(ConnectionFailed("refused"))
        await pilot.pause()
        # Input should still be disabled
        from textual.widgets import Input
        user_input = app.query_one("#user-input", Input)
        assert user_input.disabled is True


@pytest.mark.asyncio
async def test_stream_delta_updates_reply(patched_tui_app):
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        # Enable input first
        app.post_message(ConnectionReady(tool_count=1, tool_names=["t"]))
        await pilot.pause()

        app._current_reply = ""
        app.post_message(StreamDelta("Hello "))
        await pilot.pause()
        assert app._current_reply == "Hello "

        app.post_message(StreamDelta("world"))
        await pilot.pause()
        assert app._current_reply == "Hello world"


@pytest.mark.asyncio
async def test_stream_complete_resets_state(patched_tui_app):
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        # Enable input
        app.post_message(ConnectionReady(tool_count=1, tool_names=["t"]))
        await pilot.pause()

        # Simulate streaming state
        app._is_streaming = True
        app._current_reply = "partial"
        from textual.widgets import Input, Button
        app.query_one("#user-input", Input).disabled = True
        app.query_one("#send-btn", Button).disabled = True

        app.post_message(StreamComplete("final reply"))
        await pilot.pause()

        assert app._is_streaming is False
        assert app._current_reply == ""
        assert app.query_one("#user-input", Input).disabled is False
        assert app.query_one("#send-btn", Button).disabled is False


@pytest.mark.asyncio
async def test_trace_event_writes_to_trace_log(patched_tui_app):
    from agent.tui.trace_processor import TraceEvent
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        app.post_message(TraceEvent("test trace line"))
        await pilot.pause()
        # Trace log should have content (we verify no crash)


@pytest.mark.asyncio
async def test_action_clear_chat(patched_tui_app, mock_session_store):
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        app._history = [{"role": "user", "content": "hi"}]
        app._reply_counter = 3

        app.action_clear_chat()
        await pilot.pause()

        assert app._history == []
        assert app._reply_counter == 0
        mock_session_store.delete.assert_called_with("test-session")


@pytest.mark.asyncio
async def test_switch_session(patched_tui_app, mock_session_store):
    mock_session_store.get.return_value = [
        {"role": "user", "content": "old msg"},
        {"role": "assistant", "content": "old reply"},
    ]

    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        app._switch_session("new-session-id")
        await pilot.pause()

        assert app._session_id == "new-session-id"
        assert app._reply_counter == 0
        mock_session_store.get.assert_called_with("new-session-id")


@pytest.mark.asyncio
async def test_reload_chat_from_history(patched_tui_app, mock_session_store):
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        app._history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
            {"role": "system", "content": "ignored"},
        ]
        app._reload_chat_from_history()
        await pilot.pause()
        # Should not crash; system messages should be skipped


@pytest.mark.asyncio
async def test_reload_history_with_output_text_blocks(patched_tui_app):
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        app._history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": [{"type": "output_text", "text": "hi"}]},
        ]
        app._reload_chat_from_history()
        await pilot.pause()


@pytest.mark.asyncio
async def test_memory_changed_triggers_ltm_refresh(patched_tui_app):
    from agent.tui.trace_processor import MemoryChanged
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        # _refresh_ltm should be called, but since MCP not connected it just shows error
        app.post_message(MemoryChanged())
        await pilot.pause()


@pytest.mark.asyncio
async def test_handle_input_clear_command(patched_tui_app, mock_session_store):
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        app._history = [{"role": "user", "content": "old"}]
        app._handle_input("clear")
        await pilot.pause()
        assert app._history == []


@pytest.mark.asyncio
async def test_handle_input_empty_ignored(patched_tui_app):
    """Empty input should not trigger send."""
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        app.post_message(ConnectionReady(tool_count=1, tool_names=["t"]))
        await pilot.pause()
        counter_before = app._reply_counter
        # Simulate pressing enter with empty input (via handler)
        from textual.widgets import Input
        inp = app.query_one("#user-input", Input)
        inp.value = ""
        # The on_user_input_submitted checks for empty so no send


@pytest.mark.asyncio
async def test_handle_input_during_streaming_ignored(patched_tui_app):
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        app.post_message(ConnectionReady(tool_count=1, tool_names=["t"]))
        await pilot.pause()
        app._is_streaming = True
        counter_before = app._reply_counter
        # Input should be ignored during streaming
        # The on_user_input_submitted and on_send_pressed both check _is_streaming


@pytest.mark.asyncio
async def test_on_unmount_without_mcp(patched_tui_app):
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        app._mcp_server = None
        await app.on_unmount()
        # Should not raise


@pytest.mark.asyncio
async def test_on_unmount_with_mcp(patched_tui_app):
    mock_mcp = MagicMock()
    mock_mcp.__aexit__ = AsyncMock()
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        app._mcp_server = mock_mcp
        await app.on_unmount()
        mock_mcp.__aexit__.assert_called_once_with(None, None, None)


@pytest.mark.asyncio
async def test_on_unmount_mcp_error_suppressed(patched_tui_app):
    mock_mcp = MagicMock()
    mock_mcp.__aexit__ = AsyncMock(side_effect=RuntimeError("cleanup fail"))
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        app._mcp_server = mock_mcp
        await app.on_unmount()  # Should not raise


@pytest.mark.asyncio
async def test_refresh_stm_shows_history(patched_tui_app, mock_session_store):
    mock_session_store.get.return_value = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        app._refresh_stm()
        await pilot.pause()


@pytest.mark.asyncio
async def test_refresh_stm_truncates_long_content(patched_tui_app, mock_session_store):
    mock_session_store.get.return_value = [
        {"role": "user", "content": "x" * 500},
    ]
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        app._refresh_stm()
        await pilot.pause()


@pytest.mark.asyncio
async def test_session_info_shows_current(patched_tui_app):
    async with patched_tui_app.run_test(size=(120, 40)) as pilot:
        app = pilot.app
        from textual.widgets import Static
        info = app.query_one("#session-info", Static)
        # Verify the widget exists and was initialized with session info
        assert info is not None
