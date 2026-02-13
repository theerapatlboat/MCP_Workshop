"""FastAPI Chat Server — POST /chat endpoint for AI Agent with MCP tools.

Connects to the Order Management MCP server on startup and exposes
an HTTP API at port 3000 for external clients (frontend, Postman, curl)
to chat with the Agent.

Usage:
    1. Start the MCP server:  cd mcp-server && python server.py
    2. Start this API:        cd agent && python agent_api.py
"""

import os
import re
import traceback
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from openai import BadRequestError
from pydantic import BaseModel, Field

from agents import Agent, Runner, trace
from agents.mcp import MCPServerStreamableHttp
from session_store import SessionStore

load_dotenv()

# ════════════════════════════════════════════════════════════
#  CONFIG
# ════════════════════════════════════════════════════════════

MCP_ORDER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")
AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-4o-mini")

AGENT_INSTRUCTIONS = """\
คุณคือ ผู้ช่วยขาย ผงเครื่องเทศหอมรักกัน

คุณช่วยผู้ใช้เรื่อง:
- ตอบคำถามเกี่ยวกับสินค้า ผงเครื่องเทศหอมรักกัน และ ผงสามเกลอ
- แนะนำสูตรทำน้ำซุป (น้ำข้น, น้ำใส) พร้อมวัตถุดิบ
- แจ้งราคาและโปรโมชั่น (ขนาด 15g, 30g)
- แสดงรีวิวจากลูกค้า
- แจ้งช่องทางการซื้อ (Facebook, TikTok, Shopee, Lazada)
- แสดงใบรับรอง (อย., ฮาลาล, เจ)
- สร้างคำสั่งซื้อเมื่อลูกค้ายืนยัน
- จดจำข้อมูลลูกค้าด้วย memory tools

กฎ:
- ตอบกลับภาษาเดียวกับที่ผู้ใช้พิมพ์มา
- ใช้ knowledge_search เพื่อดึงข้อมูลจริงเสมอ ห้ามเดาหรือแต่งข้อมูล
- เมื่อผลลัพธ์จาก knowledge_search มี image_ids ให้แนบรูปภาพโดยใส่ marker <<IMG:IMAGE_ID>> ในข้อความ
  ตัวอย่าง: ถ้า image_ids = ["IMG_PROD_001", "IMG_REVIEW_001"] ให้ใส่ <<IMG:IMG_PROD_001>> <<IMG:IMG_REVIEW_001>> ท้ายข้อความ
- แนบรูปเฉพาะที่เกี่ยวข้องกับคำถาม อย่าแนบทุกรูป ส่งรูปไม่เกิน 3 รูปต่อข้อความ
- เมื่อผู้ใช้ถามเกี่ยวกับสินค้า ให้ใช้:
  • knowledge_search — ค้นหาข้อมูลสินค้า สูตร ราคา รีวิว ฯลฯ
    รองรับ category filter: product_overview, product_features, certifications,
    recipe, recipe_ingredients, pricing, sales_channels, how_to_use,
    customer_reviews, product_variant
  • list_product — ตรวจสอบสต็อก/ราคาล่าสุดจากระบบ, สร้าง order
- สร้าง/ดู/ลบ order draft และแนบการชำระเงิน
- ตรวจสอบสถานะการจัดส่ง
- ดูรายงานยอดขาย
- ตรวจสอบที่อยู่
- จดจำข้อมูลสำคัญของผู้ใช้ด้วย memory tools:
  • memory_add — บันทึกข้อมูลสำคัญ (ชื่อ, ที่อยู่, จำนวนสั่งซื้อ, สูตรที่สนใจ)
  • memory_search — ค้นหาสิ่งที่เคยจำไว้ก่อนตอบ
  • memory_get_all — ดูข้อมูลทั้งหมดของผู้ใช้
  • memory_delete — ลบข้อมูลที่ผู้ใช้ขอให้ลืม
- เมื่อผู้ใช้บอกข้อมูลสำคัญ ให้ memory_add ทันที
- ทุก memory tool ต้องส่ง user_id เสมอ

รูปแบบการตอบ:
- ห้ามใช้ตาราง markdown (| --- |) เด็ดขาด เพราะแสดงผลไม่สวยบน Messenger
- ใช้รายการแบบเลขลำดับ (1. 2. 3.) หรือขีดหัวข้อ (•) แทน
- ข้อความกระชับ อ่านง่ายบนมือถือ
- marker <<IMG:...>> ให้ใส่ท้ายข้อความเท่านั้น ห้ามใส่กลางประโยค
"""

# ════════════════════════════════════════════════════════════
#  IMAGE MARKER PARSING
# ════════════════════════════════════════════════════════════

IMG_MARKER_PATTERN = re.compile(r"<<IMG:(IMG_[A-Z]+_\d+)>>")


def parse_image_markers(text: str) -> tuple[str, list[str]]:
    """Extract <<IMG:...>> markers from text, return (clean_text, image_ids).

    Example:
        Input:  "สินค้าครบ 3 แบบ <<IMG:IMG_PROD_001>> <<IMG:IMG_REVIEW_001>>"
        Output: ("สินค้าครบ 3 แบบ", ["IMG_PROD_001", "IMG_REVIEW_001"])
    """
    image_ids = IMG_MARKER_PATTERN.findall(text)
    clean_text = IMG_MARKER_PATTERN.sub("", text).strip()
    # Deduplicate while preserving order
    unique_ids = list(dict.fromkeys(image_ids))
    return clean_text, unique_ids


# ════════════════════════════════════════════════════════════
#  SESSION HISTORY FILTER
# ════════════════════════════════════════════════════════════


def _filter_history_for_storage(items: list) -> list:
    """Filter conversation history to keep only user/assistant text messages.

    Removes tool call items (function_call, function_call_output) to prevent
    orphaned references when history is truncated by SessionStore.
    """
    filtered = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        # Skip tool-related items
        if item_type in ("function_call", "function_call_output"):
            continue
        role = item.get("role")
        # Keep user messages
        if role == "user":
            filtered.append(item)
        # Keep assistant message outputs (Responses API format)
        elif item_type == "message" or role == "assistant":
            filtered.append(item)
    return filtered


# ════════════════════════════════════════════════════════════
#  SESSION STORE (SQLite-backed)
# ════════════════════════════════════════════════════════════

session_store = SessionStore()

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
        params={"url": MCP_ORDER_URL, "timeout": 30},
        client_session_timeout_seconds=30,
        cache_tools_list=True,
    )
    await order_mcp.__aenter__()

    tools = await order_mcp.list_tools()
    print(f"MCP connected — {len(tools)} tools available:")
    for t in tools:
        print(f"  - {t.name}: {t.description[:60] if t.description else ''}")

    agent = Agent(
        name="Raggan Sales Assistant",
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

app = FastAPI(title="Raggan Chat API", lifespan=lifespan)


# ── Request / Response models ────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = Field(default=None, description="Session ID (auto-generated if omitted)")


class ChatResponse(BaseModel):
    session_id: str
    response: str
    image_ids: list[str] = Field(default_factory=list, description="Image IDs to send as attachments")
    memory_count: int


# ── POST /chat ───────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    # Resolve session_id
    session_id = req.session_id or uuid.uuid4().hex[:8]

    # Get conversation history from persistent store
    history = session_store.get(session_id)

    # Build input: history + new user message
    input_messages = history + [{"role": "user", "content": req.message}]

    # Run the agent
    try:
        with trace("Chat API"):
            result = await Runner.run(agent, input=input_messages)
    except BadRequestError as e:
        if "No tool call found" in str(e):
            # Session history corrupted — clear and retry with fresh input
            print(f"Corrupted session {session_id}, clearing and retrying...")
            session_store.delete(session_id)
            try:
                with trace("Chat API (retry)"):
                    result = await Runner.run(
                        agent,
                        input=[{"role": "user", "content": req.message}],
                    )
            except Exception:
                traceback.print_exc()
                return ChatResponse(
                    session_id=session_id,
                    response="ขออภัย ระบบไม่สามารถประมวลผลได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง",
                    image_ids=[],
                    memory_count=0,
                )
        else:
            traceback.print_exc()
            return ChatResponse(
                session_id=session_id,
                response="ขออภัย ระบบไม่สามารถประมวลผลได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง",
                image_ids=[],
                memory_count=len(history),
            )
    except Exception:
        traceback.print_exc()
        return ChatResponse(
            session_id=session_id,
            response="ขออภัย ระบบไม่สามารถประมวลผลได้ในขณะนี้ กรุณาลองใหม่อีกครั้ง",
            image_ids=[],
            memory_count=len(history),
        )

    # Extract response and update session
    try:
        new_history = _filter_history_for_storage(result.to_input_list())
        session_store.save(session_id, new_history)
        raw_reply = result.final_output or "ขออภัย ไม่สามารถสร้างคำตอบได้ กรุณาลองใหม่"
    except Exception:
        traceback.print_exc()
        raw_reply = "ขออภัย เกิดข้อผิดพลาดในการประมวลผลคำตอบ"

    # Parse image markers from agent response
    clean_reply, image_ids = parse_image_markers(raw_reply)

    return ChatResponse(
        session_id=session_id,
        response=clean_reply,
        image_ids=image_ids,
        memory_count=session_store.count(session_id),
    )


# ════════════════════════════════════════════════════════════
#  RUN
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("agent_api:app", host="0.0.0.0", port=3000, reload=True)
