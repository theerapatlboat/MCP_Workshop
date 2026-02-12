# Facebook Messenger Webhook - Tutorial

## สารบัญ

1. [ภาพรวม](#ภาพรวม)
2. [สิ่งที่ต้องเตรียม](#สิ่งที่ต้องเตรียม)
3. [ติดตั้งและตั้งค่า](#ติดตั้งและตั้งค่า)
4. [ตั้งค่า Facebook App](#ตั้งค่า-facebook-app)
5. [เปิด Server ด้วย ngrok](#เปิด-server-ด้วย-ngrok)
6. [ลงทะเบียน Webhook กับ Facebook](#ลงทะเบียน-webhook-กับ-facebook)
7. [ทดสอบ Webhook](#ทดสอบ-webhook)
8. [โครงสร้างโค้ด](#โครงสร้างโค้ด)
9. [การทำงานของแต่ละ Endpoint](#การทำงานของแต่ละ-endpoint)
10. [Logging](#logging)
11. [Deploy ขึ้น Production](#deploy-ขึ้น-production)
12. [Troubleshooting](#troubleshooting)

---

## ภาพรวม

Webhook นี้ทำหน้าที่เป็นตัวกลางระหว่าง Facebook Messenger กับ AI Agent:

```
User (Messenger) → Facebook Platform → Webhook (FastAPI) → AI Agent → Webhook → Facebook Send API → User
```

เมื่อผู้ใช้ส่งข้อความผ่าน Messenger → Facebook จะ POST event มาที่ webhook → webhook ตรวจสอบ signature แล้ว forward ข้อความไปยัง AI Agent → รับคำตอบกลับมา → ส่งกลับผู้ใช้ผ่าน Facebook Send API

---

## สิ่งที่ต้องเตรียม

- **Python 3.10+**
- **Facebook Developer Account** — สร้างได้ที่ https://developers.facebook.com
- **Facebook Page** — Page ที่จะผูกกับ Bot
- **ngrok** (สำหรับ dev) — ใช้เปิด tunnel ให้ Facebook เข้าถึง localhost ได้
- **AI Agent Server** — endpoint ที่รับ POST `/chat` แล้วตอบกลับ

---

## ติดตั้งและตั้งค่า

### 1. ติดตั้ง dependencies

```bash
cd webhook
pip install -r requirements.txt
```

### 2. สร้างไฟล์ `.env`

```bash
cp .env.example .env
```

แก้ไขค่าในไฟล์ `.env`:

```env
FB_VERIFY_TOKEN=my_secret_verify_token_123
FB_APP_SECRET=abc123def456...
FB_PAGE_ACCESS_TOKEN=EAAxxxxxxx...
AI_AGENT_URL=http://localhost:8000/chat
```

| ตัวแปร | คำอธิบาย | หาได้จาก |
|--------|----------|----------|
| `FB_VERIFY_TOKEN` | Token ที่คุณตั้งเองสำหรับ verify webhook (คิดขึ้นมาเอง) | ตั้งเองเลย |
| `FB_APP_SECRET` | App Secret ของ Facebook App | Facebook App Dashboard → Settings → Basic → App Secret |
| `FB_PAGE_ACCESS_TOKEN` | Page Access Token สำหรับส่งข้อความ | Facebook App Dashboard → Messenger → Settings → Token Generation |
| `AI_AGENT_URL` | URL ของ AI Agent endpoint | ขึ้นอยู่กับ AI Agent ที่คุณใช้ |

### 3. รัน Server

```bash
python main.py
```

Server จะรันที่ `http://localhost:8001`

---

## ตั้งค่า Facebook App

### ขั้นตอนที่ 1: สร้าง Facebook App

1. ไปที่ https://developers.facebook.com/apps
2. กด **Create App**
3. เลือก **Business** → **Next**
4. ตั้งชื่อ App แล้วกด **Create App**

### ขั้นตอนที่ 2: เพิ่ม Messenger Product

1. ในหน้า App Dashboard กด **Add Product**
2. เลือก **Messenger** → **Set Up**

### ขั้นตอนที่ 3: สร้าง Page Access Token

1. ไปที่ **Messenger → Settings → Access Tokens**
2. กด **Add or Remove Pages** แล้วเลือก Facebook Page ที่ต้องการ
3. กด **Generate Token** แล้วคัดลอก token ไปใส่ใน `.env` ที่ `FB_PAGE_ACCESS_TOKEN`

### ขั้นตอนที่ 4: หา App Secret

1. ไปที่ **Settings → Basic**
2. กด **Show** ที่ช่อง App Secret แล้วคัดลอกไปใส่ใน `.env` ที่ `FB_APP_SECRET`

---

## เปิด Server ด้วย ngrok

Facebook ต้องเข้าถึง webhook ผ่าน HTTPS ดังนั้นตอน dev ต้องใช้ ngrok:

### 1. ติดตั้ง ngrok

ดาวน์โหลดจาก https://ngrok.com/download แล้ว sign up เพื่อรับ auth token

```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

### 2. เปิด tunnel

```bash
ngrok http 8001
```

จะได้ URL ประมาณนี้:

```
Forwarding  https://abcd-1234.ngrok-free.app → http://localhost:8001
```

จด URL นี้ไว้ใช้ในขั้นตอนต่อไป (เช่น `https://abcd-1234.ngrok-free.app`)

---

## ลงทะเบียน Webhook กับ Facebook

### 1. ตั้งค่า Webhook URL

1. ไปที่ **Messenger → Settings → Webhooks**
2. กด **Add Callback URL**
3. ใส่ข้อมูล:
   - **Callback URL**: `https://abcd-1234.ngrok-free.app/webhook`
   - **Verify Token**: ค่าเดียวกับที่ตั้งไว้ใน `FB_VERIFY_TOKEN`
4. กด **Verify and Save**

ถ้าทุกอย่างถูกต้อง Facebook จะส่ง GET request มาที่ `/webhook` แล้ว verify สำเร็จ

### 2. Subscribe to Events

เลือก Webhook Fields ที่ต้องการ:
- **messages** — รับข้อความจากผู้ใช้
- **messaging_postbacks** — รับ postback จากปุ่ม
- **messaging_optins** — รับ opt-in events

### 3. Subscribe Page

1. ในส่วน **Webhooks** เลือก Page ที่ต้องการ
2. กด **Subscribe** เพื่อเชื่อม Page กับ Webhook

---

## ทดสอบ Webhook

### ทดสอบ Verify (GET)

```bash
curl "http://localhost:8001/webhook?hub.mode=subscribe&hub.verify_token=my_secret_verify_token_123&hub.challenge=1234567890"
```

ผลลัพธ์ที่ถูกต้อง: `1234567890`

### ทดสอบรับ Event (POST)

```bash
curl -X POST http://localhost:8001/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "object": "page",
    "entry": [{
      "id": "PAGE_ID",
      "time": 1234567890,
      "messaging": [{
        "sender": {"id": "USER_ID"},
        "recipient": {"id": "PAGE_ID"},
        "timestamp": 1234567890,
        "message": {
          "mid": "mid.1234",
          "text": "สวัสดี"
        }
      }]
    }]
  }'
```

ผลลัพธ์ที่ถูกต้อง: `EVENT_RECEIVED`

### ทดสอบจริงผ่าน Messenger

1. เปิด Facebook Page ที่ผูกไว้
2. กดปุ่ม **Send Message** หรือไปที่ Messenger แล้วค้นหาชื่อ Page
3. พิมพ์ข้อความอะไรก็ได้
4. ดูที่ console และ `logs/webhook.log` จะเห็น log ของข้อความที่เข้ามา

---

## โครงสร้างโค้ด

```
webhook/
├── main.py              # FastAPI application หลัก
├── requirements.txt     # Python dependencies
├── .env.example         # ตัวอย่างไฟล์ environment variables
├── .env                 # ค่า config จริง (ไม่ commit)
├── logs/
│   └── webhook.log      # ไฟล์ log (สร้างอัตโนมัติ)
├── static/
│   ├── privacy.html     # หน้า Privacy Policy
│   └── terms.html       # หน้า Terms of Service
└── TUTORIAL.md          # ไฟล์นี้
```

---

## การทำงานของแต่ละ Endpoint

### `GET /webhook` — Verification

Facebook จะเรียก endpoint นี้ตอนลงทะเบียน webhook เพื่อตรวจสอบว่าเป็นเซิร์ฟเวอร์ของเราจริง

```
GET /webhook?hub.mode=subscribe&hub.verify_token=xxx&hub.challenge=123
```

- ตรวจสอบว่า `hub.mode` = `"subscribe"`
- ตรวจสอบว่า `hub.verify_token` ตรงกับค่า `FB_VERIFY_TOKEN` ใน `.env`
- ถ้าถูกต้อง → return `hub.challenge`
- ถ้าไม่ถูกต้อง → return `403 Forbidden`

### `POST /webhook` — รับ Events

Facebook จะ POST events มาที่นี่ทุกครั้งที่มีข้อความใหม่

**ลำดับการทำงาน:**

1. **ตรวจ Signature** — ตรวจ header `X-Hub-Signature-256` ด้วย HMAC SHA-256 กับ `FB_APP_SECRET` เพื่อยืนยันว่า request มาจาก Facebook จริง
2. **Parse Events** — แกะ JSON body เพื่อดึง messaging events
3. **กรอง Echo** — ข้าม messages ที่มี `is_echo: true` (ข้อความที่ bot ส่งออกไปเอง)
4. **Forward ไป AI Agent** — ส่งข้อความผู้ใช้ไป `POST AI_AGENT_URL` แล้วรอคำตอบ
5. **ตอบกลับผู้ใช้** — ส่งคำตอบกลับผ่าน Facebook Send API
6. **Return** — ตอบ `EVENT_RECEIVED` เสมอ (Facebook requirement)

### `GET /privacy` — Privacy Policy

หน้า Privacy Policy สำหรับ Facebook App Review (จำเป็นต้องมีเพื่อให้ App ผ่าน review)

### `GET /terms` — Terms of Service

หน้า Terms of Service สำหรับ Facebook App Review

---

## Logging

ระบบ log จะบันทึกทั้ง console และไฟล์:

- **Console** — เห็นทันทีตอนรัน server
- **File** — บันทึกที่ `logs/webhook.log`
  - ไฟล์ log จะ rotate อัตโนมัติเมื่อถึง 5 MB
  - เก็บไฟล์เก่าไว้สูงสุด 3 ไฟล์ (`webhook.log.1`, `.2`, `.3`)

**รูปแบบ log:**

```
2026-02-12 10:30:45,123 | INFO     | Message from 123456 to 789012: สวัสดี
2026-02-12 10:30:46,456 | INFO     | Message sent to 123456
```

**ดู log แบบ real-time:**

```bash
# Windows PowerShell
Get-Content logs/webhook.log -Wait

# Linux/macOS
tail -f logs/webhook.log
```

---

## Deploy ขึ้น Production

ตอน deploy จริงไม่ต้องใช้ ngrok แล้ว ใช้ server จริงแทน

### ตัวอย่าง: Deploy ด้วย Docker

สร้างไฟล์ `Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

```bash
docker build -t fb-webhook .
docker run -d --env-file .env -p 8001:8001 fb-webhook
```

### หลัง Deploy

1. เปลี่ยน Webhook Callback URL ใน Facebook App Dashboard เป็น URL ของ server จริง เช่น `https://yourdomain.com/webhook`
2. ใส่ URL ของ Privacy Policy และ Terms ใน **Settings → Basic**:
   - Privacy Policy URL: `https://yourdomain.com/privacy`
   - Terms of Service URL: `https://yourdomain.com/terms`

---

## Troubleshooting

### Webhook verify ไม่ผ่าน

- ตรวจสอบว่า `FB_VERIFY_TOKEN` ใน `.env` ตรงกับค่าที่กรอกใน Facebook Dashboard
- ตรวจสอบว่า server รันอยู่และ ngrok tunnel เปิดอยู่
- ดู log ว่ามี request เข้ามาไหม

### ส่งข้อความแล้วไม่ได้คำตอบ

- ตรวจสอบว่า `FB_PAGE_ACCESS_TOKEN` ถูกต้องและยังไม่หมดอายุ
- ตรวจสอบว่า AI Agent server รันอยู่ที่ `AI_AGENT_URL`
- ดู log จะเห็น error ถ้า AI Agent หรือ Send API มีปัญหา

### Signature verification failed

- ตรวจสอบว่า `FB_APP_SECRET` ใน `.env` ตรงกับ App Secret ใน Facebook Dashboard
- ถ้าทดสอบด้วย curl โดยไม่มี signature ให้เคลียร์ค่า `FB_APP_SECRET` ออกก่อน (ระบบจะข้าม verification)

### ข้อความซ้ำ (echo)

- ระบบจะข้าม message ที่มี `is_echo: true` อัตโนมัติ
- ถ้ายังเห็นข้อความซ้ำ ตรวจสอบว่าไม่ได้ subscribe webhook ซ้ำ

### Log ไฟล์ไม่สร้าง

- ตรวจสอบ permission ของโฟลเดอร์ `logs/`
- โฟลเดอร์จะถูกสร้างอัตโนมัติตอนรัน server
