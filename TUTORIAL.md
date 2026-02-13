# GoSaaS AI Messenger Bot — Tutorial

คู่มือการติดตั้งและใช้งานระบบ AI Chatbot ที่เชื่อมต่อกับ GoSaaS Order Management รองรับทั้ง CLI, TUI และ Facebook Messenger

## สารบัญ

1. [ภาพรวมระบบ](#1-ภาพรวมระบบ)
2. [สิ่งที่ต้องเตรียม](#2-สิ่งที่ต้องเตรียม)
3. [ติดตั้งและตั้งค่า](#3-ติดตั้งและตั้งค่า)
4. [รันระบบ](#4-รันระบบ)
5. [ใช้งาน CLI / TUI / API](#5-ใช้งาน-cli--tui--api)
6. [ทดสอบ MCP Server ด้วย Inspector](#6-ทดสอบ-mcp-server-ด้วย-inspector)
7. [ตั้งค่า Facebook Messenger](#7-ตั้งค่า-facebook-messenger)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. ภาพรวมระบบ

```
                      ┌─────────────────┐
                      │  Facebook       │
                      │  Messenger      │
                      └────────┬────────┘
                               ↓ POST event
┌─────────────────────────────────────────────┐
│  Webhook (port 8001)                        │
│  - ตรวจ signature จาก Facebook              │
│  - แยก sender_id และข้อความ                 │
│  - forward ไป Agent API                     │
└─────────────────────┬───────────────────────┘
                      ↓ POST /chat
┌─────────────────────────────────────────────┐
│  Agent API (port 3000)                      │    CLI / TUI Agent
│  - เก็บประวัติสนทนาใน SQLite (sessions.db)  │    (run_agents.py)
│  - ใช้ OpenAI Agents SDK ประมวลผล           │        │
│  - เรียก tools ผ่าน MCP protocol            │        │
│  - Short-Term Memory (ประวัติ chat)         │        │
│  - Long-Term Memory (mem0 + Qdrant)         │        │
└─────────────────────┬───────────────────────┘        │
                      ↓ MCP (Streamable HTTP)          ↓
┌─────────────────────────────────────────────┐
│  MCP Server (port 8000)                     │
│  - 21 tools (ออเดอร์, สินค้า, memory ฯลฯ)   │
│  - เรียก GoSaaS API จริง                    │
│  - Long-Term Memory (mem0 + Qdrant)         │
└─────────────────────────────────────────────┘
```

### Services

| Service | Port | ไฟล์ | หน้าที่ |
|---------|------|------|---------|
| **MCP Server** | 8000 | `mcp-server/server.py` | เปิด tools 21 ตัวให้ Agent เรียกใช้ผ่าน MCP protocol |
| **Agent API** | 3000 | `agent/agent_api.py` | AI Agent ประมวลผลข้อความและตัดสินใจเรียก tools |
| **Webhook** | 8001 | `webhook/main.py` | รับ/ส่งข้อความกับ Facebook Messenger |
| **CLI Agent** | — | `agent/run_agents.py` | Interactive CLI สำหรับทดสอบใน terminal |
| **TUI Agent** | — | `agent/run_agents.py --tui` | Terminal UI พร้อม tabs (chat, traces, memory, sessions) |
| **Vector Search** | — | `agent/vector_search.py` | REPL สำหรับเก็บและค้นหาเอกสารด้วย semantic search |

### Tools ที่ Agent ใช้ได้ (21 tools)

| หมวด | Tools |
|------|-------|
| **Order Draft** | `create_order_draft`, `get_order_draft`, `delete_order_draft`, `get_order_draft_meta`, `attach_order_draft_payment` |
| **Product** | `list_product`, `get_product` |
| **Shipment** | `get_shipping_status`, `get_shipment` |
| **Report** | `get_sales_summary`, `get_sales_summary_today`, `get_sales_filter` |
| **Order** | `get_order_meta` |
| **Utilities** | `verify_address`, `faq`, `intent_classify` |
| **Hybrid Search** | `hybrid_search` |
| **Memory** | `memory_add`, `memory_search`, `memory_get_all`, `memory_delete` |

---

## 2. สิ่งที่ต้องเตรียม

- **Python 3.10+**
- **OpenAI API Key** — สำหรับ AI Agent (GPT-4o-mini)
- **GoSaaS UAT API Key** — สำหรับเรียก API จัดการออเดอร์
- **Node.js >= 18** (optional) — สำหรับ MCP Inspector
- **Facebook Developer Account + Page** (สำหรับ Messenger bot เท่านั้น)
- **ngrok** (สำหรับ dev Messenger) — เปิด HTTPS tunnel ให้ Facebook เข้าถึง localhost

---

## 3. ติดตั้งและตั้งค่า

### 3.1 ติดตั้ง Dependencies

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
pip install -r webhook/requirements.txt   # สำหรับ Messenger bot
```

### 3.2 ตั้งค่า `.env` (root — MCP Server + Agent)

```env
OPENAI_API_KEY=sk-proj-xxxx...
UAT_API_KEY=sk_xxxx...
UAT_API_URL=https://oapi.uatgosaasapi.co/api/v1
```

ตัวแปร optional:

| ตัวแปร | Default | คำอธิบาย |
|--------|---------|----------|
| `MCP_SERVER_URL` | `http://localhost:8000/mcp` | URL ของ MCP Server |
| `AGENT_MODEL` | `gpt-4o-mini` | โมเดล LLM ที่ Agent ใช้ |
| `MAX_HISTORY_MESSAGES` | `50` | จำนวน messages สูงสุดต่อ session |
| `SESSION_TTL_HOURS` | `24` | อายุ session (ชั่วโมง) |

### 3.3 ตั้งค่า `webhook/.env` (สำหรับ Messenger เท่านั้น)

```bash
cd webhook && cp .env.example .env
```

```env
FB_VERIFY_TOKEN=MIi6G9fln_1jRtnKMAdZ7Vkmke7BGBra
FB_APP_SECRET=your_app_secret_here
FB_PAGE_ACCESS_TOKEN=EAAxxxxxxx...
AI_AGENT_URL=http://localhost:3000/chat
```

---

## 4. รันระบบ

### โหมด CLI (2 terminals) — ทดสอบเร็วที่สุด

```bash
# Terminal 1 — MCP Server (เปิดก่อนเสมอ)
python mcp-server/server.py
# รอจนเห็น: Starting MCP server on http://localhost:8000/mcp

# Terminal 2 — CLI Agent
python agent/run_agents.py
```

### โหมด TUI (2 terminals) — มี UI + tabs

```bash
# Terminal 1 — MCP Server
python mcp-server/server.py

# Terminal 2 — TUI Agent
python agent/run_agents.py --tui
```

### โหมด Messenger (3 terminals + ngrok)

```bash
# Terminal 1 — MCP Server
python mcp-server/server.py

# Terminal 2 — Agent API
python agent/agent_api.py
# รอจนเห็น: Agent ready — model: gpt-4o-mini

# Terminal 3 — Webhook
python webhook/main.py
# รอจนเห็น: Uvicorn running on http://0.0.0.0:8001

# Terminal 4 — ngrok tunnel (สำหรับ dev)
ngrok http 8001
```

### สรุป Ports

```
http://localhost:8000  →  MCP Server (tools)
http://localhost:3000  →  Agent API (สำหรับ webhook/frontend)
http://localhost:8001  →  Webhook (Facebook Messenger)
```

---

## 5. ใช้งาน CLI / TUI / API

### 5.1 CLI Agent

| คำสั่ง | ผลลัพธ์ |
|--------|---------|
| พิมพ์ข้อความ + Enter | ส่งข้อความให้ Agent |
| `clear` | ล้างประวัติสนทนา |
| `quit` / `exit` / `q` | ออกจากโปรแกรม |

ตัวอย่าง:

```
You: ค้นหาสินค้า iPhone
You: ยอดขายวันนี้
You: ติดตามพัสดุ TH12345678
You: สร้างออเดอร์ สินค้า id 5 จำนวน 2 ชิ้น ส่งให้ คุณสมชาย 0812345678
      123 ถ.สุขุมวิท แขวงคลองตัน เขตคลองเตย กรุงเทพ 10110
```

### 5.2 TUI Agent

TUI แบ่งเป็น 2 ส่วน — **ซ้าย (55%)** Chat panel, **ขวา (45%)** Tabbed panel:

| Tab | คำอธิบาย |
|-----|----------|
| **Replies** | คำตอบล่าสุดจาก Agent แบบ streaming |
| **Traces** | trace ของ Agent (tool calls, LLM generations) |
| **STM** | Short-Term Memory — ประวัติสนทนาใน session ปัจจุบัน |
| **LTM** | Long-Term Memory — ข้อมูลที่จดจำของผู้ใช้ (ใส่ user_id → กด Refresh) |
| **Session** | จัดการ sessions — ดู/สลับ sessions |

Keybindings: `Enter` = ส่งข้อความ, `Ctrl+Q` = ออก, `Tab` = สลับ elements

### 5.3 Agent API (HTTP)

```bash
# ส่งข้อความ (สร้าง session ใหม่อัตโนมัติ)
curl -X POST http://localhost:3000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"สวัสดี\"}"

# คุยต่อเนื่อง (ส่ง session_id เดิม)
curl -X POST http://localhost:3000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"ค้นหาสินค้า\", \"session_id\": \"a1b2c3d4\"}"
```

Response:

```json
{
  "session_id": "a1b2c3d4",
  "response": "สวัสดีครับ! ยินดีให้บริการ...",
  "memory_count": 2
}
```

### 5.4 Vector Search REPL

```bash
python agent/vector_search.py
```

| คำสั่ง | ตัวอย่าง |
|--------|----------|
| `add <text>` | `add Machine learning is a subset of AI` |
| `load <filepath>` | `load phone_products.txt` |
| `search <query>` | `search มือถือจอใหญ่` |
| `search <query> /N` | `search AI /3` |
| `search <query> --flag` | `search iPhone --min-price 20000 --color ดำ` |
| `list` | แสดงเอกสารทั้งหมด |
| `count` | จำนวนเอกสาร |

Metadata filters: `--min-price`, `--max-price`, `--color`, `--model`, `--min-screen`, `--max-screen`, `--min-stock`

---

## 6. ทดสอบ MCP Server ด้วย Inspector

[MCP Inspector](https://github.com/modelcontextprotocol/inspector) เป็น Web UI สำหรับทดสอบและ debug MCP Server โดยไม่ต้องเขียน client code

### วิธีใช้

**1. เริ่ม MCP Server** (Terminal 1):

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

1. คลิกแท็บ **Tools** > **List Tools** → เห็น tools ทั้ง 21 ตัว
2. เลือก tool ที่ต้องการทดสอบ
3. กรอก parameter > กด **Run Tool**

### ตัวอย่าง

| Tool | Parameter | ค่า |
|------|-----------|-----|
| `verify_address` | name | `สมชาย ใจดี` |
| | tel | `0812345678` |
| | province | `กรุงเทพมหานคร` |
| | postal_code | `10110` |
| `list_product` | find | `เสื้อ` |
| `get_sales_summary_today` | *(ไม่มี)* | — |
| `memory_search` | query | `ยี่ห้อที่ชอบ` |
| | user_id | `test-user` |

เปลี่ยน port (ถ้าชนกัน):

```bash
CLIENT_PORT=8080 SERVER_PORT=9000 npx @modelcontextprotocol/inspector
```

---

## 7. ตั้งค่า Facebook Messenger

> ส่วนนี้จำเป็นเฉพาะเมื่อต้องการใช้งานผ่าน Facebook Messenger

### 7.1 สร้าง Facebook App

1. ไปที่ https://developers.facebook.com/apps → **สร้างแอพ**
2. เลือก **อื่นๆ** → **ธุรกิจ** → ตั้งชื่อ → **สร้างแอพ**
3. เมนูซ้าย → **กรณีการใช้งาน** → **ตอบกลับข้อความ** → **ปรับแต่ง**

### 7.2 หา Credentials

- **App Secret**: การตั้งค่าแอพ → ข้อมูลพื้นฐาน → ข้อมูลลับของแอพ → ใส่ `FB_APP_SECRET`
- **Page Token**: การตั้งค่า Messenger API → สร้างโทเค็นการเข้าถึง → เชื่อมต่อ Page → สร้างโทเค็น → ใส่ `FB_PAGE_ACCESS_TOKEN`

### 7.3 ลงทะเบียน Webhook

1. เปิด ngrok: `ngrok http 8001` → จด URL (เช่น `https://abcd-1234.ngrok-free.app`)
2. การตั้งค่า Messenger API → กำหนดค่า Webhooks:
   - **Callback URL**: `https://abcd-1234.ngrok-free.app/webhook`
   - **Verify Token**: ค่าเดียวกับ `FB_VERIFY_TOKEN` ใน `webhook/.env`
3. กด **ยืนยันและบันทึก**
4. Subscribe events: **messages** + **messaging_postbacks**

### 7.4 ใส่ Privacy Policy URL

- การตั้งค่าแอพ → ข้อมูลพื้นฐาน → ใส่ URL Privacy Policy + Terms of Service
- ตอน dev ใช้ URL ของ ngrok เช่น `https://abcd-1234.ngrok-free.app/privacy`

> **หมายเหตุ:** Development Mode ใช้ได้เฉพาะ admin/developer/tester ของ App เพิ่ม tester ได้ที่ **บทบาทในแอพ** → เพิ่มผู้คน

---

## 8. Troubleshooting

| ปัญหา | วิธีแก้ |
|-------|---------|
| `Failed to connect to MCP server` | ตรวจว่า `python mcp-server/server.py` รันอยู่ |
| `OPENAI_API_KEY not set` | ตรวจไฟล์ `.env` ว่ามี key ถูกต้อง |
| Tool call ล้มเหลว | ตรวจ `UAT_API_KEY` และ `UAT_API_URL` ใน `.env` |
| Port ถูกใช้งาน | ปิด process อื่นที่ใช้ port 8000/8001/3000 |
| Inspector "Connection Error" | ตรวจว่า MCP Server รันอยู่ + URL `http://localhost:8000/mcp` ถูกต้อง |
| Webhook verify ไม่ผ่าน | ตรวจว่า webhook server + ngrok รันอยู่, `FB_VERIFY_TOKEN` ตรงกัน |
| ส่งข้อความแล้วไม่ตอบ | ตรวจว่าทั้ง 3 services รันอยู่, ตรวจ `FB_PAGE_ACCESS_TOKEN` + `AI_AGENT_URL` |
| Signature verification failed | ตรวจ `FB_APP_SECRET`, ทดสอบ local ให้เคลียร์ค่าชั่วคราว |
| Bot ตอบช้า | ปกติ 5-15 วินาที (OpenAI + GoSaaS API), Facebook timeout 20 วินาที |

### ดู Log

```bash
# Windows PowerShell
Get-Content webhook/logs/webhook.log -Wait

# Linux/macOS
tail -f webhook/logs/webhook.log
```

---

## โครงสร้างโปรเจค

```
AI-Workshop/
├── .env                          # API keys (OpenAI, GoSaaS)
├── requirements.txt              # Python dependencies
├── mcp-server/                   # MCP Server — port 8000
│   ├── server.py                 # FastMCP server + tool registration (21 tools)
│   ├── config.py                 # OpenAI client + mem0 memory + API helpers
│   ├── models.py                 # Pydantic models
│   └── tools/                    # 8 modules, 21 tools
│       ├── order_draft.py        # 5 tools: สร้าง/ดู/ลบ draft, แนบชำระเงิน
│       ├── product.py            # 2 tools: ค้นหา/ดูสินค้า
│       ├── shipment.py           # 2 tools: ติดตามพัสดุ
│       ├── report.py             # 3 tools: ยอดขาย
│       ├── order.py              # 1 tool: order metadata
│       ├── utilities.py          # 3 tools: ตรวจที่อยู่/FAQ/intent
│       ├── hybrid_search.py      # 1 tool: semantic + substring + LLM search
│       └── memory.py             # 4 tools: long-term memory (mem0 + Qdrant)
├── agent/                        # AI Agent
│   ├── run_agents.py             # CLI/TUI (--tui flag)
│   ├── agent_api.py              # HTTP API — port 3000
│   ├── session_store.py          # SQLite session management
│   ├── vector_search.py          # Semantic search REPL
│   └── tui/                      # Textual TUI interface
│       ├── app.py                # TUI application
│       ├── trace_processor.py    # Trace → Textual events
│       └── styles.tcss           # TUI styles
└── webhook/                      # Facebook Webhook — port 8001
    ├── main.py                   # FastAPI webhook server
    ├── .env                      # Facebook credentials
    └── static/                   # Privacy Policy + Terms
```
