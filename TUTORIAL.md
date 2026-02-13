# GoSaaS AI Messenger Bot — Tutorial

คู่มือการติดตั้งและใช้งานระบบ AI Chatbot ที่เชื่อมต่อกับ GoSaaS Order Management รองรับทั้ง CLI และ Facebook Messenger

## สารบัญ

1. [ภาพรวมระบบ](#1-ภาพรวมระบบ)
2. [สถาปัตยกรรม](#2-สถาปัตยกรรม)
3. [สิ่งที่ต้องเตรียม](#3-สิ่งที่ต้องเตรียม)
4. [ติดตั้ง Dependencies](#4-ติดตั้ง-dependencies)
5. [ตั้งค่า Environment Variables](#5-ตั้งค่า-environment-variables)
6. [ตั้งค่า Facebook App บน Meta Developer](#6-ตั้งค่า-facebook-app-บน-meta-developer)
7. [รันระบบทั้งหมด](#7-รันระบบทั้งหมด)
8. [เปิด ngrok และลงทะเบียน Webhook](#8-เปิด-ngrok-และลงทะเบียน-webhook)
9. [ทดสอบระบบ](#9-ทดสอบระบบ)
10. [โครงสร้างโปรเจค](#10-โครงสร้างโปรเจค)
11. [รายละเอียด Components](#11-รายละเอียด-components)
12. [Tools ทั้ง 21 ตัว](#12-tools-ทั้ง-21-ตัว)
13. [CLI Agent — ใช้งานผ่าน Terminal](#13-cli-agent--ใช้งานผ่าน-terminal)
14. [ระบบ Tracing](#14-ระบบ-tracing)
15. [TUI Agent — ใช้งานผ่าน Terminal UI](#15-tui-agent--ใช้งานผ่าน-terminal-ui)
16. [Vector Search REPL — ค้นหาเอกสารด้วย AI](#16-vector-search-repl--ค้นหาเอกสารด้วย-ai)
17. [Concepts สำคัญ](#17-concepts-สำคัญ)
18. [ระบบ Memory — Short-Term vs Long-Term](#18-ระบบ-memory--short-term-vs-long-term)
19. [ทดสอบ MCP Server ด้วย MCP Inspector](#19-ทดสอบ-mcp-server-ด้วย-mcp-inspector)
20. [Logging](#20-logging)
21. [Deploy ขึ้น Production](#21-deploy-ขึ้น-production)
22. [Troubleshooting](#22-troubleshooting)

---

## 1. ภาพรวมระบบ

ระบบประกอบด้วย 3 ส่วนหลักที่ทำงานร่วมกัน ทำให้ลูกค้าสามารถสั่งซื้อสินค้า ติดตามพัสดุ ดูรายงานยอดขาย และอื่นๆ ได้ทั้งผ่าน **Facebook Messenger**, **CLI** และ **TUI**:

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
│  - รับคำตอบแล้วส่งกลับผ่าน Send API         │
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

---

## 2. สถาปัตยกรรม

### Services

| Service | Port | ไฟล์ | หน้าที่ |
|---------|------|------|---------|
| **MCP Server** | 8000 | `mcp-server/server.py` | เปิด tools 21 ตัวให้ Agent เรียกใช้ผ่าน MCP protocol |
| **Webhook** | 8001 | `webhook/main.py` | รับ/ส่งข้อความกับ Facebook Messenger |
| **Agent API** | 3000 | `agent/agent_api.py` | AI Agent ที่ประมวลผลข้อความและตัดสินใจเรียก tools |
| **CLI Agent** | — | `agent/run_agents.py` | Agent แบบ interactive CLI สำหรับทดสอบใน terminal |
| **TUI Agent** | — | `agent/tui/app.py` | Agent แบบ Textual TUI พร้อม tabs สำหรับดู traces, memory, sessions |
| **Vector Search** | — | `agent/vector_search.py` | Interactive REPL สำหรับเก็บและค้นหาเอกสารด้วย semantic search |

### Tools ที่ Agent ใช้ได้ (21 tools)

| หมวด | Tools | ตัวอย่างการใช้ |
|------|-------|---------------|
| **Order Draft** | `create_order_draft`, `get_order_draft`, `delete_order_draft`, `get_order_draft_meta`, `attach_order_draft_payment` | "สร้างออเดอร์สินค้า A 2 ชิ้น ส่งไปที่..." |
| **Product** | `list_product`, `get_product` | "ค้นหาสินค้าชื่อ xxx", "สินค้า ID 123 ราคาเท่าไร" |
| **Shipment** | `get_shipping_status`, `get_shipment` | "ติดตามพัสดุ TH123456", "สถานะออเดอร์ #789" |
| **Report** | `get_sales_summary`, `get_sales_summary_today`, `get_sales_filter` | "ยอดขายวันนี้", "สรุปยอดขายเดือนนี้" |
| **Order** | `get_order_meta` | ดึง metadata สำหรับสร้างออเดอร์ |
| **Utilities** | `verify_address`, `faq`, `intent_classify` | ตรวจที่อยู่, ตอบคำถามทั่วไป, จัดหมวดหมู่ intent |
| **Hybrid Search** | `hybrid_search` | "มือถือจอใหญ่ราคาถูก", ค้นหาสินค้าด้วย semantic + substring พร้อม LLM refinement |
| **Memory** | `memory_add`, `memory_search`, `memory_get_all`, `memory_delete` | "ผมชื่อสมชาย ชอบ Samsung" → จดจำข้ามเซสชัน, "ผมเคยบอกว่าชอบยี่ห้ออะไร?" |

---

## 3. สิ่งที่ต้องเตรียม

- **Python 3.10+**
- **OpenAI API Key** — สำหรับ AI Agent (GPT-4o-mini)
- **GoSaaS UAT API Key** — สำหรับเรียก API จัดการออเดอร์
- **Facebook Developer Account** — https://developers.facebook.com (สำหรับ Messenger bot)
- **Facebook Page** — Page ที่จะผูกกับ Bot
- **ngrok** (สำหรับ dev) — เปิด HTTPS tunnel ให้ Facebook เข้าถึง localhost
- **Node.js >= 18** (optional) — สำหรับ MCP Inspector

---

## 4. ติดตั้ง Dependencies

```bash
# สร้าง virtual environment (แนะนำ)
python -m venv venv

# เปิดใช้งาน
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# ติดตั้ง dependencies ทั้งหมด
pip install -r requirements.txt

# ติดตั้งเพิ่มสำหรับ webhook
pip install -r webhook/requirements.txt
```

หรือติดตั้งด้วย `uv` (เร็วกว่า):

```bash
uv pip install -r requirements.txt
```

| แพ็กเกจ | ใช้ทำอะไร |
|---------|----------|
| `openai-agents` | OpenAI Agents SDK — Agent, Runner, Tracing |
| `mcp[cli]` / `fastmcp` | Model Context Protocol — MCP Server |
| `openai` | OpenAI API (FAQ/Intent ใน utilities.py) |
| `httpx` | HTTP client เรียก GoSaaS API |
| `fastapi` | Web framework สำหรับ Webhook + Agent API |
| `uvicorn` | ASGI server สำหรับ FastAPI |
| `pydantic` | Data validation |
| `python-dotenv` | โหลด `.env` |
| `faiss-cpu` | Facebook AI Similarity Search — vector search engine |
| `prompt_toolkit` | Interactive REPL — autocomplete, history, colored prompt |
| `mem0ai` | Long-term memory — mem0 + Qdrant vector store (จดจำข้อมูลผู้ใช้ข้ามเซสชัน) |
| `textual` | Terminal UI framework — TUI interface พร้อม tabs สำหรับ chat, traces, memory |

---

## 5. ตั้งค่า Environment Variables

### 5.1 ไฟล์ `.env` (root — สำหรับ MCP Server + Agent)

```env
# OpenAI — สำหรับ AI Agent
OPENAI_API_KEY=sk-proj-xxxx...

# GoSaaS UAT API — สำหรับ MCP tools
UAT_API_KEY=sk_xxxx...
UAT_API_URL=https://oapi.uatgosaasapi.co/api/v1
```

ตัวแปร optional:

| ตัวแปร | Default | คำอธิบาย |
|--------|---------|----------|
| `MCP_SERVER_URL` | `http://localhost:8000/mcp` | URL ของ MCP Server |
| `AGENT_MODEL` | `gpt-4o-mini` | โมเดล LLM ที่ Agent ใช้ |
| `MAX_HISTORY_MESSAGES` | `50` | จำนวน messages สูงสุดต่อ session (short-term memory) |
| `SESSION_TTL_HOURS` | `24` | อายุ session เป็นชั่วโมง (หมดอายุแล้วลบอัตโนมัติ) |
| `CLI_SESSION_ID` | `cli` | Session ID สำหรับ CLI/TUI mode |

### 5.2 ไฟล์ `webhook/.env` (สำหรับ Webhook)

```bash
cd webhook
cp .env.example .env
```

แก้ไขค่า:

```env
FB_VERIFY_TOKEN=MIi6G9fln_1jRtnKMAdZ7Vkmke7BGBra
FB_APP_SECRET=your_app_secret_here
FB_PAGE_ACCESS_TOKEN=EAAxxxxxxx...
AI_AGENT_URL=http://localhost:3000/chat
```

| ตัวแปร | คำอธิบาย | หาได้จาก |
|--------|----------|----------|
| `FB_VERIFY_TOKEN` | Token สำหรับ verify webhook (ตั้งเองได้) | สร้างเอง หรือใช้ค่าที่ generate ไว้แล้ว |
| `FB_APP_SECRET` | App Secret ของ Facebook App | Meta Developer → การตั้งค่าแอพ → ข้อมูลพื้นฐาน → ข้อมูลลับของแอพ |
| `FB_PAGE_ACCESS_TOKEN` | Page Token สำหรับส่งข้อความกลับ | Meta Developer → Messenger API → สร้างโทเค็นการเข้าถึง |
| `AI_AGENT_URL` | URL ของ Agent API | `http://localhost:3000/chat` |

---

## 6. ตั้งค่า Facebook App บน Meta Developer

### ขั้นตอนที่ 1: สร้าง Facebook App

1. ไปที่ https://developers.facebook.com/apps
2. กด **สร้างแอพ** (Create App)
3. เลือก **อื่นๆ** (Other) → **ถัดไป**
4. เลือกประเภท **ธุรกิจ** (Business) → **ถัดไป**
5. ตั้งชื่อ App (เช่น "RF AI-Workshop") → กด **สร้างแอพ**

### ขั้นตอนที่ 2: เพิ่ม Messenger Product

1. เมนูซ้าย → **กรณีการใช้งาน** (Use Cases)
2. มองหา **"ตอบกลับข้อความ"** หรือ **Respond to messages**
3. กด **ปรับแต่ง** (Customize)
4. จะเข้าสู่หน้า **การตั้งค่า Messenger API**

### ขั้นตอนที่ 3: หา App Secret

1. เมนูซ้าย → **การตั้งค่าแอพ** → **ข้อมูลพื้นฐาน**
2. หาช่อง **ข้อมูลลับของแอพ** (App Secret) → กด **แสดง**
3. คัดลอกไปใส่ `FB_APP_SECRET` ใน `webhook/.env`

### ขั้นตอนที่ 4: เชื่อมต่อ Facebook Page

1. ในหน้า **การตั้งค่า Messenger API**
2. หัวข้อ **"2. สร้างโทเค็นการเข้าถึง"** → กดปุ่ม **เชื่อมต่อ**
3. เลือก Facebook Page ที่ต้องการ → อนุญาตสิทธิ์ทั้งหมด
4. กลับมาจะเห็น Page ที่เชื่อมแล้ว → กด **สร้างโทเค็น** (Generate Token)
5. คัดลอก token (ขึ้นต้นด้วย `EAA...`) ไปใส่ `FB_PAGE_ACCESS_TOKEN` ใน `webhook/.env`

### ขั้นตอนที่ 5: ใส่ Privacy Policy URL

1. เมนูซ้าย → **การตั้งค่าแอพ** → **ข้อมูลพื้นฐาน**
2. เลื่อนลงหาช่อง **URL นโยบายความเป็นส่วนตัว** → ใส่ `https://YOUR_DOMAIN/privacy`
3. ช่อง **URL ข้อกำหนดในการให้บริการ** → ใส่ `https://YOUR_DOMAIN/terms`
4. กด **บันทึกการเปลี่ยนแปลง**

> ตอน dev ใช้ URL ของ ngrok เช่น `https://abcd-1234.ngrok-free.app/privacy`

### ขั้นตอนที่ 6: ขอสิทธิ์ pages_messaging (ถ้าจำเป็น)

1. ในหน้า **การตั้งค่า Messenger API**
2. หัวข้อ **"3. ตรวจสอบแอพให้เสร็จ"** → กด **ขอสิทธิ์การอนุญาต**
3. ขอสิทธิ์ **pages_messaging** เพื่อให้ bot ส่งข้อความได้

> หมายเหตุ: ระหว่างพัฒนา (Development Mode) สามารถทดสอบได้กับ admin/developer/tester ของ App เท่านั้น ต้อง publish App และผ่าน App Review ถึงจะใช้งานกับผู้ใช้ทั่วไปได้

---

## 7. รันระบบทั้งหมด

### โหมด Messenger (3 terminals)

ต้องเปิด **3 terminals** พร้อมกัน ตามลำดับ:

**Terminal 1 — MCP Server (เปิดก่อน):**

```bash
python mcp-server/server.py
```

รอจนเห็น: `Starting MCP server on http://localhost:8000/mcp`

**Terminal 2 — Agent API:**

```bash
python agent/agent_api.py
```

รอจนเห็น: `Agent ready — model: gpt-4o-mini`

**Terminal 3 — Webhook:**

```bash
python webhook/main.py
```

รอจนเห็น: `Uvicorn running on http://0.0.0.0:8001`

### โหมด CLI (2 terminals)

ถ้าต้องการทดสอบแค่ใน terminal โดยไม่ต้องใช้ Messenger:

**Terminal 1 — MCP Server:**

```bash
python mcp-server/server.py
```

**Terminal 2 — CLI Agent:**

```bash
python agent/run_agents.py
```

### โหมด TUI (2 terminals)

Terminal UI แบบมี tabs สำหรับดู chat, traces, memory, sessions ในหน้าจอเดียว:

**Terminal 1 — MCP Server:**

```bash
python mcp-server/server.py
```

**Terminal 2 — TUI Agent:**

```bash
python agent/run_agents.py --tui
```

### สรุป Ports

```
http://localhost:8000  →  MCP Server (tools)
http://localhost:8001  →  Webhook (Facebook)
http://localhost:3000  →  Agent API (AI)
```

---

## 8. เปิด ngrok และลงทะเบียน Webhook

Facebook ต้องเข้าถึง webhook ผ่าน **HTTPS** ตอน dev ต้องใช้ ngrok

### 8.1 ติดตั้ง ngrok

ดาวน์โหลดจาก https://ngrok.com/download แล้ว sign up เพื่อรับ auth token

```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

### 8.2 เปิด tunnel (Terminal 4)

```bash
ngrok http 8001
```

จะได้ URL ประมาณ:

```
Forwarding  https://abcd-1234.ngrok-free.app → http://localhost:8001
```

จด URL นี้ไว้ (เช่น `https://abcd-1234.ngrok-free.app`)

### 8.3 ลงทะเบียน Webhook กับ Facebook

1. กลับไปที่ **การตั้งค่า Messenger API** ใน Meta Developer
2. หัวข้อ **"1. กำหนดค่า Webhooks"**
3. กรอก:
   - **URL การเรียกกลับ** (Callback URL): `https://abcd-1234.ngrok-free.app/webhook`
   - **ตรวจสอบยืนยันโทเค็น** (Verify Token): ค่าเดียวกับ `FB_VERIFY_TOKEN` ใน `webhook/.env`
4. กด **ยืนยันและบันทึก** (Verify and Save)

ถ้าสำเร็จจะเห็นเครื่องหมายถูกสีเขียว

### 8.4 Subscribe Webhook Fields

หลัง verify สำเร็จ ต้องเลือก events ที่จะรับ:

- **messages** — รับข้อความจากผู้ใช้
- **messaging_postbacks** — รับ postback จากปุ่ม

---

## 9. ทดสอบระบบ

### 9.1 ทดสอบแต่ละส่วนแยก

**ทดสอบ Webhook Verify (ไม่ต้องเปิด Agent):**

```bash
curl "http://localhost:8001/webhook?hub.mode=subscribe&hub.verify_token=MIi6G9fln_1jRtnKMAdZ7Vkmke7BGBra&hub.challenge=12345"
```

ผลลัพธ์: `12345`

**ทดสอบ Agent API ตรง (ต้องเปิด MCP Server + Agent API):**

```bash
curl -X POST http://localhost:3000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"สวัสดี\"}"
```

ผลลัพธ์:

```json
{
  "session_id": "a1b2c3d4",
  "response": "สวัสดีครับ! ยินดีให้บริการ...",
  "memory_count": 2
}
```

**ทดสอบ Agent API แบบมี session_id (คุยต่อเนื่อง):**

```bash
curl -X POST http://localhost:3000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"ค้นหาสินค้าเสื้อยืด\", \"session_id\": \"a1b2c3d4\"}"
```

**ทดสอบ Webhook รับ Event (ต้องเปิดทั้ง 3 services):**

```bash
curl -X POST http://localhost:8001/webhook ^
  -H "Content-Type: application/json" ^
  -d "{\"object\": \"page\", \"entry\": [{\"id\": \"PAGE_ID\", \"time\": 1234567890, \"messaging\": [{\"sender\": {\"id\": \"USER_ID\"}, \"recipient\": {\"id\": \"PAGE_ID\"}, \"timestamp\": 1234567890, \"message\": {\"mid\": \"mid.1234\", \"text\": \"สวัสดี\"}}]}]}"
```

ผลลัพธ์: `EVENT_RECEIVED`

> หมายเหตุ: ทดสอบ local ด้วย curl จะไม่มี X-Hub-Signature-256 header ถ้า `FB_APP_SECRET` มีค่า ให้เคลียร์ค่าชั่วคราวหรือเพิ่ม header ที่ถูกต้อง

### 9.2 ทดสอบจริงผ่าน Messenger

1. ตรวจสอบว่า **ทั้ง 3 services + ngrok** รันอยู่
2. เปิด Facebook Messenger
3. ค้นหาชื่อ Facebook Page ที่ผูกไว้
4. พิมพ์ข้อความ เช่น:
   - `"สวัสดี"` — ทดสอบการทักทาย
   - `"ค้นหาสินค้า"` — ทดสอบ product search
   - `"ยอดขายวันนี้"` — ทดสอบ report
   - `"ติดตามพัสดุ TH123"` — ทดสอบ shipment tracking
5. ดู log ที่ terminal ของ webhook และ agent

> **สำคัญ:** ตอน Development Mode ต้องใช้ Facebook account ที่เป็น admin/developer/tester ของ App เท่านั้น ผู้ใช้อื่นจะส่งข้อความไม่ได้จนกว่า App จะผ่าน review

### 9.3 เพิ่ม Tester

ถ้าต้องการให้คนอื่นทดสอบได้โดยไม่ต้อง publish App:

1. Meta Developer → **บทบาทในแอพ** (App Roles)
2. กด **เพิ่มผู้คน** → ค้นหาชื่อ → เพิ่มเป็น **ผู้ทดสอบ** (Tester)
3. คนที่ถูกเพิ่มต้อง accept invitation ที่ https://developers.facebook.com/requests

---

## 10. โครงสร้างโปรเจค

```
AI-Workshop/
├── .env                          # API keys (OpenAI, GoSaaS)
├── requirements.txt              # Python dependencies (MCP + Agent)
├── TUTORIAL.md                   # ไฟล์นี้
├── phone_products.txt            # ข้อมูลสินค้ามือถือ 100 รายการ (pipe-delimited)
│
├── mcp-server/                   # MCP Server — port 8000
│   ├── server.py                 # FastMCP server + tool registration (21 tools)
│   ├── config.py                 # OpenAI client + mem0 memory config + API helpers
│   ├── models.py                 # Pydantic models (AddressVerificationResult)
│   ├── mem0_data/                # Qdrant vector DB สำหรับ long-term memory (สร้างอัตโนมัติ)
│   │   └── qdrant/
│   └── tools/
│       ├── order_draft.py        # 5 tools: สร้าง/ดู/ลบ draft, แนบชำระเงิน
│       ├── product.py            # 2 tools: ค้นหา/ดูรายละเอียดสินค้า
│       ├── shipment.py           # 2 tools: ติดตามพัสดุ/ดูรายละเอียดจัดส่ง
│       ├── report.py             # 3 tools: สรุปยอดขาย/ยอดวันนี้/ตัวกรอง
│       ├── order.py              # 1 tool:  ดึง order metadata
│       ├── utilities.py          # 3 tools: ตรวจที่อยู่/FAQ/จัดหมวด intent
│       ├── hybrid_search.py      # 1 tool:  ค้นหาสินค้า semantic + substring + LLM refinement
│       └── memory.py             # 4 tools: memory_add/search/get_all/delete (long-term memory)
│
├── agent/                        # AI Agent
│   ├── run_agents.py             # CLI/TUI version (--tui flag สำหรับ TUI mode)
│   ├── agent_api.py              # API version — port 3000 (สำหรับ webhook/frontend)
│   ├── session_store.py          # SQLite session management (short-term memory)
│   ├── vector_search.py          # Semantic search REPL (OpenAI Embeddings + FAISS + SQLite)
│   ├── sessions.db               # SQLite DB — ประวัติสนทนา (สร้างอัตโนมัติ)
│   ├── vector_store.db           # SQLite DB — product embeddings (สร้างอัตโนมัติ)
│   └── tui/                      # Textual TUI interface
│       ├── __init__.py
│       ├── app.py                # TUI application (chat, replies, traces, STM, LTM, sessions)
│       ├── trace_processor.py    # TUI trace processor (bridges SDK traces → Textual events)
│       └── styles.tcss           # TUI CSS styles
│
└── webhook/                      # Facebook Webhook — port 8001
    ├── main.py                   # FastAPI webhook server
    ├── requirements.txt          # Python dependencies (webhook)
    ├── .env                      # Facebook credentials
    ├── .env.example              # ตัวอย่าง env
    ├── logs/
    │   └── webhook.log           # Log file (สร้างอัตโนมัติ)
    └── static/
        ├── privacy.html          # Privacy Policy สำหรับ App Review
        └── terms.html            # Terms of Service สำหรับ App Review
```

---

## 11. รายละเอียด Components

### 11.1 Webhook (`webhook/main.py`)

| Endpoint | Method | คำอธิบาย |
|----------|--------|----------|
| `/webhook` | GET | Facebook verification — ตรวจ `hub.verify_token` แล้ว return `hub.challenge` |
| `/webhook` | POST | รับ events จาก Facebook → ตรวจ signature → forward ไป Agent → ส่งคำตอบกลับ |
| `/privacy` | GET | หน้า Privacy Policy (HTML) |
| `/terms` | GET | หน้า Terms of Service (HTML) |

**POST /webhook ทำงานอย่างไร:**

1. ตรวจ `X-Hub-Signature-256` ด้วย HMAC SHA-256 + `FB_APP_SECRET`
2. Parse JSON body → วน loop ทุก messaging event
3. ข้าม echo messages (`is_echo: true`)
4. ถ้าเป็น text message → `POST http://localhost:3000/chat` พร้อม `message` (ใช้ `sender_id` เป็น `session_id` เพื่อแยกสนทนาแต่ละคน)
5. ถ้าเป็น postback → forward `payload` ไป Agent เหมือนกัน
6. รับคำตอบ → ส่งกลับผ่าน Facebook Send API (`POST graph.facebook.com/v24.0/me/messages`)
7. Return `EVENT_RECEIVED` เสมอ (Facebook requirement)

### 11.2 Agent API (`agent/agent_api.py`)

| Endpoint | Method | คำอธิบาย |
|----------|--------|----------|
| `/chat` | POST | รับ `message` + `session_id` (optional) → ให้ AI ประมวลผล → ตอบ `response` |

**Request Body:**

| Field | Type | Required | คำอธิบาย |
|-------|------|----------|----------|
| `message` | string | ✅ | ข้อความจากผู้ใช้ |
| `session_id` | string | ❌ | Session ID (ถ้าไม่ส่ง จะสร้างอัตโนมัติ 8 ตัวอักษร) |

**Response Body:**

| Field | Type | คำอธิบาย |
|-------|------|----------|
| `session_id` | string | Session ID สำหรับคุยต่อเนื่อง |
| `response` | string | ข้อความตอบจาก AI Agent |
| `memory_count` | int | จำนวน messages ในประวัติสนทนา |

**ฟีเจอร์:**

- **Conversation history (Short-Term Memory)** — เก็บประวัติสนทนาแยกตาม `session_id` ใน **SQLite** (`sessions.db`) ผ่าน `SessionStore` class ทำให้คุยต่อเนื่องได้ แม้รีสตาร์ท server ก็ไม่หาย
- **Session limits** — สูงสุด 50 ข้อความต่อ session, หมดอายุ 24 ชั่วโมง (configurable ผ่าน env vars)
- **Long-Term Memory** — Agent ใช้ memory tools (`memory_add`, `memory_search`) ผ่าน MCP เพื่อจดจำข้อมูลผู้ใช้ข้ามเซสชัน (ชื่อ, งบ, ยี่ห้อที่ชอบ)
- **Auto session** — ถ้าไม่ส่ง `session_id` จะสร้างใหม่อัตโนมัติ (uuid ตัดเหลือ 8 ตัว)
- **OpenAI Agents SDK** — ใช้ `Runner.run()` ครอบด้วย `trace()` เพื่อ observability
- **MCP connection** — เชื่อมต่อ MCP Server ตอน startup (lifespan) และปิดตอน shutdown อัตโนมัติ
- **Error handling** — ครอบ try/except ทั้ง Runner.run() และ post-processing ไม่ให้เป็น HTTP 500

**ตัวอย่าง request/response:**

```json
// Request — ครั้งแรก (ไม่ส่ง session_id)
POST /chat
{"message": "ค้นหาสินค้าเสื้อยืด"}

// Response
{
  "session_id": "a1b2c3d4",
  "response": "พบสินค้าเสื้อยืด 3 รายการ:\n1. เสื้อยืดคอกลม - ฿250\n2. ...",
  "memory_count": 4
}

// Request — คุยต่อเนื่อง (ส่ง session_id เดิม)
POST /chat
{"message": "สั่งตัวแรก 2 ชิ้น", "session_id": "a1b2c3d4"}

// Response
{
  "session_id": "a1b2c3d4",
  "response": "รับทราบครับ กำลังสร้างออเดอร์สินค้าเสื้อยืดคอกลม 2 ชิ้น ...",
  "memory_count": 10
}
```

### 11.3 MCP Server (`mcp-server/server.py`)

MCP Server เปิด tools 21 ตัวให้ Agent เรียกใช้ผ่าน Model Context Protocol:

- ใช้ **FastMCP** framework
- Tools ทุกตัวเรียก **GoSaaS UAT API** จริง (bearer token auth)
- HTTP client ตั้ง timeout 15 วินาที
- Utilities tools (verify_address, faq, intent_classify) ใช้ **OpenAI GPT-4o-mini** เพิ่มเติม
- **Memory tools** (memory_add, memory_search, memory_get_all, memory_delete) ใช้ **mem0** + **Qdrant vector DB** สำหรับ long-term memory

**Configuration (`mcp-server/config.py`):**

- **OpenAI client** — สำหรับ FAQ, intent classification, hybrid search refinement
- **mem0 Memory** — Long-term memory config:
  - LLM: `gpt-4o-mini` (สกัดข้อมูลสำคัญจากบทสนทนาอัตโนมัติ)
  - Embedder: `text-embedding-3-small` (แปลง memory เป็น vector)
  - Vector Store: **Qdrant** (เก็บใน `mcp-server/mem0_data/qdrant/`)
- **API helpers** — `api_get()`, `api_post()`, `api_delete()` สำหรับเรียก GoSaaS API

### 11.4 Session Store (`agent/session_store.py`)

SQLite-backed persistent session store สำหรับ short-term memory:

- เก็บประวัติสนทนาใน `agent/sessions.db`
- ตาราง `sessions`: `session_id` (PK), `history` (JSON), `created_at`, `updated_at`
- **Max messages** — ตัด messages เก่าเมื่อเกิน 50 (env: `MAX_HISTORY_MESSAGES`)
- **TTL** — ลบ session ที่ไม่ได้ใช้เกิน 24 ชม. อัตโนมัติ (env: `SESSION_TTL_HOURS`)
- **Lazy cleanup** — ทำความสะอาด expired sessions ทุกครั้งที่เรียก `.get()`
- Methods: `get()`, `save()`, `delete()`, `count()`, `list_all()`

### 11.5 CLI Agent (`agent/run_agents.py`)

Agent ตัวเดียวกันแต่รันเป็น interactive CLI สำหรับทดสอบใน terminal มี ConsoleTraceProcessor แสดง trace แบบ real-time พร้อมสีเพื่อ debug รองรับ 2 โหมด:

- **CLI mode** (default) — พิมพ์ใน terminal, streaming response
- **TUI mode** (`--tui`) — เปิด Textual UI พร้อม tabs สำหรับ chat, traces, memory, sessions

---

## 12. Tools ทั้ง 21 ตัว

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

### Hybrid Search

| Tool | คำอธิบาย |
|------|----------|
| `hybrid_search` | ค้นหาสินค้าแบบ hybrid (semantic + substring) พร้อม LLM refinement |

**Parameters:**

| Parameter | Type | Default | คำอธิบาย |
|-----------|------|---------|----------|
| `query` | string | — | คำค้นหา (ภาษาไทยหรืออังกฤษ) |
| `top_k` | int | 5 | จำนวนผลลัพธ์สูงสุดต่อแบบค้นหา |
| `min_price` | float | null | ราคาขั้นต่ำ (บาท) |
| `max_price` | float | null | ราคาสูงสุด (บาท) |
| `color` | string | null | สีสินค้า (partial match) |
| `model` | string | null | รุ่นสินค้า (partial match) |
| `min_screen` | float | null | ขนาดหน้าจอขั้นต่ำ (นิ้ว) |
| `max_screen` | float | null | ขนาดหน้าจอสูงสุด (นิ้ว) |
| `min_stock` | int | null | จำนวนคงเหลือขั้นต่ำ |

**วิธีทำงาน:**

1. **Semantic Search** — ค้นหาตามความหมายด้วย OpenAI embeddings + FAISS (เช่น "มือถือจอใหญ่ราคาถูก")
2. **Substring Search** — ค้นหาตรงตัวอักษร SQL LIKE ใน text, name, sku, color, model (เช่น SKU "IPH-16PM")
3. **Merge & Deduplicate** — รวมผลลัพธ์จากทั้ง 2 วิธี ตัดรายการซ้ำ
4. **LLM Refinement** — ใช้ GPT-4o-mini กรองผลลัพธ์ที่ไม่เกี่ยวข้องออก (เมื่อสงสัย จะเก็บไว้ — ให้ recall สูงกว่า precision)

**ตัวอย่าง response:**

```json
{
  "success": true,
  "query": "มือถือจอใหญ่",
  "filters": {"min_price": 20000},
  "total_candidates": 10,
  "refined_count": 5,
  "results": [
    {
      "id": 1,
      "name": "iPhone 16 Pro Max",
      "sku": "IPH-16PM-BLK-256",
      "price": 52900,
      "price_formatted": "52,900 บาท",
      "stock": 15,
      "color": "ดำไทเทเนียม",
      "model": "iPhone 16 Pro Max",
      "screen_size": 6.9,
      "score": 0.8234,
      "source": "vector"
    }
  ]
}
```

> **หมายเหตุ:** tool นี้ต้องมีข้อมูลใน vector store ก่อน — ใช้ `python agent/vector_search.py` แล้วรัน `load <product_file>` เพื่อนำเข้าสินค้า

### Memory (Long-Term)

| Tool | คำอธิบาย |
|------|----------|
| `memory_add` | บันทึกข้อมูลสำคัญของผู้ใช้ข้ามเซสชัน (ชื่อ, งบ, ยี่ห้อที่ชอบ, สี) |
| `memory_search` | ค้นหา memory ที่เกี่ยวข้องกับคำถาม (semantic search) |
| `memory_get_all` | ดึง memory ทั้งหมดของผู้ใช้ |
| `memory_delete` | ลบ memory ที่ระบุ (เมื่อผู้ใช้ขอให้ลืม) |

**Parameters (memory_add):**

| Parameter | Type | คำอธิบาย |
|-----------|------|----------|
| `messages` | string | JSON string ของ messages array เช่น `'[{"role":"user","content":"ผมชื่อต้น ชอบ iPhone"}]'` |
| `user_id` | string | รหัสผู้ใช้ (เช่น Facebook sender_id หรือ session_id) |

**Parameters (memory_search):**

| Parameter | Type | Default | คำอธิบาย |
|-----------|------|---------|----------|
| `query` | string | — | คำค้นหา เช่น "ยี่ห้อที่ชอบ", "งบประมาณ" |
| `user_id` | string | — | รหัสผู้ใช้ |
| `limit` | int | 5 | จำนวนผลลัพธ์สูงสุด |

**วิธีทำงาน:**

1. เมื่อผู้ใช้บอกข้อมูลสำคัญ Agent จะเรียก `memory_add` ทันที
2. mem0 ใช้ LLM (GPT-4o-mini) สกัดข้อมูลสำคัญจากบทสนทนาอัตโนมัติ
3. แปลงเป็น vector ด้วย `text-embedding-3-small` แล้วเก็บใน Qdrant
4. เมื่อผู้ใช้กลับมาคุย Agent จะเรียก `memory_search` เพื่อ personalize คำตอบ

**ตัวอย่างข้อมูลที่ถูกจดจำ:**

- ชื่อผู้ใช้, เบอร์โทร, ที่อยู่
- งบประมาณ, ยี่ห้อที่ชอบ, สีที่ชอบ
- ประวัติการสั่งซื้อ, preference ต่างๆ

---

## 13. CLI Agent — ใช้งานผ่าน Terminal

### วิธีรัน

```bash
# Terminal 1
python mcp-server/server.py

# Terminal 2
python agent/run_agents.py
```

### คำสั่ง

| คำสั่ง | ผลลัพธ์ |
|--------|---------|
| พิมพ์ข้อความ + Enter | ส่งข้อความให้ Agent |
| `clear` | ล้างประวัติสนทนา |
| `quit` / `exit` / `q` | ออกจากโปรแกรม |
| `Ctrl+C` | บังคับออก |

### ตัวอย่างการใช้งาน

**ค้นหาสินค้า:**

```
You: แสดงรายการสินค้าทั้งหมด
Assistant: รายการสินค้าที่มี: 1. สินค้า A  2. สินค้า B ...
```

**ดูยอดขายวันนี้:**

```
You: ยอดขายวันนี้เท่าไหร่
Assistant: ยอดขายวันนี้ทั้งหมด 15,230 บาท จาก 12 ออเดอร์
```

**ตรวจสอบสถานะจัดส่ง:**

```
You: เช็คพัสดุ tracking TH12345678
Assistant: พัสดุ TH12345678 สถานะ: กำลังจัดส่ง ...
```

**สร้าง Order Draft:**

```
You: สร้างออเดอร์ให้ คุณสมชาย 0812345678 ที่อยู่ 123 ถ.สุขุมวิท
     แขวงคลองตัน เขตคลองเตย กรุงเทพ 10110 สินค้า id 5 จำนวน 2 ชิ้น
Assistant: (Agent จะเรียก verify_address, get_order_draft_meta, แล้วจึง create_order_draft)
```

---

## 14. ระบบ Tracing

CLI Agent มี ConsoleTraceProcessor แสดง trace ใน terminal (stderr) แบบ real-time พร้อมสี:

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

## 15. TUI Agent — ใช้งานผ่าน Terminal UI

### วิธีรัน

```bash
# Terminal 1
python mcp-server/server.py

# Terminal 2
python agent/run_agents.py --tui
```

### หน้าจอ

TUI แบ่งเป็น 2 ส่วน:

- **ซ้าย (55%)** — Chat panel แสดงข้อความ user (สีฟ้า) และ assistant (สีเขียว)
- **ขวา (45%)** — Tabbed panel มี 5 tabs

### Tabs

| Tab | คำอธิบาย |
|-----|----------|
| **Replies** | แสดงคำตอบล่าสุดจาก Agent แบบ streaming (สีเขียว) |
| **Traces** | แสดง trace ของ Agent (tool calls, LLM generations, MCP operations) |
| **STM** | Short-Term Memory — ประวัติสนทนาใน session ปัจจุบัน (จาก SQLite) |
| **LTM** | Long-Term Memory — ข้อมูลที่จดจำของผู้ใช้ (จาก mem0/Qdrant) ใส่ `user_id` แล้วกด **Refresh** |
| **Session** | จัดการ sessions — ดูรายการ sessions, สลับ session, ดู session ปัจจุบัน |

### การใช้งาน

1. **พิมพ์ข้อความ** ที่ช่อง input ด้านล่าง แล้วกด **Enter** หรือคลิก **Send**
2. **ดู STM** — คลิก tab "STM" จะแสดงประวัติ chat ทั้งหมดใน session นี้
3. **ดู LTM** — คลิก tab "LTM" → ใส่ user_id (default: `cli`) → กด **Refresh** → เห็น memories ที่จดจำไว้
4. **สลับ Session** — คลิก tab "Session" → กด **Refresh Sessions** → คลิกเลือก session ที่ต้องการ
5. **ดู Traces** — คลิก tab "Traces" เพื่อดูว่า Agent เรียก tools อะไรบ้าง

### Keybindings

| คีย์ | ผลลัพธ์ |
|------|---------|
| `Enter` | ส่งข้อความ |
| `Ctrl+Q` | ออกจากโปรแกรม |
| `Tab` | สลับระหว่าง elements |

---

## 16. Vector Search REPL — ค้นหาเอกสารด้วย AI

Interactive REPL สำหรับเก็บและค้นหาเอกสารด้วย **Semantic Search** — ค้นหาตามความหมาย ไม่ใช่แค่คำตรงตัว พร้อม autocomplete, command history, และ colored prompt ด้วย `prompt_toolkit`

### สถาปัตยกรรม

```
คำสั่ง add:
  ข้อความ → OpenAI Embedding API → เก็บใน SQLite (text + vector)

คำสั่ง load:
  ไฟล์สินค้า → parse metadata → แปลงเป็นภาษาธรรมชาติ → batch embed → เก็บใน SQLite (text + vector + metadata)

คำสั่ง search (hybrid):
  คำค้นหา → [1] OpenAI Embedding → FAISS (semantic)
           → [2] SQLite LIKE (substring)
           → แสดงผลแยก 2 sections พร้อม ★ overlap marking
```

| เทคโนโลยี | หน้าที่ |
|-----------|---------|
| **OpenAI `text-embedding-3-small`** | แปลงข้อความเป็น vector 1536 มิติ |
| **FAISS (Facebook AI Similarity Search)** | ค้นหา vector ที่ใกล้เคียงที่สุดแบบ cosine similarity |
| **SQLite** | เก็บข้อความต้นฉบับและ embedding ลงไฟล์ `agent/vector_store.db` |
| **prompt_toolkit** | Interactive REPL พร้อม autocomplete, history, colored prompt |

### ติดตั้ง

```bash
pip install -r requirements.txt
```

> `faiss-cpu` และ `prompt_toolkit` อยู่ใน `requirements.txt` แล้ว

### วิธีใช้งาน

**เปิด REPL:**

```bash
python agent/vector_search.py
```

**ตัวอย่าง session:**

```
  +==================================================+
  |  Vector Search -- Semantic Search with FAISS      |
  |  Model: text-embedding-3-small                   |
  |  DB: vector_store.db                             |
  |  Documents: 0                                    |
  +==================================================+

  Type 'help' for commands, 'quit' to exit.

vector> add Machine learning is a subset of AI
  Stored document 1 (40 chars)

vector> add Python is great for data science
  Stored document 2 (33 chars)

vector> add The quick brown fox jumps over the lazy dog
  Stored document 3 (43 chars)

vector> search AI and deep learning

  Results for: "AI and deep learning"
  ================================================

  [1] (score: 0.4849)  ID: 1
      Added: 2026-02-12T07:49:23+00:00
      Machine learning is a subset of AI

  [2] (score: 0.3066)  ID: 2
      Added: 2026-02-12T07:49:23+00:00
      Python is great for data science

vector> search animals /2

  Results for: "animals"
  ================================================

  [1] (score: 0.3115)  ID: 3
      Added: 2026-02-12T07:49:24+00:00
      The quick brown fox jumps over the lazy dog

  [2] (score: 0.1772)  ID: 1
      Added: 2026-02-12T07:49:23+00:00
      Machine learning is a subset of AI

vector> list

  Documents (3 total):
    [1] Machine learning is a subset of AI (2026-02-12)
    [2] Python is great for data science (2026-02-12)
    [3] The quick brown fox jumps over the lazy dog (2026-02-12)

vector> count
  3 documents in store

vector> quit
  Goodbye!
```

### ฟีเจอร์ REPL

| ฟีเจอร์ | คำอธิบาย |
|---------|----------|
| **Autocomplete** | กด Tab เพื่อเติมคำสั่ง (add, load, search, list, count, help, quit) |
| **Command History** | กดลูกศรขึ้น/ลงเพื่อเรียกคำสั่งก่อนหน้า |
| **Colored Prompt** | prompt `vector>` แสดงสีฟ้า (cyan) |
| **Ctrl+C / Ctrl+D** | ออกจากโปรแกรมได้ทุกเมื่อ |

### คำสั่งทั้งหมด

| คำสั่ง | คำอธิบาย | ตัวอย่าง |
|--------|----------|----------|
| `add <text>` | เพิ่มเอกสารลง vector store | `add ข้อความที่ต้องการเก็บ` |
| `load <filepath>` | นำเข้าไฟล์ — ตรวจจับอัตโนมัติว่าเป็นไฟล์สินค้า (structured) หรือ plain text | `load products.txt` |
| `search <query>` | Hybrid search: semantic + substring (top 5) | `search มือถือจอใหญ่` |
| `search <query> /N` | กำหนดจำนวนผลลัพธ์ | `search AI /3` |
| `search <query> --flag` | ค้นหาพร้อม metadata filter | `search iPhone --min-price 20000 --color ดำ` |
| `list` | แสดงเอกสารทั้งหมดในฐานข้อมูล | `list` |
| `count` | แสดงจำนวนเอกสาร | `count` |
| `help` | แสดงรายการคำสั่ง | `help` |
| `quit` / `exit` / `q` | ออกจากโปรแกรม | `quit` |

### Metadata Filters สำหรับ Search

ใช้ flags เพิ่มท้ายคำสั่ง `search` เพื่อกรองผลลัพธ์ตาม metadata ของสินค้า:

| Flag | คำอธิบาย | ตัวอย่าง |
|------|----------|----------|
| `--min-price N` | ราคาขั้นต่ำ (บาท) | `--min-price 10000` |
| `--max-price N` | ราคาสูงสุด (บาท) | `--max-price 30000` |
| `--color X` | สีสินค้า (partial match) | `--color ดำ` |
| `--model X` | รุ่นสินค้า (partial match) | `--model Galaxy` |
| `--min-screen N` | ขนาดหน้าจอขั้นต่ำ (นิ้ว) | `--min-screen 6.5` |
| `--max-screen N` | ขนาดหน้าจอสูงสุด (นิ้ว) | `--max-screen 6.8` |
| `--min-stock N` | จำนวนคงเหลือขั้นต่ำ | `--min-stock 10` |

**ตัวอย่างการใช้ filters:**

```
vector> search มือถือจอใหญ่ --min-price 20000 --max-price 40000
vector> search iPhone สีดำ --min-stock 10 /3
vector> search IPH-16PM                        (substring finds exact SKU)
```

### รูปแบบไฟล์สินค้า (Product File Format)

คำสั่ง `load` จะตรวจจับไฟล์สินค้าอัตโนมัติจาก header ที่เป็น pipe-delimited (`|`):

```
id | name | sku | price | stock | color | model | screen_size
1 | iPhone 16 Pro Max | IPH-16PM-BLK-256 | 52900 | 15 | ดำไทเทเนียม | iPhone 16 Pro Max | 6.9
2 | Samsung Galaxy S24 Ultra | SAM-S24U-BLK-256 | 44900 | 20 | ดำ Titanium | Galaxy S24 Ultra | 6.8
```

เมื่อตรวจพบไฟล์สินค้า ระบบจะ:

1. Parse metadata columns (name, sku, price, stock, color, model, screen_size)
2. แปลงแต่ละแถวเป็น **ภาษาธรรมชาติ** ก่อน embed เช่น:
   `"iPhone 16 Pro Max สีดำไทเทเนียม หน้าจอ 6.9 นิ้ว ราคา 52,900 บาท มีสินค้า 15 เครื่อง (SKU: IPH-16PM-BLK-256)"`
3. Batch embed ด้วย OpenAI API (ทีละ 100 รายการ) แล้วเก็บลง SQLite พร้อม metadata

ถ้าไฟล์ไม่มี header ที่ตรงกัน จะถือเป็น **plain text** — แต่ละบรรทัด = 1 document

**ตัวอย่างการนำเข้า:**

```
vector> load data/products.txt
  Detected structured product file: products.txt
  Found 25 products to import
  Converting rows to natural language for embedding...

  Sample (row 1):
    "iPhone 16 Pro Max สีดำไทเทเนียม หน้าจอ 6.9 นิ้ว ราคา 52,900 บาท มีสินค้า 15 เครื่อง (SKU: IPH-16PM-BLK-256)"

  Imported 25/25...
  Done! 25 products imported from products.txt
  Metadata columns stored: name, sku, price, stock, color, model, screen_size
  Use '--min-price', '--max-price', '--color', '--model' flags with search to filter
```

### Hybrid Search — ผลลัพธ์ 2 ส่วน

ทุกคำสั่ง `search` จะรันการค้นหา 2 แบบพร้อมกันและแสดงผลแยกส่วน:

```
vector> search iPhone --min-price 30000

  Hybrid search: "iPhone"
  Filters: {'min_price': '30000'}

  ════════════════════ Semantic Search (ความหมายใกล้เคียง) ════════════════════

  [1] (score: 0.7234)  ID: 1
      Name:   iPhone 16 Pro Max
      SKU:    IPH-16PM-BLK-256
      Price:  52,900 บาท
      Stock:  15 เครื่อง
      Color:  ดำไทเทเนียม
      Model:  iPhone 16 Pro Max
      Screen: 6.9 นิ้ว

  ════════════════════ Substring Search (ตรงตัวอักษร) ════════════════════

  [1] ID: 1 ★
      Name:   iPhone 16 Pro Max
      ...

  ★ = also appeared in semantic results
```

- **Semantic Search** — ค้นหาตามความหมายด้วย OpenAI embeddings + FAISS (score สูง = ตรงกว่า)
- **Substring Search** — ค้นหาตรงตัวอักษร (SQL LIKE) ใน text, name, sku, color, model
- เครื่องหมาย **★** แสดงผลลัพธ์ที่ปรากฏทั้ง 2 วิธี (overlap — ยืนยันว่าตรงจริง)

### โครงสร้างโค้ด (`agent/vector_search.py`)

| ส่วน | ฟังก์ชัน | หน้าที่ |
|------|---------|---------|
| **SQLite Layer** | `init_db()` | สร้าง/เปิดฐานข้อมูล SQLite + auto-migrate metadata columns |
| | `store_document()` | บันทึกข้อความ + embedding + metadata |
| | `load_all_embeddings()` | โหลด embeddings ทั้งหมดสำหรับสร้าง index |
| | `load_filtered_embeddings()` | โหลด embeddings ที่ผ่าน metadata filters |
| | `substring_search()` | ค้นหาด้วย SQL LIKE ใน text, name, sku, color, model |
| | `get_documents_by_ids()` | ดึงข้อความจาก ID |
| | `get_document_count()` | นับจำนวนเอกสาร |
| | `get_all_documents()` | ดึงเอกสารทั้งหมด |
| **NL Conversion** | `row_to_natural_language()` | แปลง product row เป็นประโยคภาษาธรรมชาติสำหรับ embedding |
| **Embedding Layer** | `get_embedding()` | เรียก OpenAI API แปลงข้อความเป็น vector |
| | `get_embeddings_batch()` | Embed หลายข้อความในครั้งเดียว (batch) |
| **FAISS Layer** | `build_faiss_index()` | สร้าง FAISS index จาก embeddings |
| **Programmatic API** | `get_connection()` | เปิด read-only connection สำหรับ MCP tool |
| | `hybrid_search()` | ค้นหาแบบ vector + substring, merge และ deduplicate |
| **File Parser** | `parse_product_file()` | ตรวจและ parse ไฟล์สินค้าแบบ pipe-delimited |
| **Commands** | `cmd_add()` | จัดการคำสั่ง add |
| | `cmd_load()` | จัดการคำสั่ง load (auto-detect product vs plain text) |
| | `cmd_search()` | จัดการคำสั่ง search (hybrid: semantic + substring) |
| | `parse_filters()` | แยก filter flags (--min-price, --color ฯลฯ) จาก query |
| | `cmd_list()` | จัดการคำสั่ง list |
| | `cmd_count()` | จัดการคำสั่ง count |
| | `show_help()` | แสดงรายการคำสั่ง |
| **REPL** | `show_banner()` | แสดง banner ตอนเริ่มต้น |
| | `repl()` | Interactive loop พร้อม prompt_toolkit |

### หลักการทำงาน

1. **Embedding** — ข้อความถูกแปลงเป็น vector 1536 มิติด้วย OpenAI `text-embedding-3-small` ข้อความที่มีความหมายคล้ายกันจะได้ vector ที่ชี้ไปทิศทางเดียวกัน

2. **FAISS Index** — สร้าง index แบบ `IndexFlatIP` (Inner Product) ทุกครั้งที่รัน search โดยโหลด embeddings จาก SQLite แล้ว normalize ด้วย L2 ทำให้ inner product เทียบเท่า cosine similarity

3. **SQLite Persistence** — ข้อมูลทั้งหมดเก็บใน `agent/vector_store.db` ประกอบด้วย:
   - `id` — รหัสเอกสาร (auto increment)
   - `text` — ข้อความต้นฉบับ (หรือ natural language สำหรับสินค้า)
   - `embedding` — vector เก็บเป็น BLOB (6,144 bytes ต่อเอกสาร)
   - `created_at` — วันเวลาที่เพิ่ม
   - `name` — ชื่อสินค้า (TEXT, nullable)
   - `sku` — รหัสสินค้า (TEXT, nullable)
   - `price` — ราคา (REAL, nullable)
   - `stock` — จำนวนคงเหลือ (INTEGER, nullable)
   - `color` — สี (TEXT, nullable)
   - `model` — รุ่น (TEXT, nullable)
   - `screen_size` — ขนาดหน้าจอ (REAL, nullable)

### หมายเหตุ

- ต้องมี `OPENAI_API_KEY` ใน `.env` (ใช้ key เดียวกับ Agent)
- ไฟล์ `vector_store.db` สร้างอัตโนมัติเมื่อรัน `add` หรือ `load` ครั้งแรก
- Score ยิ่งสูง = ยิ่งตรงกับคำค้นหา (0.0 ถึง 1.0) — ส่วน Substring Search ไม่มี score
- รองรับทุกภาษาที่ OpenAI embedding รองรับ (ไทย, อังกฤษ, จีน, ญี่ปุ่น ฯลฯ)
- Metadata columns (name, sku, price ฯลฯ) เป็น nullable — ฐานข้อมูลเก่าจะถูก auto-migrate เมื่อเปิดใช้งาน
- MCP tool `hybrid_search` ใช้ `get_connection()` + `hybrid_search()` จากไฟล์นี้โดยตรง

---

## 17. Concepts สำคัญ

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

### Conversation History (Short-Term Memory)

ระบบเก็บประวัติสนทนาไว้โดยใช้ `result.to_input_list()` เพื่อแปลงผลลัพธ์ (รวม tool calls และ tool results) กลับเป็น input สำหรับรอบถัดไป ทำให้ Agent จำบริบทได้ตลอดการสนทนา

- ทุก mode (CLI, TUI, API) ใช้ **SessionStore** (`agent/session_store.py`) เก็บใน **SQLite** (`sessions.db`)
- **Persistent** — รีสตาร์ท server แล้วประวัติสนทนาไม่หาย
- สูงสุด **50 ข้อความ** ต่อ session (env: `MAX_HISTORY_MESSAGES`)
- หมดอายุ **24 ชั่วโมง** หลังไม่มี activity (env: `SESSION_TTL_HOURS`)
- พิมพ์ `clear` ใน CLI เพื่อล้างประวัติ

### Long-Term Memory

นอกจาก short-term (ประวัติ chat) ระบบยังมี **long-term memory** ผ่าน mem0 + Qdrant:

- Agent เรียก `memory_add` เมื่อผู้ใช้บอกข้อมูลสำคัญ (ชื่อ, งบ, ยี่ห้อ)
- Agent เรียก `memory_search` เมื่อต้องการ personalize คำตอบ
- ข้อมูลอยู่ถาวรข้ามเซสชัน (ไม่หมดอายุ)
- ดูรายละเอียดเพิ่มใน [Section 18](#18-ระบบ-memory--short-term-vs-long-term)

### Streaming

CLI Agent ใช้ `Runner.run_streamed()` เพื่อให้ข้อความแสดงทีละตัวอักษร (token-by-token) ไม่ต้องรอจนตอบเสร็จทั้งหมด

### MCP (Model Context Protocol)

Agent ไม่ได้เรียก GoSaaS API โดยตรง แต่เรียกผ่าน MCP Server ซึ่งทำหน้าที่เป็นตัวกลาง ข้อดีคือ:
- แยก business logic (API calls) ออกจาก Agent logic
- Tools ถูก define ครั้งเดียวใน `mcp-server/tools/` แล้ว Agent เห็นอัตโนมัติ
- สามารถใช้ MCP Server เดียวกันกับ Agent หลายตัวได้

---

## 18. ระบบ Memory — Short-Term vs Long-Term

ระบบมี memory 2 ชั้นที่ทำงานร่วมกัน:

### เปรียบเทียบ

| ด้าน | Short-Term Memory | Long-Term Memory |
|------|-------------------|------------------|
| **ไฟล์** | `agent/session_store.py` | `mcp-server/tools/memory.py` |
| **Storage** | SQLite (`agent/sessions.db`) | Qdrant Vector DB (`mcp-server/mem0_data/qdrant/`) |
| **Library** | Python sqlite3 | mem0 + Qdrant |
| **ขอบเขต** | 1 session (1 บทสนทนา) | ข้าม session ทั้งหมด (ตลอดไป) |
| **อายุข้อมูล** | หมดอายุ 24 ชม. (configurable) | ไม่หมดอายุ (persistent ถาวร) |
| **จำกัด** | สูงสุด 50 messages ต่อ session | ไม่จำกัด |
| **Key** | `session_id` | `user_id` |
| **เก็บอะไร** | ข้อความทั้งหมด (user + assistant + tool calls) | ข้อมูลสำคัญที่สกัดมา (ชื่อ, งบ, ยี่ห้อ, สี) |
| **วิธีเก็บ** | อัตโนมัติทุก turn | Agent เรียก `memory_add` tool |
| **วิธีดึง** | โหลดอัตโนมัติตอนเริ่มทุก turn | Agent เรียก `memory_search` / `memory_get_all` |
| **ใช้ทำอะไร** | จำบริบทสนทนา ("เมื่อกี้ถามอะไร?") | จดจำข้อมูลผู้ใช้ข้ามวัน/ข้ามเดือน ("คุณเคยบอกว่าชอบ iPhone") |

### สรุปแบบเข้าใจง่าย

- **Short-Term = ความจำระยะสั้น** — เหมือนคนจำได้ว่าเมื่อกี้คุยอะไร แต่พอหลับไป (24 ชม.) จะลืมหมด
- **Long-Term = ความจำระยะยาว** — เหมือนจดสมุด ข้อมูลสำคัญจะอยู่ตลอดไป แม้เริ่มบทสนทนาใหม่ก็ยังจำได้

### Data Flow

```
ผู้ใช้ส่งข้อความ
       │
1. โหลด Short-Term Memory (ประวัติ chat ใน session นี้)
       │
2. ส่ง [ประวัติ + ข้อความใหม่] ให้ Agent
       │
3. Agent อาจเรียก memory_search (Long-Term) เพื่อดึง preference เก่า
4. Agent ประมวลผลและตอบ
5. Agent อาจเรียก memory_add (Long-Term) ถ้าผู้ใช้บอกข้อมูลใหม่
       │
6. บันทึก Short-Term Memory (ทั้ง history ใหม่)
       │
ส่งคำตอบกลับผู้ใช้
```

### ทดสอบ Short-Term Memory

ทดสอบว่า Agent จำบริบทได้ภายใน session เดียวกัน:

```bash
# ส่งข้อความแรก
curl -X POST http://localhost:3000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"สวัสดี ผมชื่อสมชาย\", \"session_id\": \"test-stm\"}"

# ถามย้อน (session_id เดิม) → ต้องตอบได้ว่า "สมชาย"
curl -X POST http://localhost:3000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"เมื่อกี้ผมบอกว่าผมชื่ออะไร?\", \"session_id\": \"test-stm\"}"

# เปลี่ยน session → ต้องตอบไม่ได้ (ไม่มีบริบทเก่า)
curl -X POST http://localhost:3000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"เมื่อกี้ผมบอกว่าผมชื่ออะไร?\", \"session_id\": \"test-stm-new\"}"
```

### ทดสอบ Long-Term Memory

ทดสอบว่า Agent จดจำข้อมูลสำคัญได้แม้ลบ short-term:

```bash
# บอกข้อมูลสำคัญ → Agent ควรเรียก memory_add
curl -X POST http://localhost:3000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"ผมชื่อธนกร ชอบ iPhone สีดำ งบ 40,000\", \"session_id\": \"test-ltm\"}"

# ลบ short-term memory (ล้างประวัติ chat)
sqlite3 agent/sessions.db "DELETE FROM sessions WHERE session_id = 'test-ltm';"

# ถามข้อมูลที่เคยบอก (session_id เดิม = user_id เดิม)
# → Agent ควรเรียก memory_search แล้วตอบได้ว่า "iPhone สีดำ"
curl -X POST http://localhost:3000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"ผมเคยบอกว่าชอบยี่ห้ออะไร?\", \"session_id\": \"test-ltm\"}"
```

### ทดสอบความแตกต่าง

```bash
# บอกข้อมูลทั้งสำคัญ (ชอบสีแดง) และไม่สำคัญ (อากาศร้อน)
curl -X POST http://localhost:3000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"ผมชื่อวิชัย ชอบสีแดง งบ 20,000 แล้วก็วันนี้อากาศร้อนมาก\", \"session_id\": \"test-diff\"}"

# ลบ short-term
sqlite3 agent/sessions.db "DELETE FROM sessions WHERE session_id = 'test-diff';"

# "อากาศร้อน" → ตอบไม่ได้ (short-term ถูกลบ, ไม่อยู่ใน long-term)
# "ชอบสีอะไร" → ตอบ "สีแดง" ได้ (long-term ยังจำอยู่!)
```

---

## 19. ทดสอบ MCP Server ด้วย MCP Inspector

[MCP Inspector](https://github.com/modelcontextprotocol/inspector) เป็น Web UI สำหรับทดสอบและ debug MCP Server โดยไม่ต้องเขียน client code

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

## 20. Logging

Webhook บันทึก log ทั้ง console และไฟล์:

- **Console** — เห็นทันทีใน terminal
- **File** — `webhook/logs/webhook.log`
  - Rotate อัตโนมัติเมื่อถึง 5 MB
  - เก็บไฟล์เก่าสูงสุด 3 ไฟล์

**รูปแบบ:**

```
2026-02-12 10:30:45,123 | INFO     | Message from 123456 to 789012: สวัสดี
2026-02-12 10:30:46,456 | INFO     | Message sent to 123456
2026-02-12 10:30:47,789 | ERROR    | Send API error 400: Invalid token
```

**ดู log แบบ real-time:**

```bash
# Windows PowerShell
Get-Content webhook/logs/webhook.log -Wait

# Linux/macOS
tail -f webhook/logs/webhook.log
```

---

## 21. Deploy ขึ้น Production

ตอน deploy จริงไม่ต้องใช้ ngrok ใช้ server ที่มี domain + SSL แทน

### ตัวอย่าง: Docker Compose

```yaml
# docker-compose.yml
services:
  mcp-server:
    build: ./mcp-server
    ports:
      - "8000:8000"
    env_file: .env

  agent-api:
    build: ./agent
    ports:
      - "3000:3000"
    env_file: .env
    depends_on:
      - mcp-server

  webhook:
    build: ./webhook
    ports:
      - "8001:8001"
    env_file: ./webhook/.env
    depends_on:
      - agent-api
```

### หลัง Deploy

1. เปลี่ยน **Callback URL** ใน Meta Developer เป็น URL จริง เช่น `https://yourdomain.com/webhook`
2. อัปเดต **Privacy Policy URL** และ **Terms URL** ใน **การตั้งค่าแอพ → ข้อมูลพื้นฐาน**
3. อัปเดต `AI_AGENT_URL` ใน `webhook/.env` ให้ชี้ไป Agent API ของ production

---

## 22. Troubleshooting

| ปัญหา | วิธีแก้ |
|-------|---------|
| `Failed to connect to MCP server` | ตรวจสอบว่า `python mcp-server/server.py` รันอยู่ |
| `OPENAI_API_KEY not set` | ตรวจสอบไฟล์ `.env` ว่ามี key ถูกต้อง |
| Tool call ล้มเหลว | ตรวจสอบ `UAT_API_KEY` และ `UAT_API_URL` ใน `.env` |
| สีไม่แสดงใน terminal | ใช้ terminal ที่รองรับ ANSI colors (Windows Terminal, VS Code) |
| Port 8000/8001/3000 ถูกใช้งาน | ปิด process อื่นที่ใช้ port นั้น |
| Inspector ขึ้น "Connection Error" | ตรวจสอบว่า mcp-server/server.py รันอยู่ และ URL ถูกต้อง |

### Webhook verify ไม่ผ่าน

- ตรวจว่า **webhook server รันอยู่** และ **ngrok tunnel เปิดอยู่**
- ตรวจว่า `FB_VERIFY_TOKEN` ใน `webhook/.env` ตรงกับค่าที่กรอกใน Meta Developer
- ดู log ใน terminal ของ webhook ว่ามี GET request เข้ามาไหม

### ส่งข้อความแล้วไม่ได้คำตอบ

- ตรวจว่า **ทั้ง 3 services รันอยู่** (MCP Server → Agent API → Webhook)
- ตรวจ `FB_PAGE_ACCESS_TOKEN` ว่ายังใช้ได้อยู่
- ตรวจ `AI_AGENT_URL` ใน `webhook/.env` ว่าชี้ไป `http://localhost:3000/chat`
- ดู log ของ webhook — ถ้าเห็น "AI Agent request failed" แสดงว่า Agent API มีปัญหา
- ดู log ของ agent — ถ้าเห็น MCP connection error แสดงว่า MCP Server มีปัญหา

### Signature verification failed

- ตรวจว่า `FB_APP_SECRET` ใน `webhook/.env` ตรงกับ App Secret ใน Meta Developer
- ทดสอบ local ด้วย curl: เคลียร์ค่า `FB_APP_SECRET` ชั่วคราว (ระบบจะข้ามตรวจ signature)

### Bot ตอบช้า

- Agent ต้องเรียก OpenAI API + GoSaaS API ซึ่งอาจใช้เวลา 5-15 วินาที
- Facebook จะรอ response ไม่เกิน 20 วินาที ก่อน timeout
- ถ้าช้าเกินไป ลองเปลี่ยน model เป็นตัวที่เร็วกว่า (เช่น `gpt-4o-mini`)

### ข้อความซ้ำ (echo)

- ระบบข้าม message ที่มี `is_echo: true` อัตโนมัติ
- ถ้ายังซ้ำ ตรวจว่าไม่ได้ subscribe webhook ซ้ำหลายครั้ง

### ทดสอบกับคนอื่นไม่ได้

- ตอน **Development Mode** ใช้ได้เฉพาะ admin/developer/tester ของ App
- เพิ่ม tester ได้ที่ **บทบาทในแอพ** → เพิ่มผู้คน
- ต้อง publish App + ผ่าน **App Review** ถึงจะใช้กับผู้ใช้ทั่วไปได้
