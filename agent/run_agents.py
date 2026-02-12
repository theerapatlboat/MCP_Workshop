"""Interactive CLI Agent using OpenAI Agents SDK with local MCP Server.

Connects to the Order Management MCP server (server.py) and provides
an interactive CLI with streamed responses and real-time tracing of
every tool call and agent loop iteration.

Usage:
    1. Start the MCP server:  python server.py
    2. Run this agent:        python run_agents.py
"""

import asyncio
import sys
import os
import time

from dotenv import load_dotenv

from agents import (
    Agent,
    Runner,
    trace,
    set_trace_processors,
    AgentSpanData,
    FunctionSpanData,
    GenerationSpanData,
    MCPListToolsSpanData,
    HandoffSpanData,
    GuardrailSpanData,
)
from agents.mcp import MCPServerStreamableHttp
from openai.types.responses import ResponseTextDeltaEvent
from session_store import SessionStore

load_dotenv()


# ════════════════════════════════════════════════════════════
#  CONSOLE TRACE PROCESSOR
# ════════════════════════════════════════════════════════════

class ConsoleTraceProcessor:
    """Prints real-time trace events to stderr for observability.

    Shows agent loop iterations, tool calls with inputs/outputs,
    LLM generation details, and timing for every span.
    """

    COLORS = {
        "trace":      "\033[96m",   # cyan
        "agent":      "\033[93m",   # yellow
        "tool":       "\033[92m",   # green
        "llm":        "\033[95m",   # magenta
        "mcp":        "\033[94m",   # blue
        "handoff":    "\033[91m",   # red
        "guardrail":  "\033[33m",   # dark yellow
        "reset":      "\033[0m",
        "dim":        "\033[2m",
    }

    def __init__(self):
        self._times: dict[str, float] = {}

    # ── Trace lifecycle ──────────────────────────

    def on_trace_start(self, trace_obj) -> None:
        c = self.COLORS
        self._log(f"\n{c['trace']}{'━'*60}")
        self._log(f"  TRACE START ▸ {trace_obj.name}")
        self._log(f"  ID: {trace_obj.trace_id}")
        self._log(f"{'━'*60}{c['reset']}")

    def on_trace_end(self, trace_obj) -> None:
        c = self.COLORS
        self._log(f"{c['trace']}{'━'*60}")
        self._log(f"  TRACE END   ▸ {trace_obj.name}")
        self._log(f"{'━'*60}{c['reset']}\n")

    # ── Span lifecycle ───────────────────────────

    def on_span_start(self, span) -> None:
        self._times[span.span_id] = time.time()
        data = span.span_data
        c = self.COLORS

        if isinstance(data, AgentSpanData):
            tools = ", ".join(data.tools) if data.tools else "none"
            self._log(f"{c['agent']}  ▶ AGENT: {data.name}  [tools: {tools}]{c['reset']}")

        elif isinstance(data, FunctionSpanData):
            input_preview = self._truncate(data.input, 120) if data.input else ""
            self._log(f"{c['tool']}  ▶ TOOL CALL: {data.name}")
            if input_preview:
                self._log(f"    input: {input_preview}")
            self._log(c['reset'], end="")

        elif isinstance(data, GenerationSpanData):
            model = data.model or "unknown"
            self._log(f"{c['llm']}  ▶ LLM GENERATION  [model: {model}]{c['reset']}")

        elif isinstance(data, MCPListToolsSpanData):
            self._log(f"{c['mcp']}  ▶ MCP LIST TOOLS  [server: {data.server}]{c['reset']}")

        elif isinstance(data, HandoffSpanData):
            self._log(
                f"{c['handoff']}  ▶ HANDOFF: "
                f"{data.from_agent} → {data.to_agent}{c['reset']}"
            )

        elif isinstance(data, GuardrailSpanData):
            self._log(f"{c['guardrail']}  ▶ GUARDRAIL: {data.name}{c['reset']}")

        else:
            self._log(f"{c['dim']}  ▶ {type(data).__name__}{c['reset']}")

    def on_span_end(self, span) -> None:
        dt = time.time() - self._times.pop(span.span_id, time.time())
        data = span.span_data
        c = self.COLORS
        elapsed = f"{dt:.2f}s"

        if isinstance(data, AgentSpanData):
            self._log(f"{c['agent']}  ◀ AGENT DONE: {data.name}  [{elapsed}]{c['reset']}")

        elif isinstance(data, FunctionSpanData):
            output_preview = self._truncate(str(data.output), 200) if data.output else ""
            self._log(f"{c['tool']}  ◀ TOOL DONE: {data.name}  [{elapsed}]")
            if output_preview:
                self._log(f"    output: {output_preview}")
            self._log(c['reset'], end="")

        elif isinstance(data, GenerationSpanData):
            usage = ""
            if data.usage:
                inp = data.usage.get("input_tokens", "?")
                out = data.usage.get("output_tokens", "?")
                usage = f"  tokens: {inp} in / {out} out"
            self._log(
                f"{c['llm']}  ◀ LLM DONE  "
                f"[model: {data.model or '?'}, {elapsed}{usage}]{c['reset']}"
            )

        elif isinstance(data, MCPListToolsSpanData):
            count = len(data.result) if data.result else 0
            self._log(
                f"{c['mcp']}  ◀ MCP TOOLS LOADED: "
                f"{count} tools  [{elapsed}]{c['reset']}"
            )

        elif isinstance(data, HandoffSpanData):
            self._log(
                f"{c['handoff']}  ◀ HANDOFF DONE: "
                f"{data.from_agent} → {data.to_agent}  [{elapsed}]{c['reset']}"
            )

        elif isinstance(data, GuardrailSpanData):
            status = "TRIGGERED" if data.triggered else "passed"
            self._log(
                f"{c['guardrail']}  ◀ GUARDRAIL: "
                f"{data.name} — {status}  [{elapsed}]{c['reset']}"
            )

        else:
            self._log(f"{c['dim']}  ◀ {type(data).__name__}  [{elapsed}]{c['reset']}")

    def shutdown(self) -> None:
        pass

    def force_flush(self) -> None:
        pass

    # ── Helpers ──────────────────────────────────

    @staticmethod
    def _log(msg: str, **kwargs) -> None:
        print(msg, file=sys.stderr, flush=True, **kwargs)

    @staticmethod
    def _truncate(text: str, max_len: int = 120) -> str:
        text = text.replace("\n", " ").strip()
        if len(text) > max_len:
            return text[:max_len] + "…"
        return text


# ════════════════════════════════════════════════════════════
#  AGENT CONFIGURATION
# ════════════════════════════════════════════════════════════

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")
AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-4o-mini")
CLI_SESSION_ID = os.getenv("CLI_SESSION_ID", "cli")

session_store = SessionStore()

AGENT_INSTRUCTIONS = """\
You are GoSaaS Order Management Assistant.

You help users with:
- Order drafts: create, view, delete, attach payments
- Product search and details
- Smart product search via hybrid_search (semantic + substring + LLM refinement)
- Shipping status tracking
- Sales reports and summaries
- Address verification
- FAQ and intent classification

Rules:
- Reply in the same language the user writes in
- Always use tools to get real data — never guess or fabricate
- When creating orders, first verify the address and fetch meta data
- Show results clearly and concisely
- When users ask about products, choose the right tool:
  • hybrid_search — recommendations, comparisons, search by attributes (color, screen, price, brand)
    Supports filters: min_price, max_price, color, model, min_screen, max_screen, min_stock
  • list_product — check live stock/price, view all products, create orders
- Remember important user info with memory tools (long-term memory across sessions):
  • memory_add — store important info (name, preferences, budget, favorite brand, color)
  • memory_search — recall previously stored info before answering
  • memory_get_all — view all stored info for a user
  • memory_delete — forget info when the user asks
- When a user shares important info (name, budget, favorite brand), call memory_add immediately
- All memory tools require user_id parameter
"""


# ════════════════════════════════════════════════════════════
#  INTERACTIVE CLI
# ════════════════════════════════════════════════════════════

async def chat_loop(agent: Agent) -> None:
    """Interactive conversation loop with streaming and persistent history."""
    history = session_store.get(CLI_SESSION_ID)

    if history:
        print(f"\n  Session: {CLI_SESSION_ID} (resumed {len(history)} messages)")
    else:
        print(f"\n  Session: {CLI_SESSION_ID} (new)")

    print("\nCommands:")
    print("  Type your message to chat")
    print("  'clear' — reset conversation history")
    print("  'quit'  — exit\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            return

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            return
        if user_input.lower() == "clear":
            session_store.delete(CLI_SESSION_ID)
            history = []
            print("[Conversation history cleared]\n")
            continue

        # Build messages with conversation history
        messages = history + [{"role": "user", "content": user_input}]

        print("\nAssistant: ", end="", flush=True)

        try:
            with trace("Conversation Turn"):
                result = Runner.run_streamed(agent, input=messages)
                async for event in result.stream_events():
                    if (
                        event.type == "raw_response_event"
                        and isinstance(event.data, ResponseTextDeltaEvent)
                    ):
                        print(event.data.delta, end="", flush=True)

            print("\n")

            # Preserve full conversation history for next turn
            history = result.to_input_list()
            session_store.save(CLI_SESSION_ID, history)

        except Exception as e:
            print(f"\n\n[Error: {e}]\n")


async def main():
    # Install console trace processor (replaces default OpenAI exporter)
    set_trace_processors([ConsoleTraceProcessor()])

    print("=" * 60)
    print("  GoSaaS Order Management Agent")
    print("  Powered by OpenAI Agents SDK + MCP")
    print(f"  Model: {AGENT_MODEL}")
    print(f"  MCP Server: {MCP_SERVER_URL}")
    print("=" * 60)

    try:
        async with MCPServerStreamableHttp(
            name="GoSaaS MCP",
            params={"url": MCP_SERVER_URL},
            cache_tools_list=True,
        ) as server:
            # Show available tools on startup
            tools = await server.list_tools()
            print(f"\n  Connected — {len(tools)} tools available:")
            for t in tools:
                print(f"    - {t.name}: {t.description[:60] if t.description else ''}")

            agent = Agent(
                name="GoSaaS Assistant",
                instructions=AGENT_INSTRUCTIONS,
                mcp_servers=[server],
                model=AGENT_MODEL,
            )

            await chat_loop(agent)

    except ConnectionError:
        print(f"\nCould not connect to MCP server at {MCP_SERVER_URL}")
        print("Start it first:  python server.py")
        sys.exit(1)
    except Exception as e:
        print(f"\nFailed to connect to MCP server at {MCP_SERVER_URL}")
        print(f"Start it first:  python server.py")
        print(f"Error: {e}")
        sys.exit(1)


async def main_tui():
    """Launch the TUI version of the agent."""
    from tui.app import AgentTuiApp

    app = AgentTuiApp(
        mcp_url=MCP_SERVER_URL,
        model=AGENT_MODEL,
        session_id=CLI_SESSION_ID,
        session_store=session_store,
        agent_instructions=AGENT_INSTRUCTIONS,
    )
    await app.run_async()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GoSaaS Order Management Agent")
    parser.add_argument("--tui", action="store_true", help="Launch TUI interface")
    args = parser.parse_args()

    if args.tui:
        asyncio.run(main_tui())
    else:
        asyncio.run(main())
