# GoSaaS Order Management Agent — Tutorial

## สรุปภาพรวมระบบ

ระบบประกอบด้วย 2 ส่วนหลัก:

```
agent/                                                  mcp-server/
┌─────────────────────┐     MCP (Streamable HTTP)     ┌─────────────────────┐
│   run_agents.py     │ ────────────────────────────▶ │    server.py        │
│   (OpenAI Agents)   │ ◀──────────────────────────── │    (MCP Server)     │
└─────────┬───────────┘                                └──────────┬──────────┘
          │ Streaming                                             │ HTTP API
          ▼                                                       ▼
     CLI Input/Output                                   GoSaaS OPEN-API (UAT)
```

```
├── agent/
│   └── run_agents.py          # Agent CLI — OpenAI Agents SDK
├── mcp-server/
│   ├── server.py              # MCP Server — entry point
│   ├── config.py              # Shared config, API helpers, OpenAI client
│   ├── models.py              # Pydantic models (AddressVerificationResult)
│   └── tools/
│       ├── __init__.py
│       ├── order_draft.py     # Order draft CRUD + payment
│       ├── product.py         # Product list / get
│       ├── shipment.py        # Shipping status / shipment details
│       ├── report.py          # Sales summary / filters
│       ├── order.py           # Order metadata (WIP)
│       └── utilities.py       # verify_address, faq, intent_classify
├── .env                       # API keys (OpenAI, GoSaaS UAT)
└── requirements.txt           # Dependencies
```

| ไฟล์ | หน้าที่ |
|------|---------|
| `mcp-server/server.py` | MCP Server — เปิด 16 tools ผ่านโปรโตคอล MCP |
| `mcp-server/config.py` | Shared config — API helpers, HTTP client, OpenAI client |
| `mcp-server/models.py` | Pydantic models ที่ใช้ร่วมกันระหว่าง tools |
| `mcp-server/tools/` | Tool modules แยกตามหมวดหมู่ (order, product, shipment, report, utilities) |
| `agent/run_agents.py` | Agent CLI — เชื่อมต่อ MCP, สร้าง Agent, รับ input, streaming + tracing |
| `.env` | API keys (OpenAI, GoSaaS UAT) |
| `requirements.txt` | Dependencies |

---

## 1. ติดตั้ง Dependencies

```bash
# สร้าง virtual environment (แนะนำ)
python -m venv venv

# เปิดใช้งาน
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# ติดตั้ง dependencies
pip install -r requirements.txt
```

หรือใช้ `uv` (เร็วกว่า):

```bash
uv pip install -r requirements.txt
```

| แพ็กเกจ | ใช้ทำอะไร |
|---------|----------|
| `openai-agents` | OpenAI Agents SDK — Agent, Runner, Tracing |
| `mcp[cli]` | Model Context Protocol — MCP Server |
| `openai` | OpenAI API (FAQ/Intent ใน utilities.py) |
| `httpx` | HTTP client เรียก GoSaaS API |
| `pydantic` | Data validation |
| `python-dotenv` | โหลด `.env` |

---

## 2. ตั้งค่า Environment Variables

สร้างไฟล์ `.env`:

```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx
UAT_API_KEY=sk_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
UAT_API_URL=https://oapi.uatgosaasapi.co/api/v1
```

ตัวแปร optional:

| ตัวแปร | Default | คำอธิบาย |
|--------|---------|----------|
| `MCP_SERVER_URL` | `http://localhost:8000/mcp` | URL ของ MCP Server |
| `AGENT_MODEL` | `gpt-4o-mini` | โมเดล LLM ที่ Agent ใช้ |

---

## 3. วิธีรัน (ต้องเปิด 2 Terminal)

### Terminal 1 — MCP Server

```bash
python mcp-server/server.py
```

Server จะเริ่มที่ `http://localhost:8000/mcp` (transport: `streamable-http`)

### Terminal 2 — Agent CLI

```bash
python agent/run_agents.py
```

---

## 4. คำสั่งใน CLI

| คำสั่ง | ผลลัพธ์ |
|--------|---------|
| พิมพ์ข้อความ + Enter | ส่งข้อความให้ Agent |
| `clear` | ล้างประวัติสนทนา |
| `quit` / `exit` / `q` | ออกจากโปรแกรม |
| `Ctrl+C` | บังคับออก |

---

## 5. ตัวอย่างการใช้งาน

### ค้นหาสินค้า

```
You: แสดงรายการสินค้าทั้งหมด
Assistant: รายการสินค้าที่มี: 1. สินค้า A  2. สินค้า B ...
```

### ดูยอดขายวันนี้

```
You: ยอดขายวันนี้เท่าไหร่
Assistant: ยอดขายวันนี้ทั้งหมด 15,230 บาท จาก 12 ออเดอร์
```

### ตรวจสอบสถานะจัดส่ง

```
You: เช็คพัสดุ tracking TH12345678
Assistant: พัสดุ TH12345678 สถานะ: กำลังจัดส่ง ...
```

### สร้าง Order Draft

```
You: สร้างออเดอร์ให้ คุณสมชาย 0812345678 ที่อยู่ 123 ถ.สุขุมวิท
     แขวงคลองตัน เขตคลองเตย กรุงเทพ 10110 สินค้า id 5 จำนวน 2 ชิ้น
Assistant: (Agent จะเรียก verify_address, get_order_draft_meta, แล้วจึง create_order_draft)
```

---

## 6. ระบบ Tracing — อ่าน Output

Tracing แสดงใน terminal (stderr) แบบ real-time พร้อมสี:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TRACE START > Conversation Turn
  ID: trace_abc123def456
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  > AGENT: GoSaaS Assistant  [tools: list_product, get_product, ...]
  > LLM GENERATION  [model: gpt-4o-mini]
  < LLM DONE  [model: gpt-4o-mini, 0.82s  tokens: 1200 in / 45 out]
  > TOOL CALL: list_product
    input: {"find": ""}
  < TOOL DONE: list_product  [0.34s]
    output: {"data": [{"id": 1, "name": "..."}, ...]}
  > LLM GENERATION  [model: gpt-4o-mini]
  < LLM DONE  [model: gpt-4o-mini, 1.05s  tokens: 2100 in / 120 out]
  < AGENT DONE: GoSaaS Assistant  [2.21s]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TRACE END > Conversation Turn
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### ความหมายของแต่ละ Span

| สี | Span | ความหมาย |
|----|------|----------|
| เหลือง | `AGENT` | Agent loop เริ่ม/จบทำงาน + แสดง tools ที่มี |
| เขียว | `TOOL CALL / TOOL DONE` | เรียก MCP tool + แสดง input/output |
| ม่วง | `LLM GENERATION / LLM DONE` | LLM คิดคำตอบ + แสดงโมเดล, เวลา, tokens |
| น้ำเงิน | `MCP LIST TOOLS` | โหลดรายการ tools จาก MCP Server |
| แดง | `HANDOFF` | ส่งต่อไปยัง Agent อื่น (ถ้ามี multi-agent) |
| เหลืองเข้ม | `GUARDRAIL` | ตรวจสอบ guardrail (ถ้าตั้งค่าไว้) |

---

## 7. Tools ทั้ง 16 ตัว (จาก mcp-server/tools/)

### Order Draft

| Tool | คำอธิบาย |
|------|----------|
| `create_order_draft` | สร้างคำสั่งซื้อฉบับร่าง |
| `get_order_draft_meta` | ดึง meta data (channels, carriers, payments) |
| `get_order_draft` | ดึง order draft ตาม ID |
| `delete_order_draft` | ลบ order draft |
| `attach_order_draft_payment` | แนบข้อมูลการชำระเงิน |

### Product

| Tool | คำอธิบาย |
|------|----------|
| `list_product` | ค้นหา/แสดงรายการสินค้า |
| `get_product` | ดึงสินค้าตาม ID |

### Shipment

| Tool | คำอธิบาย |
|------|----------|
| `get_shipping_status` | ตรวจสอบสถานะจัดส่ง |
| `get_shipment` | ดึงข้อมูล shipment ตาม order_draft_id |

### Report

| Tool | คำอธิบาย |
|------|----------|
| `get_sales_summary` | รายงานยอดขายตามช่วงเวลา |
| `get_sales_summary_today` | ยอดขายวันนี้ |
| `get_sales_filter` | ตัวกรองรายงาน |

### Order (WIP)

| Tool | คำอธิบาย |
|------|----------|
| `get_order_meta` | metadata สำหรับสร้าง order |

### Utilities

| Tool | คำอธิบาย |
|------|----------|
| `verify_address` | ตรวจสอบที่อยู่ครบถ้วน |
| `faq` | ตอบคำถามที่พบบ่อย (AI) |
| `intent_classify` | จัดประเภท intent ข้อความ |

---

## 8. ทดสอบ MCP Server ด้วย MCP Inspector

[MCP Inspector](https://github.com/modelcontextprotocol/inspector) เป็น Web UI สำหรับทดสอบและ debug MCP Server โดยไม่ต้องเขียน client code

### Prerequisites

- **Node.js** >= 18 (แนะนำ 22.x)
- ไม่ต้องติดตั้งแยก — ใช้ `npx` รันได้เลย

### วิธีใช้

**1. เริ่ม server ก่อน** (Terminal 1):

```bash
python mcp-server/server.py
```

**2. เปิด Inspector** (Terminal 2):

```bash
npx @modelcontextprotocol/inspector
```

Inspector จะเปิด Web UI ที่ **http://localhost:6274**

**3. เชื่อมต่อ:**

1. เปลี่ยน **Transport Type** เป็น `Streamable HTTP`
2. ใส่ URL: `http://localhost:8000/mcp`
3. กด **Connect**

**4. ทดสอบ Tools:**

1. คลิกแท็บ **Tools** > **List Tools**
2. เลือก tool ที่ต้องการทดสอบ
3. กรอก parameter > กด **Run Tool**

### ตัวอย่างการทดสอบ

**ทดสอบ `verify_address`:**

| Field | ตัวอย่างค่า |
|-------|------------|
| name | `สมชาย ใจดี` |
| tel | `0812345678` |
| province | `กรุงเทพมหานคร` |
| postal_code | `10110` |

**ทดสอบ `list_product`:**

| Field | ตัวอย่างค่า |
|-------|------------|
| find | `เสื้อ` |

### เปลี่ยน Port (ถ้า port ชนกัน)

```bash
CLIENT_PORT=8080 SERVER_PORT=9000 npx @modelcontextprotocol/inspector
```

---

## 9. โครงสร้างโค้ด agent/run_agents.py

```
agent/run_agents.py
├── ConsoleTraceProcessor     # Custom trace processor แสดง trace ใน terminal
│   ├── on_trace_start()      # เริ่ม trace
│   ├── on_trace_end()        # จบ trace
│   ├── on_span_start()       # เริ่ม span (agent/tool/llm/mcp/...)
│   └── on_span_end()         # จบ span + แสดงเวลา
│
├── Agent Configuration       # ตั้งค่า Agent
│   ├── MCP_SERVER_URL        # URL ของ MCP Server
│   ├── AGENT_MODEL           # โมเดล LLM
│   └── AGENT_INSTRUCTIONS    # System prompt ของ Agent
│
├── chat_loop()               # Interactive loop
│   ├── input()               # รับ input จากผู้ใช้
│   ├── Runner.run_streamed() # รัน Agent แบบ streaming
│   ├── stream_events()       # รับ events แบบ real-time
│   └── to_input_list()       # เก็บประวัติสนทนา
│
└── main()                    # Entry point
    ├── set_trace_processors  # ติดตั้ง ConsoleTraceProcessor
    ├── MCPServerStreamableHttp  # เชื่อมต่อ MCP Server
    ├── Agent()               # สร้าง Agent + เชื่อม MCP
    └── chat_loop()           # เริ่ม interactive loop
```

---

## 10. Concepts สำคัญ

### Agent Loop (วงจรการทำงานของ Agent)

```
ผู้ใช้พิมพ์ข้อความ
       │
       ▼
   ┌─────────┐
   │   LLM   │ ◀──── Agent Instructions + Conversation History
   └────┬────┘
        │
        ├── ถ้าเป็นข้อความตอบ → แสดงผลแบบ streaming → จบ
        │
        └── ถ้าเป็น tool call → เรียก MCP Tool
                                      │
                                      ▼
                               ┌─────────────┐
                               │  MCP Server  │ → เรียก GoSaaS API
                               └──────┬──────┘
                                      │
                                      ▼
                               ส่งผลลัพธ์กลับ LLM → วนลูปใหม่
```

Agent จะวนลูปจนกว่าจะได้คำตอบสุดท้ายที่เป็นข้อความ (ไม่ใช่ tool call)

### Conversation History

ระบบเก็บประวัติสนทนาไว้ใน `history` list โดยใช้ `result.to_input_list()` เพื่อแปลงผลลัพธ์ (รวม tool calls และ tool results) กลับเป็น input สำหรับรอบถัดไป ทำให้ Agent จำบริบทได้ตลอดการสนทนา

พิมพ์ `clear` เพื่อล้างประวัติและเริ่มสนทนาใหม่

### Streaming

ใช้ `Runner.run_streamed()` แทน `Runner.run()` เพื่อให้ข้อความแสดงทีละตัวอักษร (token-by-token) ไม่ต้องรอจนตอบเสร็จทั้งหมด

### MCP (Model Context Protocol)

Agent ไม่ได้เรียก GoSaaS API โดยตรง แต่เรียกผ่าน MCP Server (`mcp-server/server.py`) ซึ่งทำหน้าที่เป็นตัวกลาง ข้อดีคือ:
- แยก business logic (API calls) ออกจาก Agent logic
- Tools ถูก define ครั้งเดียวใน mcp-server/tools/ แล้ว Agent เห็นอัตโนมัติ
- สามารถใช้ MCP Server เดียวกันกับ Agent หลายตัวได้

---

## 11. Troubleshooting

| ปัญหา | วิธีแก้ |
|-------|---------|
| `Failed to connect to MCP server` | ตรวจสอบว่า `python mcp-server/server.py` รันอยู่ |
| `OPENAI_API_KEY not set` | ตรวจสอบไฟล์ `.env` ว่ามี key ถูกต้อง |
| Agent ตอบช้า | เปลี่ยน `AGENT_MODEL` เป็น `gpt-4o-mini` |
| Tool call ล้มเหลว | ตรวจสอบ `UAT_API_KEY` และ `UAT_API_URL` ใน `.env` |
| สีไม่แสดงใน terminal | ใช้ terminal ที่รองรับ ANSI colors (Windows Terminal, VS Code) |
| Inspector ขึ้น "Connection Error" | ตรวจสอบว่า mcp-server/server.py รันอยู่ และ URL ถูกต้อง |
| Port 6274 / 6277 ถูกใช้งาน | ใช้ `CLIENT_PORT` / `SERVER_PORT` เปลี่ยน port |
| Port 8000 ถูกใช้งาน | ปิด process อื่นที่ใช้ port 8000 |
