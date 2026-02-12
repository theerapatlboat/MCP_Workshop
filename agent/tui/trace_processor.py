"""TUI-compatible trace processor for the OpenAI Agents SDK.

Posts trace events as Textual messages instead of printing to stderr.
"""

import time

from rich.text import Text
from textual.message import Message

from agents import (
    AgentSpanData,
    FunctionSpanData,
    GenerationSpanData,
    MCPListToolsSpanData,
    HandoffSpanData,
    GuardrailSpanData,
)


class TraceEvent(Message):
    """Carries a Rich Text trace line to the TUI."""

    def __init__(self, text: Text | str) -> None:
        super().__init__()
        self.text = text


class MemoryChanged(Message):
    """Posted when the agent uses a memory tool, to trigger LTM refresh."""
    pass


class TuiTraceProcessor:
    """Bridges OpenAI Agents SDK tracing into the Textual event loop."""

    MEMORY_TOOLS = {"memory_add", "memory_delete", "memory_search"}

    def __init__(self, app) -> None:
        self._app = app
        self._times: dict[str, float] = {}
        self._reply_counter = 0
        self._llm_counter = 0

    # ── Trace lifecycle ──────────────────────────────

    def on_trace_start(self, trace_obj) -> None:
        self._reply_counter += 1
        self._llm_counter = 0
        self._post(Text(f"\nTraces for Reply #{self._reply_counter}", style="bold cyan"))

    def on_trace_end(self, trace_obj) -> None:
        pass

    # ── Span lifecycle ───────────────────────────────

    def on_span_start(self, span) -> None:
        self._times[span.span_id] = time.time()
        data = span.span_data

        if isinstance(data, AgentSpanData):
            self._post(Text(f">>> Agent started: {data.name}", style="bold yellow"))

        elif isinstance(data, GenerationSpanData):
            self._llm_counter += 1
            self._post(Text(f"LLM #{self._llm_counter} ...", style="magenta"))

        elif isinstance(data, FunctionSpanData):
            preview = self._truncate(data.input, 80) if data.input else ""
            line = f"TOOL CALL: {data.name}"
            if preview:
                line += f"  ({preview})"
            self._post(Text(line, style="green"))

        elif isinstance(data, MCPListToolsSpanData):
            self._post(Text(f"MCP LIST TOOLS: {data.server}", style="blue"))

        elif isinstance(data, HandoffSpanData):
            self._post(Text(f"HANDOFF: {data.from_agent} → {data.to_agent}", style="red"))

        elif isinstance(data, GuardrailSpanData):
            self._post(Text(f"GUARDRAIL: {data.name}", style="dark_orange"))

        else:
            self._post(Text(f"  {type(data).__name__}", style="dim"))

    def on_span_end(self, span) -> None:
        dt = time.time() - self._times.pop(span.span_id, time.time())
        data = span.span_data
        elapsed = f"{dt:.1f}s"

        if isinstance(data, AgentSpanData):
            self._post(Text(f"<<< Agent finished: {data.name}  [{elapsed}]", style="bold yellow"))

        elif isinstance(data, GenerationSpanData):
            usage_str = ""
            if data.usage:
                inp = data.usage.get("input_tokens", "?")
                out = data.usage.get("output_tokens", "?")
                cached = data.usage.get("cached_tokens", None)
                usage_str = f"  [in:{inp}"
                if cached:
                    usage_str += f" cached:{cached}"
                usage_str += f" out:{out}]"
            self._post(Text(
                f"LLM #{self._llm_counter} done {elapsed}{usage_str}",
                style="magenta",
            ))

        elif isinstance(data, FunctionSpanData):
            output_preview = ""
            if data.output:
                output_preview = f"  → {self._truncate(str(data.output), 100)}"
            self._post(Text(f"TOOL DONE: {data.name}  [{elapsed}]{output_preview}", style="green"))
            if data.name in self.MEMORY_TOOLS:
                self._app.post_message(MemoryChanged())

        elif isinstance(data, MCPListToolsSpanData):
            count = len(data.result) if data.result else 0
            self._post(Text(f"MCP TOOLS LOADED: {count} tools  [{elapsed}]", style="blue"))

        elif isinstance(data, HandoffSpanData):
            self._post(Text(
                f"HANDOFF DONE: {data.from_agent} → {data.to_agent}  [{elapsed}]",
                style="red",
            ))

        elif isinstance(data, GuardrailSpanData):
            status = "TRIGGERED" if data.triggered else "passed"
            self._post(Text(f"GUARDRAIL: {data.name} — {status}  [{elapsed}]", style="dark_orange"))

        else:
            self._post(Text(f"  {type(data).__name__}  [{elapsed}]", style="dim"))

    def shutdown(self) -> None:
        pass

    def force_flush(self) -> None:
        pass

    # ── Helpers ──────────────────────────────────────

    def _post(self, text: Text | str) -> None:
        self._app.post_message(TraceEvent(text))

    @staticmethod
    def _truncate(text: str, max_len: int = 80) -> str:
        text = text.replace("\n", " ").strip()
        if len(text) > max_len:
            return text[:max_len] + "…"
        return text
