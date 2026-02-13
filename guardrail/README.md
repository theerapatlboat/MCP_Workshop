# Guardrail Proxy API

Proxy API ที่กรองข้อความก่อนส่งถึง chatbot โดยข้อความต้องผ่าน **2 ระบบ** ถึงจะไปถึง Agent ได้

```
Webhook (8001) -> Guardrail (8002) -> Agent API (3000) -> MCP (8000)
                      |
                      +-> BLOCKED -> ข้อความปฏิเสธสุภาพ
```

## ระบบกรอง 2 ชั้น

| ระบบ | ไฟล์ | หน้าที่ |
|------|------|---------|
| Vector Similarity | `vector_guard.py` | เช็คว่าหัวข้อตรงกับ allowed topics ไหม (FAISS + cosine similarity) |
| LLM Policy | `llm_guard.py` | เช็คว่าข้อความตาม policy ธุรกิจไหม (GPT-4o-mini ตัดสิน) |

ข้อความต้อง **ผ่านทั้ง 2 ระบบ** ถึงจะส่งต่อให้ chatbot ได้ ทั้ง 2 ระบบทำงาน **พร้อมกัน** (parallel) เพื่อลด latency

## โครงสร้างไฟล์

```
guardrail/
├── main.py           # FastAPI app, POST /guard, orchestration
├── config.py         # ตั้งค่า OpenAI client, env vars, threshold
├── models.py         # Pydantic models (request/response)
├── vector_guard.py   # ระบบที่ 1: Vector similarity (FAISS)
├── llm_guard.py      # ระบบที่ 2: LLM policy (GPT-4o-mini)
├── topics.json       # รายการหัวข้อที่อนุญาต (แก้ไขได้)
├── requirements.txt  # dependencies
└── logs/             # log files (สร้างอัตโนมัติ)
```

## ติดตั้งและใช้งาน

### 1. ติดตั้ง dependencies

```bash
cd guardrail
pip install -r requirements.txt
```

### 2. ตั้งค่า environment variables

ต้องมี `OPENAI_API_KEY` ใน `.env` ที่ root ของโปรเจ็ค (ใช้ตัวเดียวกับ services อื่น)

ตัวแปรเพิ่มเติม (มี default แล้ว ไม่ต้องตั้งก็ได้):

| ตัวแปร | ค่าเริ่มต้น | คำอธิบาย |
|--------|------------|----------|
| `AGENT_API_URL` | `http://localhost:3000/chat` | URL ของ Agent API ที่จะ forward ไป |
| `GUARDRAIL_PORT` | `8002` | Port ของ Guardrail Proxy |
| `VECTOR_SIMILARITY_THRESHOLD` | `0.45` | Threshold สำหรับ cosine similarity (0.0-1.0) |

### 3. เริ่มต้น services (ตามลำดับ)

```bash
# Terminal 1 — MCP Server
cd mcp-server && python server.py

# Terminal 2 — Agent API
cd agent && python agent_api.py

# Terminal 3 — Guardrail Proxy
cd guardrail && python main.py

# Terminal 4 — Webhook (ถ้าต้องการ)
cd webhook && python main.py
```

### 4. เชื่อมต่อ Webhook กับ Guardrail

ใน `webhook/.env` ให้ชี้ `AI_AGENT_URL` ไปที่ guardrail แทน agent โดยตรง:

```
AI_AGENT_URL=http://localhost:8002/guard
```

## ทดสอบ

### ข้อความที่ควรผ่าน

```bash
curl -X POST http://localhost:8002/guard ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"iPhone 16 ราคาเท่าไหร่\", \"session_id\": \"test1\"}"
```

Response:
```json
{
  "session_id": "test1",
  "response": "...(คำตอบจาก agent)...",
  "passed": true,
  "vector_check": {"passed": true, "check_name": "vector_similarity", "score": 0.72, "reason": "สอบถามราคาสินค้า..."},
  "llm_check": {"passed": true, "check_name": "llm_policy", "score": 0.95, "reason": "Product price inquiry"}
}
```

### ข้อความที่ควรถูก block

```bash
curl -X POST http://localhost:8002/guard ^
  -H "Content-Type: application/json" ^
  -d "{\"message\": \"ช่วยเขียนโค้ด Python ให้หน่อย\", \"session_id\": \"test2\"}"
```

Response:
```json
{
  "session_id": "test2",
  "response": "ขออภัยค่ะ ดิฉันเป็นผู้ช่วยขายสินค้ามือถือ...",
  "passed": false,
  "vector_check": {"passed": false, "check_name": "vector_similarity", "score": 0.18, "reason": "..."},
  "llm_check": {"passed": false, "check_name": "llm_policy", "score": 0.95, "reason": "Code generation request"}
}
```

### Health check

```bash
curl http://localhost:8002/health
```

## ปรับแต่ง

### เพิ่ม/แก้ไขหัวข้อที่อนุญาต

แก้ไขไฟล์ `topics.json` แล้ว **restart server** (topics จะถูก embed ใหม่ตอน startup):

```json
{
  "allowed_topics": [
    "หัวข้อใหม่ที่ต้องการเพิ่ม คำที่เกี่ยวข้อง keyword",
    ...
  ]
}
```

แต่ละ topic ควรรวมคำที่เกี่ยวข้องไว้ด้วยกัน (ทั้ง Thai + English) เพื่อให้ embedding ครอบคลุม

### ปรับ threshold

- **ค่าต่ำ (0.25-0.35)**: ผ่อนปรน — ข้อความส่วนใหญ่จะผ่าน vector check, พึ่ง LLM policy เป็นหลัก
- **ค่ากลาง (0.35-0.45)**: สมดุล
- **ค่าสูง (0.45-0.60)**: เข้มงวด — ต้องตรงหัวข้อค่อนข้างชัด

ปรับผ่าน env var ได้โดยไม่ต้องแก้โค้ด:

```
VECTOR_SIMILARITY_THRESHOLD=0.35
```

### แก้ไข policy ของ LLM

แก้ตัวแปร `POLICY_SYSTEM_PROMPT` ใน `llm_guard.py` ซึ่งกำหนดว่าอะไร ALLOWED / BLOCKED

### แก้ไขข้อความปฏิเสธ

แก้ `rejection_message_th` และ `rejection_message_en` ใน `topics.json`

## Error Handling (Fail-Open)

เมื่อระบบมีปัญหา (เช่น OpenAI API ล่ม) จะ **ให้ข้อความผ่านไป** แทนที่จะ block — เพราะการ block ลูกค้าจริงเสียหายมากกว่า

| สถานการณ์ | พฤติกรรม |
|-----------|----------|
| Embedding API ล่ม | ให้ผ่าน, log error |
| LLM API ล่ม | ให้ผ่าน, log error |
| LLM ตอบไม่ใช่ JSON | ให้ผ่าน, log warning |
| Agent API เข้าไม่ได้ | ตอบข้อความ error กลับลูกค้า |
| `topics.json` ไม่มี | server crash ตอน startup (ต้องมี) |

## Logs

Log files อยู่ที่ `guardrail/logs/guardrail.log` (auto-rotate 5MB, เก็บ 3 ไฟล์)

ตัวอย่าง log:
```
2026-02-13 10:00:01 | INFO     | Guard request: session=abc123 message='iPhone 16 ราคาเท่าไหร่'
2026-02-13 10:00:01 | INFO     | Vector check: score=0.7234 threshold=0.45 passed=True topic='สอบถามราคาสินค้า...'
2026-02-13 10:00:01 | INFO     | LLM check: allowed=True confidence=0.95 reason='Product price inquiry'
2026-02-13 10:00:01 | INFO     | PASSED: session=abc123 forwarding to agent
```

## API Reference

### POST /guard

Request:
```json
{
  "message": "ข้อความจากลูกค้า",
  "session_id": "optional_session_id"
}
```

Response:
```json
{
  "session_id": "string | null",
  "response": "คำตอบจาก agent หรือข้อความปฏิเสธ",
  "passed": true,
  "vector_check": {
    "passed": true,
    "check_name": "vector_similarity",
    "score": 0.72,
    "reason": "matched topic text"
  },
  "llm_check": {
    "passed": true,
    "check_name": "llm_policy",
    "score": 0.95,
    "reason": "brief explanation"
  },
  "memory_count": 5
}
```

### GET /health

Response:
```json
{"status": "ok", "service": "guardrail-proxy"}
```
