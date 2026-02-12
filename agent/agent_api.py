"""FastAPI Chat Server — POST /chat endpoint for AI Agent with MCP tools.

Connects to the Order Management MCP server on startup and exposes
an HTTP API at port 3000 for external clients (frontend, Postman, curl)
to chat with the Agent.

Usage:
    1. Start the MCP server:  cd mcp-server && python server.py
    2. Start this API:        cd agent && python agent_api.py
"""

import os
import traceback
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, Field

from agents import Agent, Runner, trace
from agents.mcp import MCPServerStreamableHttp

load_dotenv()

# ════════════════════════════════════════════════════════════
#  CONFIG
# ════════════════════════════════════════════════════════════

MCP_ORDER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")
AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-4o-mini")

AGENT_INSTRUCTIONS = """\
คุณคือ GoSaaS Order Management Assistant

คุณช่วยผู้ใช้เรื่อง:
- สร้าง/ดู/ลบ order draft และแนบการชำระเงิน
- ค้นหาสินค้าและดูรายละเอียด
- ตรวจสอบสถานะการจัดส่ง
- ดูรายงานยอดขาย
- ตรวจสอบที่อยู่
- ตอบคำถามทั่วไป (FAQ) และจัดประเภทข้อความ

กฎ:
- ตอบกลับภาษาเดียวกับที่ผู้ใช้พิมพ์มา
- ใช้ tools เพื่อดึงข้อมูลจริงเสมอ ห้ามเดาหรือแต่งข้อมูล
- เมื่อสร้าง order ให้ตรวจสอบที่อยู่และดึง meta data ก่อน
- แสดงผลลัพธ์ให้ชัดเจนและกระชับ
"""

# ════════════════════════════════════════════════════════════
#  IN-MEMORY SESSION STORE
# ════════════════════════════════════════════════════════════

sessions: dict[str, list] = {}

# ════════════════════════════════════════════════════════════
#  LIFESPAN — connect/disconnect MCP
# ════════════════════════════════════════════════════════════

order_mcp: MCPServerStreamableHttp | None = None
agent: Agent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global order_mcp, agent

    # ── Startup ──
    print(f"Connecting to MCP server: {MCP_ORDER_URL}")
    order_mcp = MCPServerStreamableHttp(
        name="Order MCP",
        params={"url": MCP_ORDER_URL},
        cache_tools_list=True,
    )
    await order_mcp.__aenter__()

    tools = await order_mcp.list_tools()
    print(f"MCP connected — {len(tools)} tools available:")
    for t in tools:
        print(f"  - {t.name}: {t.description[:60] if t.description else ''}")

    agent = Agent(
        name="GoSaaS Assistant",
        instructions=AGENT_INSTRUCTIONS,
        mcp_servers=[order_mcp],
        model=AGENT_MODEL,
    )
    print(f"Agent ready — model: {AGENT_MODEL}")

    yield

    # ── Shutdown ──
    print("Shutting down MCP connections...")
    await order_mcp.__aexit__(None, None, None)


# ════════════════════════════════════════════════════════════
#  FASTAPI APP
# ════════════════════════════════════════════════════════════

app = FastAPI(title="GoSaaS Chat API", lifespan=lifespan)


# ── Request / Response models ────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = Field(default=None, description="Session ID (auto-generated if omitted)")


class ChatResponse(BaseModel):
    session_id: str
    response: str
    memory_count: int


# ── POST /chat ───────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    # Resolve session_id
    session_id = req.session_id or uuid.uuid4().hex[:8]

    # Get or create conversation history
    history = sessions.setdefault(session_id, [])

    # Build input: history + new user message
    input_messages = history + [{"role": "user", "content": req.message}]

    # Run the agent
    try:
        with trace("Chat API"):
            result = await Runner.run(agent, input=input_messages)
    except Exception:
        traceback.print_exc()
        return ChatResponse(
            session_id=session_id,
            response="ขออภัย ระบบไม่สามารถประมวลผลได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง",
            memory_count=len(history),
        )

    # Extract response and update session
    try:
        sessions[session_id] = result.to_input_list()
        reply = result.final_output or "ขออภัย ไม่สามารถสร้างคำตอบได้ กรุณาลองใหม่"
    except Exception:
        traceback.print_exc()
        reply = "ขออภัย เกิดข้อผิดพลาดในการประมวลผลคำตอบ"

    return ChatResponse(
        session_id=session_id,
        response=reply,
        memory_count=len(sessions[session_id]),
    )


# ════════════════════════════════════════════════════════════
#  RUN
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("agent_api:app", host="0.0.0.0", port=3000, reload=True)
