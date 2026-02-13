# Send Image to User Flow (Facebook Messenger)

สรุป flow การส่งรูปภาพกลับไปให้ user ผ่าน Facebook Messenger อย่างละเอียด

---

## 1. Architecture Overview

ระบบประกอบด้วย 4 services ทำงานร่วมกัน:

```
User (Messenger)
      |
      v
[Webhook]  :8001          รับข้อความจาก Facebook, ส่งข้อความ+รูปกลับ
      |
      v
[Guardrail Proxy]  :8002  ตรวจสอบข้อความ (Vector + LLM policy)
      |
      v
[Agent API]  :3000         AI Agent ตอบคำถาม + แปะ image markers
      |
      v
[MCP Server]  :8000        knowledge_search tool ค้น knowledge base + image_ids
```

---

## 2. Pre-requisite: การเตรียมรูปภาพ (One-time Setup)

ก่อนที่ระบบจะส่งรูปได้ ต้องเตรียมข้อมูลรูปภาพล่วงหน้า 3 ขั้นตอน:

### 2.1 Image Mapping (`storage/image_mapping.txt`)

ไฟล์ JSON กำหนด image_id แต่ละรูป พร้อมชื่อไฟล์และคำอธิบาย:

```json
{
  "IMG_PROD_001": {
    "file": "IMG_PROD_001.jpg",
    "original": "30 กรัม-01.jpg",
    "description": "สินค้าครบ 3 แบบ (ผงเครื่องเทศน้ำข้น, น้ำใส, ผงสามเกลอ) ขนาด 30 กรัม"
  }
}
```

รูปภาพจริงอยู่ที่ `storage/image/` (เช่น `storage/image/IMG_PROD_001.jpg`)

### 2.2 Upload รูปไป Facebook (`webhook/upload_images.py`)

สคริปต์อัปโหลดรูปไป Facebook Attachment Upload API เพื่อได้ reusable attachment_id:

```
POST https://graph.facebook.com/v24.0/me/message_attachments
Content-Type: multipart/form-data
Body:
  message={"attachment":{"type":"image","payload":{"is_reusable":true}}}
  filedata=@storage/image/IMG_PROD_001.jpg
Params:
  access_token=FB_PAGE_ACCESS_TOKEN

Response: {"attachment_id": "2693222324365369"}
```

วิธีรัน: `cd webhook && python upload_images.py`

### 2.3 Attachment ID Mapping (`webhook/fb_attachment_ids.json`)

ผลลัพธ์จากการอัปโหลด — mapping ระหว่าง image_id กับ Facebook attachment_id:

```json
{
  "IMG_PROD_001": "2693222324365369",
  "IMG_PROD_002": "3442378862568291",
  "IMG_REVIEW_001": "1237514705015697",
  "IMG_CERT_001": "1971530966793598",
  "IMG_RECIPE_001": "917789361188388",
  "IMG_MARKETING_001": "1699678674538116"
}
```

ไฟล์นี้จะถูกโหลดตอน Webhook startup (`webhook/main.py:74-82`)

---

## 3. Knowledge Base กับ image_ids

### 3.1 Knowledge Base Data (`storage/ผงเครื่องเทศหอมรักกัน.txt`)

ข้อมูลสินค้า 13 records (JSONL format) แต่ละ record มี `image_ids` กำกับ:

| doc_id | category | image_ids |
|--------|----------|-----------|
| raggan_001 | product_overview | IMG_PROD_001, IMG_MARKETING_001 |
| raggan_003 | certifications | IMG_CERT_001 |
| raggan_004 | recipe (น้ำข้น) | IMG_PROD_002, IMG_RECIPE_002 |
| raggan_006 | recipe (น้ำใส) | IMG_PROD_003, IMG_RECIPE_001 |
| raggan_008 | pricing (30g) | IMG_PROD_002, IMG_PROD_003 |
| raggan_012 | customer_reviews | IMG_REVIEW_001-006 |

### 3.2 Vector Store (`agent/vector_search.py`)

Knowledge base ถูก embed เป็น vectors เก็บใน SQLite + FAISS:
- Model: `text-embedding-3-small` (1536 dimensions)
- Database: `agent/vector_store.db`
- Schema มีคอลัมน์ `image_ids` (JSON string) เก็บคู่กับแต่ละ document

---

## 4. Flow การส่งรูปภาพ (10 ขั้นตอน)

### Step 1: User ส่งข้อความบน Messenger

User พิมพ์ข้อความ เช่น "มีสินค้าอะไรบ้าง" → Facebook ส่ง webhook event มาที่เซิร์ฟเวอร์

### Step 2: Webhook รับข้อความ + ตรวจสอบ (`webhook/main.py:245-267`)

```
POST /webhook
Headers: X-Hub-Signature-256: sha256=...
Body: { "object": "page", "entry": [...] }
```

Webhook ทำ:
1. **Verify signature** — HMAC-SHA256 ด้วย `FB_APP_SECRET` (`main.py:88-95`)
2. **Return 200 ทันที** — ตอบ "EVENT_RECEIVED" เพื่อไม่ให้ Facebook retry (`main.py:267`)
3. **Spawn background task** — `asyncio.create_task()` เพื่อประมวลผลแบบ async (`main.py:265`)

### Step 3: ตรวจ duplicate + ประมวลผล (`webhook/main.py:186-214`)

ใน background task `_process_messaging_event()`:
1. **Skip echo** — ข้ามข้อความที่ bot ส่งเอง (`main.py:194`)
2. **Deduplicate** — ตรวจ message id (mid) ว่าเคยประมวลผลแล้วหรือยัง (TTL 5 นาที) (`main.py:200`)
3. **Extract text** — ดึงข้อความจาก `message.text` (`main.py:205`)

### Step 4: Forward ไป Guardrail Proxy (`webhook/main.py:155-162`)

```python
# webhook/main.py:158
result = await _forward_to_agent(AI_AGENT_URL, sender_id, text)
# AI_AGENT_URL = "http://localhost:8002/guard"
```

ใช้ `shared/http_client.py` ส่ง HTTP POST:
```
POST http://localhost:8002/guard
Body: {"session_id": "<sender_id>", "message": "<user_text>"}
```

### Step 5: Guardrail ตรวจสอบข้อความ (`guardrail/main.py:80-130`)

รัน 2 checks **พร้อมกัน** (parallel via `asyncio.gather`):

1. **Vector Similarity Check** (`guardrail/vector_guard.py`)
   - Embed ข้อความ user → เทียบกับ allowed topics 23 หมวด (FAISS index)
   - ผ่านถ้า similarity score >= threshold (0.25)

2. **LLM Policy Check** (`guardrail/llm_guard.py`)
   - ส่งข้อความไป gpt-4o-mini ตรวจว่าเข้าข่าย allowed/blocked
   - ผ่านถ้า `{"allowed": true}`

**ถ้าไม่ผ่าน** → ตอบข้อความปฏิเสธ (ไม่มี image_ids)
**ถ้าผ่านทั้ง 2** → ไปขั้นตอนถัดไป

### Step 6: Forward ไป Agent API (`guardrail/main.py:132-153`)

```python
# guardrail/main.py:135
result = await _forward_to_agent(AGENT_API_URL, req.session_id, req.message)
# AGENT_API_URL = "http://localhost:3000/chat"
```

ส่ง HTTP POST:
```
POST http://localhost:3000/chat
Body: {"session_id": "<sender_id>", "message": "<user_text>"}
```

### Step 7: Agent เรียก knowledge_search (`agent/agent_api.py:163-212`)

Agent (gpt-4o-mini) ได้รับข้อความ user พร้อม session history แล้ว:

1. Agent ตัดสินใจเรียก MCP tool `knowledge_search` (`mcp-server/tools/hybrid_search.py:19-112`)
2. knowledge_search ทำ **Two-phase hybrid search**:
   - **Phase 1:** ค้น knowledge records (ไม่รวม image_description) — top 5
   - **Phase 2:** ค้น image_description แยก — top 3
   - **Merge:** รวมผลลัพธ์ โดย knowledge มาก่อน
3. **LLM Refinement** — ใช้ gpt-4o-mini กรองผลที่ไม่เกี่ยวข้องออก
4. **Return results** — แต่ละ result มี `image_ids` list:

```json
{
  "success": true,
  "results": [
    {
      "doc_id": "raggan_001",
      "category": "product_overview",
      "title": "Product overview",
      "content": "ผงเครื่องเทศหอมรักกัน มี 2 สูตร...",
      "image_ids": ["IMG_PROD_001", "IMG_MARKETING_001"],
      "score": 0.87
    }
  ]
}
```

### Step 8: Agent สร้างข้อความพร้อม Image Markers

ตาม instructions ใน `agent/agent_config.py:32-34`:

> เมื่อผลลัพธ์จาก knowledge_search มี image_ids ให้แนบรูปภาพโดยใส่ marker `<<IMG:IMAGE_ID>>` ในข้อความ

**กฎ:**
- ใส่ marker **ท้ายข้อความเท่านั้น** ห้ามใส่กลางประโยค
- แนบเฉพาะรูปที่เกี่ยวข้อง **ไม่เกิน 3 รูปต่อข้อความ**
- Deduplicate — ไม่ซ้ำรูป

**ตัวอย่าง output ของ Agent:**
```
ผงเครื่องเทศหอมรักกันมี 2 สูตร:
1. สูตรน้ำข้น — เข้มข้น หอม
2. สูตรน้ำใส — ใส กลมกล่อม

มีขนาด 15g และ 30g ค่ะ <<IMG:IMG_PROD_001>> <<IMG:IMG_MARKETING_001>>
```

### Step 9: Parse Image Markers (`agent/agent_api.py:46-60`)

ก่อน return response, ระบบแยก markers ออกจากข้อความ:

```python
# agent/agent_api.py:46
IMG_MARKER_PATTERN = re.compile(r"<<IMG:(IMG_[A-Z]+_\d+)>>")

# agent/agent_api.py:49-60
def parse_image_markers(text: str) -> tuple[str, list[str]]:
    image_ids = IMG_MARKER_PATTERN.findall(text)          # ["IMG_PROD_001", "IMG_MARKETING_001"]
    clean_text = IMG_MARKER_PATTERN.sub("", text).strip()  # ข้อความที่เอา markers ออกแล้ว
    unique_ids = list(dict.fromkeys(image_ids))             # deduplicate
    return clean_text, unique_ids
```

**Agent API Response (`agent/agent_api.py:226-231`):**
```json
{
  "session_id": "abc123",
  "response": "ผงเครื่องเทศหอมรักกันมี 2 สูตร:\n1. สูตรน้ำข้น...",
  "image_ids": ["IMG_PROD_001", "IMG_MARKETING_001"],
  "memory_count": 5
}
```

ข้อมูลนี้ถูกส่งกลับผ่าน Guardrail (`guardrail/main.py:145-153`) → Webhook โดย `image_ids` ถูกส่งผ่านครบถ้วนทุกชั้น

### Step 10: Webhook ส่งข้อความ + รูปไป Messenger (`webhook/main.py:204-214`)

```python
# webhook/main.py:210-214
reply, image_ids = await forward_to_agent(sender_id, text)
if reply:
    await send_message(sender_id, reply)      # ส่งข้อความก่อน
if image_ids:
    await send_images(sender_id, image_ids)   # ส่งรูปตามหลัง
```

#### 10a. ส่งข้อความ text (`send_message`, `main.py:98-114`)
```
POST https://graph.facebook.com/v24.0/me/messages
Params: access_token=FB_PAGE_ACCESS_TOKEN
Body: {
  "recipient": {"id": "<sender_id>"},
  "message": {"text": "ผงเครื่องเทศหอมรักกันมี 2 สูตร:..."}
}
```

#### 10b. ส่งรูปทีละรูป (`send_images` → `send_image`, `main.py:117-152`)

1. **Lookup** — map image_id → Facebook attachment_id จาก `fb_attachment_ids` dict (โหลดจาก `fb_attachment_ids.json` ตอน startup)
2. **Send** — ส่งแต่ละรูปผ่าน Facebook Send API:

```python
# webhook/main.py:145-152
async def send_images(recipient_id: str, image_ids: list[str]) -> None:
    for image_id in image_ids:
        attachment_id = fb_attachment_ids.get(image_id)
        if not attachment_id:
            logger.warning("No Facebook attachment_id for image %s — skipping", image_id)
            continue
        await send_image(recipient_id, attachment_id)
```

```
POST https://graph.facebook.com/v24.0/me/messages
Params: access_token=FB_PAGE_ACCESS_TOKEN
Body: {
  "recipient": {"id": "<sender_id>"},
  "message": {
    "attachment": {
      "type": "image",
      "payload": {"attachment_id": "2693222324365369"}
    }
  }
}
```

**User เห็นผลลัพธ์:** ข้อความ text 1 bubble + รูปภาพแยกทีละ bubble (สูงสุด 3 รูป)

---

## 5. Image ID Categories

| Prefix | หมวด | ตัวอย่าง | จำนวน |
|--------|------|----------|-------|
| IMG_PROD_* | รูปสินค้า | IMG_PROD_001 - IMG_PROD_005 | 5 |
| IMG_REVIEW_* | รีวิวลูกค้า | IMG_REVIEW_001 - IMG_REVIEW_006 | 6 |
| IMG_CERT_* | ใบรับรอง | IMG_CERT_001 | 1 |
| IMG_RECIPE_* | สูตรอาหาร | IMG_RECIPE_001 - IMG_RECIPE_002 | 2 |
| IMG_MARKETING_* | การตลาด/วิธีใช้ | IMG_MARKETING_001 - IMG_MARKETING_002 | 2 |

**รวม: 16 รูป**

---

## 6. Sequence Diagram

```
User          Facebook       Webhook(:8001)     Guardrail(:8002)    Agent(:3000)       MCP(:8000)
 |                |                |                  |                  |                  |
 |-- ส่งข้อความ ->|                |                  |                  |                  |
 |                |-- POST /webhook -->               |                  |                  |
 |                |                |                  |                  |                  |
 |                |    verify signature                |                  |                  |
 |                |    dedup check (mid)               |                  |                  |
 |                |<-- 200 "EVENT_RECEIVED" --         |                  |                  |
 |                |                |                  |                  |                  |
 |                |         [background task]          |                  |                  |
 |                |                |                  |                  |                  |
 |                |                |-- POST /guard --->|                  |                  |
 |                |                |                  |                  |                  |
 |                |                |          vector check (FAISS)        |                  |
 |                |                |          llm check (gpt-4o-mini)     |                  |
 |                |                |                  |                  |                  |
 |                |                |              [ถ้าผ่าน]               |                  |
 |                |                |                  |-- POST /chat --->|                  |
 |                |                |                  |                  |                  |
 |                |                |                  |          Agent (gpt-4o-mini)         |
 |                |                |                  |                  |                  |
 |                |                |                  |                  |-- knowledge_search ->|
 |                |                |                  |                  |                  |
 |                |                |                  |                  |    hybrid search     |
 |                |                |                  |                  |    (vector+substring)|
 |                |                |                  |                  |    LLM refinement    |
 |                |                |                  |                  |                  |
 |                |                |                  |                  |<- results + image_ids|
 |                |                |                  |                  |                  |
 |                |                |                  |      Agent สร้างข้อความ              |
 |                |                |                  |      + <<IMG:...>> markers            |
 |                |                |                  |                  |                  |
 |                |                |                  |      parse_image_markers()            |
 |                |                |                  |      -> clean_text + image_ids        |
 |                |                |                  |                  |                  |
 |                |                |                  |<-- {response, image_ids} --|          |
 |                |                |<-- {response, image_ids} --|                  |          |
 |                |                |                  |                  |                  |
 |                |         send_message(text)         |                  |                  |
 |                |<-- POST /me/messages (text) --     |                  |                  |
 |<-- ข้อความ text --|            |                  |                  |                  |
 |                |                |                  |                  |                  |
 |                |      send_images(image_ids)        |                  |                  |
 |                |      lookup fb_attachment_ids       |                  |                  |
 |                |                |                  |                  |                  |
 |                |<-- POST /me/messages (image1) --   |                  |                  |
 |<-- รูปที่ 1 ------|            |                  |                  |                  |
 |                |<-- POST /me/messages (image2) --   |                  |                  |
 |<-- รูปที่ 2 ------|            |                  |                  |                  |
 |                |                |                  |                  |                  |
```

---

## 7. สรุปไฟล์ที่เกี่ยวข้อง

| ไฟล์ | บทบาท |
|------|-------|
| `webhook/main.py` | รับ webhook, ส่ง text + image กลับ Messenger |
| `webhook/upload_images.py` | อัปโหลดรูปไป Facebook (one-time) |
| `webhook/fb_attachment_ids.json` | mapping image_id → Facebook attachment_id |
| `guardrail/main.py` | ตรวจสอบข้อความ + forward image_ids |
| `agent/agent_api.py` | Agent endpoint + parse_image_markers() |
| `agent/agent_config.py` | กฎการใส่ <<IMG:...>> markers |
| `mcp-server/tools/hybrid_search.py` | knowledge_search() return image_ids |
| `agent/vector_search.py` | Vector store schema มี image_ids column |
| `shared/http_client.py` | forward_to_agent() ส่งผ่าน image_ids |
| `storage/image_mapping.txt` | image_id → file + description |
| `storage/image/` | ไฟล์รูปภาพจริง |
