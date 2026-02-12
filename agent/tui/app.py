"""Textual TUI for GoSaaS Order Management Agent.

Provides a rich terminal interface with chat panel, trace viewer,
short/long-term memory tabs, and session management.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import httpx
from rich.text import Text
from textual import work, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import (
    Header,
    Footer,
    Input,
    Button,
    Static,
    TabbedContent,
    TabPane,
    RichLog,
    ListView,
    ListItem,
    Label,
)

from agents import Agent, Runner, trace, set_trace_processors
from agents.mcp import MCPServerStreamableHttp
from openai.types.responses import ResponseTextDeltaEvent

# Ensure parent dir is on path for session_store import
sys.path.insert(0, str(Path(__file__).parent.parent))
from session_store import SessionStore
from tui.trace_processor import TuiTraceProcessor, TraceEvent, MemoryChanged


# ═══════════════════════════════════════════════════════
#  Custom Messages
# ═══════════════════════════════════════════════════════


class StreamDelta(Message):
    """A single text delta from the agent's streaming response."""

    def __init__(self, delta: str) -> None:
        super().__init__()
        self.delta = delta


class StreamComplete(Message):
    """Agent response finished streaming."""

    def __init__(self, full_reply: str) -> None:
        super().__init__()
        self.full_reply = full_reply


class ConnectionReady(Message):
    """MCP connection established, agent ready."""

    def __init__(self, tool_count: int, tool_names: list[str]) -> None:
        super().__init__()
        self.tool_count = tool_count
        self.tool_names = tool_names


class ConnectionFailed(Message):
    """MCP connection failed."""

    def __init__(self, error: str) -> None:
        super().__init__()
        self.error = error


# ═══════════════════════════════════════════════════════
#  TUI Application
# ═══════════════════════════════════════════════════════


class AgentTuiApp(App):
    """Textual TUI for GoSaaS Order Management Agent."""

    CSS_PATH = "styles.tcss"
    TITLE = "GoSaaS Order Management Agent"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+l", "clear_chat", "Clear chat"),
        Binding("ctrl+p", "command_palette", "Palette"),
    ]

    def __init__(
        self,
        mcp_url: str,
        model: str,
        session_id: str,
        session_store: SessionStore,
        agent_instructions: str,
    ) -> None:
        super().__init__()
        self._mcp_url = mcp_url
        self._model = model
        self._session_id = session_id
        self._session_store = session_store
        self._agent_instructions = agent_instructions
        self._agent: Agent | None = None
        self._mcp_server: MCPServerStreamableHttp | None = None
        self._history: list = []
        self._current_reply = ""
        self._is_streaming = False
        self._reply_counter = 0

    # ── Layout ───────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-body"):
            with VerticalScroll(id="chat-panel"):
                yield RichLog(id="chat-log", auto_scroll=True, markup=True, wrap=True)
            with Vertical(id="right-panel"):
                with TabbedContent(id="tabs"):
                    with TabPane("Replies", id="tab-replies"):
                        yield RichLog(
                            id="reply-log", auto_scroll=True, markup=True, wrap=True
                        )
                    with TabPane("Traces", id="tab-traces"):
                        yield RichLog(
                            id="trace-log", auto_scroll=True, markup=True, wrap=True
                        )
                    with TabPane("STM", id="tab-stm"):
                        yield RichLog(
                            id="stm-log", auto_scroll=True, markup=True, wrap=True
                        )
                    with TabPane("LTM", id="tab-ltm"):
                        with Vertical():
                            with Horizontal(id="ltm-controls"):
                                yield Input(
                                    id="ltm-user-id",
                                    placeholder="user_id",
                                    value="cli",
                                )
                                yield Button(
                                    "Refresh", id="ltm-refresh", variant="default"
                                )
                            yield RichLog(
                                id="ltm-log",
                                auto_scroll=True,
                                markup=True,
                                wrap=True,
                            )
                    with TabPane("Session", id="tab-session"):
                        with Vertical():
                            yield Button(
                                "Refresh Sessions",
                                id="session-refresh",
                                variant="default",
                            )
                            yield ListView(id="session-list")
                            yield Static(
                                f"Current: {self._session_id}", id="session-info"
                            )
        with Horizontal(id="input-bar"):
            yield Input(id="user-input", placeholder="Type your message...")
            yield Button("Send", id="send-btn", variant="primary")
        yield Footer()

    # ── Lifecycle ────────────────────────────────────

    async def on_mount(self) -> None:
        # Disable input until connected
        self.query_one("#user-input", Input).disabled = True
        self.query_one("#send-btn", Button).disabled = True

        # Load existing history
        self._history = self._session_store.get(self._session_id)
        if self._history:
            self._reload_chat_from_history()

        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(Text("Connecting to MCP server...", style="dim"))

        self.connect_mcp()

    @work(exclusive=True)
    async def connect_mcp(self) -> None:
        """Connect to MCP server and create the agent."""
        try:
            self._mcp_server = MCPServerStreamableHttp(
                name="GoSaaS MCP",
                params={"url": self._mcp_url},
                cache_tools_list=True,
            )
            await self._mcp_server.__aenter__()
            tools = await self._mcp_server.list_tools()

            # Install TUI trace processor
            trace_proc = TuiTraceProcessor(self)
            set_trace_processors([trace_proc])

            self._agent = Agent(
                name="GoSaaS Assistant",
                instructions=self._agent_instructions,
                mcp_servers=[self._mcp_server],
                model=self._model,
            )

            self.post_message(
                ConnectionReady(
                    tool_count=len(tools),
                    tool_names=[t.name for t in tools],
                )
            )
        except Exception as e:
            self.post_message(ConnectionFailed(str(e)))

    def on_connection_ready(self, event: ConnectionReady) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(
            Text(
                f"Connected — {event.tool_count} tools available",
                style="bold green",
            )
        )
        chat_log.write(Text(f"Model: {self._model}", style="dim"))
        chat_log.write(
            Text(
                f"Session: {self._session_id} ({len(self._history)} messages)",
                style="dim",
            )
        )
        chat_log.write("")

        # Enable input
        self.query_one("#user-input", Input).disabled = False
        self.query_one("#send-btn", Button).disabled = False
        self.query_one("#user-input", Input).focus()

    def on_connection_failed(self, event: ConnectionFailed) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(Text(f"Connection failed: {event.error}", style="bold red"))
        chat_log.write(
            Text("Start MCP server first:  python server.py", style="yellow")
        )

    # ── Input handling ───────────────────────────────

    @on(Input.Submitted, "#user-input")
    def on_user_input_submitted(self, event: Input.Submitted) -> None:
        if not event.value.strip() or self._is_streaming:
            return
        user_text = event.value.strip()
        event.input.clear()
        self._handle_input(user_text)

    @on(Button.Pressed, "#send-btn")
    def on_send_pressed(self, event: Button.Pressed) -> None:
        inp = self.query_one("#user-input", Input)
        if not inp.value.strip() or self._is_streaming:
            return
        user_text = inp.value.strip()
        inp.clear()
        self._handle_input(user_text)

    def _handle_input(self, user_text: str) -> None:
        if user_text.lower() == "clear":
            self.action_clear_chat()
            return

        # Show user message in chat
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(Text(f"You: {user_text}", style="bold cyan"))

        # Prepare reply log
        self._reply_counter += 1
        reply_log = self.query_one("#reply-log", RichLog)
        reply_log.clear()
        reply_log.write(Text(f"Reply #{self._reply_counter}", style="bold"))
        reply_log.write("")

        # Start streaming
        self._current_reply = ""
        self._is_streaming = True
        self.query_one("#user-input", Input).disabled = True
        self.query_one("#send-btn", Button).disabled = True

        self.send_message(user_text)

    @work(exclusive=True)
    async def send_message(self, user_text: str) -> None:
        """Run the agent with streaming and post results to the UI."""
        messages = self._history + [{"role": "user", "content": user_text}]
        full_reply = ""

        try:
            with trace("Conversation Turn"):
                result = Runner.run_streamed(self._agent, input=messages)
                async for event in result.stream_events():
                    if (
                        event.type == "raw_response_event"
                        and isinstance(event.data, ResponseTextDeltaEvent)
                    ):
                        delta = event.data.delta
                        full_reply += delta
                        self.post_message(StreamDelta(delta=delta))

            self._history = result.to_input_list()
            self._session_store.save(self._session_id, self._history)
            self.post_message(StreamComplete(full_reply=full_reply))

        except Exception as e:
            self.post_message(StreamComplete(full_reply=f"[Error: {e}]"))

    # ── Stream event handlers ────────────────────────

    def on_stream_delta(self, event: StreamDelta) -> None:
        self._current_reply += event.delta
        # Append delta to reply log
        reply_log = self.query_one("#reply-log", RichLog)
        reply_log.write(event.delta)

    def on_stream_complete(self, event: StreamComplete) -> None:
        self._is_streaming = False

        # Write final reply to chat
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(Text(f"Assistant: {event.full_reply}", style="green"))
        chat_log.write("")

        # Clean reply log — show final clean version
        reply_log = self.query_one("#reply-log", RichLog)
        reply_log.clear()
        reply_log.write(Text(f"Reply #{self._reply_counter}", style="bold"))
        reply_log.write("")
        reply_log.write(event.full_reply)

        # Refresh STM
        self._refresh_stm()

        # Re-enable input
        self._current_reply = ""
        self.query_one("#user-input", Input).disabled = False
        self.query_one("#send-btn", Button).disabled = False
        self.query_one("#user-input", Input).focus()

    # ── Trace event handler ──────────────────────────

    def on_trace_event(self, event: TraceEvent) -> None:
        trace_log = self.query_one("#trace-log", RichLog)
        trace_log.write(event.text)

    # ── Memory changed handler ───────────────────────

    def on_memory_changed(self, event: MemoryChanged) -> None:
        self._refresh_ltm()

    # ── Tab refresh methods ──────────────────────────

    def _refresh_stm(self) -> None:
        """Refresh the STM tab with current session history."""
        stm_log = self.query_one("#stm-log", RichLog)
        stm_log.clear()
        history = self._session_store.get(self._session_id)
        stm_log.write(
            Text(
                f"Session: {self._session_id} — {len(history)} messages\n",
                style="bold",
            )
        )
        for msg in history:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            if isinstance(content, list):
                # tool_call / tool_result messages
                content = json.dumps(content, ensure_ascii=False)
            if not content:
                continue
            if len(content) > 300:
                content = content[:300] + "..."
            style = {"user": "cyan", "assistant": "green"}.get(role, "dim")
            stm_log.write(Text(f"[{role}] {content}", style=style))

    @work(exclusive=False)
    async def _refresh_ltm(self) -> None:
        """Fetch long-term memories from MCP server."""
        user_id = self.query_one("#ltm-user-id", Input).value or "cli"
        ltm_log = self.query_one("#ltm-log", RichLog)
        ltm_log.clear()
        ltm_log.write(Text("Loading memories...", style="dim"))

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    self._mcp_url,
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {
                            "name": "memory_get_all",
                            "arguments": {"user_id": user_id},
                        },
                        "id": 1,
                    },
                    headers={"Content-Type": "application/json"},
                )
                data = resp.json()
                result = data.get("result", {})

                # Parse MCP tool response
                items = []
                if isinstance(result, dict) and "content" in result:
                    content = result["content"]
                    if isinstance(content, list) and content:
                        text_content = content[0].get("text", "{}")
                        try:
                            parsed = json.loads(text_content)
                            memories = parsed.get("memories", parsed)
                            if isinstance(memories, dict):
                                items = memories.get("results", [])
                            elif isinstance(memories, list):
                                items = memories
                        except json.JSONDecodeError:
                            items = []

                ltm_log.clear()
                if not items:
                    ltm_log.write(
                        Text(f"No memories found for user: {user_id}", style="dim")
                    )
                else:
                    ltm_log.write(
                        Text(
                            f"Memories for user: {user_id} ({len(items)} total)",
                            style="bold",
                        )
                    )
                    ltm_log.write("")
                    for i, mem in enumerate(items, 1):
                        mem_text = mem.get("memory", str(mem))
                        mem_id = str(mem.get("id", "?"))[:12]
                        ltm_log.write(Text(f"  {i}. {mem_text}", style="white"))
                        ltm_log.write(Text(f"     id: {mem_id}...", style="dim"))

        except Exception as e:
            ltm_log.clear()
            ltm_log.write(Text(f"Error fetching LTM: {e}", style="red"))

    def _refresh_sessions(self) -> None:
        """Refresh the Session tab with all sessions."""
        session_list = self.query_one("#session-list", ListView)
        session_list.clear()
        sessions = self._session_store.list_all()

        for s in sessions:
            sid = s["session_id"]
            count = s["message_count"]
            updated = datetime.fromtimestamp(s["updated_at"]).strftime(
                "%Y-%m-%d %H:%M"
            )
            marker = " *" if sid == self._session_id else ""
            item = ListItem(
                Label(f"{sid} — {count} msgs — {updated}{marker}"),
                id=f"sess-{sid}",
            )
            session_list.append(item)

        self.query_one("#session-info", Static).update(
            f"Current: {self._session_id} | Messages: {len(self._history)}"
        )

    # ── Button handlers ──────────────────────────────

    @on(Button.Pressed, "#ltm-refresh")
    def on_ltm_refresh(self, event: Button.Pressed) -> None:
        self._refresh_ltm()

    @on(Button.Pressed, "#session-refresh")
    def on_session_refresh(self, event: Button.Pressed) -> None:
        self._refresh_sessions()

    @on(ListView.Selected, "#session-list")
    def on_session_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if item.id and item.id.startswith("sess-"):
            new_session_id = item.id[5:]  # Strip "sess-" prefix
            self._switch_session(new_session_id)

    def _switch_session(self, session_id: str) -> None:
        """Switch to a different session."""
        self._session_id = session_id
        self._history = self._session_store.get(session_id)
        self._reply_counter = 0
        self._reload_chat_from_history()
        self._refresh_stm()
        self.query_one("#session-info", Static).update(
            f"Current: {session_id} | Messages: {len(self._history)}"
        )
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(
            Text(f"[Switched to session: {session_id}]", style="yellow")
        )
        chat_log.write("")

    def _reload_chat_from_history(self) -> None:
        """Reload the chat panel from stored history."""
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.clear()
        for msg in self._history:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            if isinstance(content, list):
                continue  # Skip tool_call/tool_result in chat view
            if not content:
                continue
            style = {"user": "bold cyan", "assistant": "green"}.get(role, "dim")
            prefix = "You" if role == "user" else "Assistant"
            chat_log.write(Text(f"{prefix}: {content}", style=style))
        chat_log.write("")

    # ── Actions ──────────────────────────────────────

    def action_clear_chat(self) -> None:
        """Clear conversation history for current session."""
        self._session_store.delete(self._session_id)
        self._history = []
        self._reply_counter = 0
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.clear()
        chat_log.write(Text("[Conversation history cleared]", style="yellow"))
        chat_log.write("")
        self._refresh_stm()
        # Clear traces and replies
        self.query_one("#trace-log", RichLog).clear()
        self.query_one("#reply-log", RichLog).clear()

    async def on_unmount(self) -> None:
        """Clean up MCP connection on exit."""
        if self._mcp_server:
            try:
                await self._mcp_server.__aexit__(None, None, None)
            except Exception:
                pass
