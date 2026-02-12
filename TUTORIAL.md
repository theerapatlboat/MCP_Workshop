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
12. [Tools ทั้ง 16 ตัว](#12-tools-ทั้ง-16-ตัว)
13. [CLI Agent — ใช้งานผ่าน Terminal](#13-cli-agent--ใช้งานผ่าน-terminal)
14. [ระบบ Tracing](#14-ระบบ-tracing)
15. [Vector Search REPL — ค้นหาเอกสารด้วย AI](#15-vector-search-repl--ค้นหาเอกสารด้วย-ai)
16. [Concepts สำคัญ](#16-concepts-สำคัญ)
17. [ทดสอบ MCP Server ด้วย MCP Inspector](#17-ทดสอบ-mcp-server-ด้วย-mcp-inspector)
18. [Logging](#18-logging)
19. [Deploy ขึ้น Production](#19-deploy-ขึ้น-production)
20. [Troubleshooting](#20-troubleshooting)

---

## 1. ภาพรวมระบบ

ระบบประกอบด้วย 3 ส่วนหลักที่ทำงานร่วมกัน ทำให้ลูกค้าสามารถสั่งซื้อสินค้า ติดตามพัสดุ ดูรายงานยอดขาย และอื่นๆ ได้ทั้งผ่าน **Facebook Messenger** และ **CLI**:

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
│  Agent API (port 3000)                      │    CLI Agent
│  - เก็บประวัติสนทนาแยกตาม session_id        │    (run_agents.py)
│  - ใช้ OpenAI Agents SDK ประมวลผล           │        │
│  - เรียก tools ผ่าน MCP protocol            │        │
└─────────────────────┬───────────────────────┘        │
                      ↓ MCP (Streamable HTTP)          ↓
┌─────────────────────────────────────────────┐
│  MCP Server (port 8000)                     │
│  - 16 tools สำหรับจัดการออเดอร์              │
│  - เรียก GoSaaS API จริง                    │
└─────────────────────────────────────────────┘
```

---

## 2. สถาปัตยกรรม

### Services

| Service | Port | ไฟล์ | หน้าที่ |
|---------|------|------|---------|
| **MCP Server** | 8000 | `mcp-server/server.py` | เปิด tools 16 ตัวให้ Agent เรียกใช้ผ่าน MCP protocol |
| **Webhook** | 8001 | `webhook/main.py` | รับ/ส่งข้อความกับ Facebook Messenger |
| **Agent API** | 3000 | `agent/agent_api.py` | AI Agent ที่ประมวลผลข้อความและตัดสินใจเรียก tools |
| **CLI Agent** | — | `agent/run_agents.py` | Agent แบบ interactive CLI สำหรับทดสอบใน terminal |
| **Vector Search** | — | `agent/vector_search.py` | Interactive REPL สำหรับเก็บและค้นหาเอกสารด้วย semantic search |

### Tools ที่ Agent ใช้ได้ (16 tools)

| หมวด | Tools | ตัวอย่างการใช้ |
|------|-------|---------------|
| **Order Draft** | `create_order_draft`, `get_order_draft`, `delete_order_draft`, `get_order_draft_meta`, `attach_order_draft_payment` | "สร้างออเดอร์สินค้า A 2 ชิ้น ส่งไปที่..." |
| **Product** | `list_product`, `get_product` | "ค้นหาสินค้าชื่อ xxx", "สินค้า ID 123 ราคาเท่าไร" |
| **Shipment** | `get_shipping_status`, `get_shipment` | "ติดตามพัสดุ TH123456", "สถานะออเดอร์ #789" |
| **Report** | `get_sales_summary`, `get_sales_summary_today`, `get_sales_filter` | "ยอดขายวันนี้", "สรุปยอดขายเดือนนี้" |
| **Order** | `get_order_meta` | ดึง metadata สำหรับสร้างออเดอร์ |
| **Utilities** | `verify_address`, `faq`, `intent_classify` | ตรวจที่อยู่, ตอบคำถามทั่วไป, จัดหมวดหมู่ intent |

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
│
├── mcp-server/                   # MCP Server — port 8000
│   ├── server.py                 # FastMCP server + tool registration
│   ├── config.py                 # API client helpers (api_get, api_post, api_delete)
│   ├── models.py                 # Pydantic models (AddressVerificationResult)
│   └── tools/
│       ├── order_draft.py        # 5 tools: สร้าง/ดู/ลบ draft, แนบชำระเงิน
│       ├── product.py            # 2 tools: ค้นหา/ดูรายละเอียดสินค้า
│       ├── shipment.py           # 2 tools: ติดตามพัสดุ/ดูรายละเอียดจัดส่ง
│       ├── report.py             # 3 tools: สรุปยอดขาย/ยอดวันนี้/ตัวกรอง
│       ├── order.py              # 1 tool:  ดึง order metadata
│       └── utilities.py          # 3 tools: ตรวจที่อยู่/FAQ/จัดหมวด intent
│
├── agent/                        # AI Agent
│   ├── run_agents.py             # CLI version (สำหรับทดสอบใน terminal)
│   ├── agent_api.py              # API version — port 3000 (สำหรับ webhook/frontend)
│   └── vector_search.py          # Semantic search REPL (OpenAI Embeddings + FAISS + SQLite)
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

- **Conversation history** — เก็บประวัติสนทนาแยกตาม `session_id` ในหน่วยความจำ (in-memory dict) ทำให้คุยต่อเนื่องได้
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

MCP Server เปิด tools ให้ Agent เรียกใช้ผ่าน Model Context Protocol:

- ใช้ **FastMCP** framework
- Tools ทุกตัวเรียก **GoSaaS UAT API** จริง (bearer token auth)
- HTTP client ตั้ง timeout 15 วินาที
- Utilities tools (verify_address, faq, intent_classify) ใช้ **OpenAI GPT-4o-mini** เพิ่มเติม

### 11.4 CLI Agent (`agent/run_agents.py`)

Agent ตัวเดียวกันแต่รันเป็น interactive CLI สำหรับทดสอบใน terminal มี ConsoleTraceProcessor แสดง trace แบบ real-time พร้อมสีเพื่อ debug

---

## 12. Tools ทั้ง 16 ตัว

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

## 15. Vector Search REPL — ค้นหาเอกสารด้วย AI

Interactive REPL สำหรับเก็บและค้นหาเอกสารด้วย **Semantic Search** — ค้นหาตามความหมาย ไม่ใช่แค่คำตรงตัว พร้อม autocomplete, command history, และ colored prompt ด้วย `prompt_toolkit`

### สถาปัตยกรรม

```
คำสั่ง add:
  ข้อความ → OpenAI Embedding API → เก็บใน SQLite (text + vector)

คำสั่ง search:
  คำค้นหา → OpenAI Embedding API → ค้นหาด้วย FAISS → แสดงผลจาก SQLite
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
| **Autocomplete** | กด Tab เพื่อเติมคำสั่ง (add, search, list, count, help, quit) |
| **Command History** | กดลูกศรขึ้น/ลงเพื่อเรียกคำสั่งก่อนหน้า |
| **Colored Prompt** | prompt `vector>` แสดงสีฟ้า (cyan) |
| **Ctrl+C / Ctrl+D** | ออกจากโปรแกรมได้ทุกเมื่อ |

### คำสั่งทั้งหมด

| คำสั่ง | คำอธิบาย | ตัวอย่าง |
|--------|----------|----------|
| `add <text>` | เพิ่มเอกสารลง vector store | `add ข้อความที่ต้องการเก็บ` |
| `search <query>` | ค้นหาเอกสารที่คล้ายกัน (top 5) | `search คำค้นหา` |
| `search <query> /N` | กำหนดจำนวนผลลัพธ์ | `search AI /3` |
| `list` | แสดงเอกสารทั้งหมดในฐานข้อมูล | `list` |
| `count` | แสดงจำนวนเอกสาร | `count` |
| `help` | แสดงรายการคำสั่ง | `help` |
| `quit` / `exit` / `q` | ออกจากโปรแกรม | `quit` |

### โครงสร้างโค้ด (`agent/vector_search.py`)

| ส่วน | ฟังก์ชัน | หน้าที่ |
|------|---------|---------|
| **SQLite Layer** | `init_db()` | สร้าง/เปิดฐานข้อมูล SQLite |
| | `store_document()` | บันทึกข้อความ + embedding |
| | `load_all_embeddings()` | โหลด embeddings ทั้งหมดสำหรับสร้าง index |
| | `get_documents_by_ids()` | ดึงข้อความจาก ID |
| | `get_document_count()` | นับจำนวนเอกสาร |
| | `get_all_documents()` | ดึงเอกสารทั้งหมด |
| **Embedding Layer** | `get_embedding()` | เรียก OpenAI API แปลงข้อความเป็น vector |
| **FAISS Layer** | `build_faiss_index()` | สร้าง FAISS index จาก embeddings |
| **Commands** | `cmd_add()` | จัดการคำสั่ง add |
| | `cmd_search()` | จัดการคำสั่ง search |
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
   - `text` — ข้อความต้นฉบับ
   - `embedding` — vector เก็บเป็น BLOB (6,144 bytes ต่อเอกสาร)
   - `created_at` — วันเวลาที่เพิ่ม

### หมายเหตุ

- ต้องมี `OPENAI_API_KEY` ใน `.env` (ใช้ key เดียวกับ Agent)
- ไฟล์ `vector_store.db` สร้างอัตโนมัติเมื่อรัน `add` ครั้งแรก
- Score ยิ่งสูง = ยิ่งตรงกับคำค้นหา (0.0 ถึง 1.0)
- รองรับทุกภาษาที่ OpenAI embedding รองรับ (ไทย, อังกฤษ, จีน, ญี่ปุ่น ฯลฯ)

---

## 16. Concepts สำคัญ

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

ระบบเก็บประวัติสนทนาไว้โดยใช้ `result.to_input_list()` เพื่อแปลงผลลัพธ์ (รวม tool calls และ tool results) กลับเป็น input สำหรับรอบถัดไป ทำให้ Agent จำบริบทได้ตลอดการสนทนา

- **CLI Agent** — เก็บใน `history` list, พิมพ์ `clear` เพื่อล้าง
- **Agent API** — เก็บใน `sessions` dict แยกตาม `session_id` (in-memory, รีสตาร์ทแล้วหาย)

### Streaming

CLI Agent ใช้ `Runner.run_streamed()` เพื่อให้ข้อความแสดงทีละตัวอักษร (token-by-token) ไม่ต้องรอจนตอบเสร็จทั้งหมด

### MCP (Model Context Protocol)

Agent ไม่ได้เรียก GoSaaS API โดยตรง แต่เรียกผ่าน MCP Server ซึ่งทำหน้าที่เป็นตัวกลาง ข้อดีคือ:
- แยก business logic (API calls) ออกจาก Agent logic
- Tools ถูก define ครั้งเดียวใน `mcp-server/tools/` แล้ว Agent เห็นอัตโนมัติ
- สามารถใช้ MCP Server เดียวกันกับ Agent หลายตัวได้

---

## 17. ทดสอบ MCP Server ด้วย MCP Inspector

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

## 18. Logging

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

## 19. Deploy ขึ้น Production

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

## 20. Troubleshooting

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
