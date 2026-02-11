# Server Guide - Order Management MCP Server

## Dependencies (requirements.txt)

| Package | Version | Description |
|---------|---------|-------------|
| `mcp[cli]` | >= 1.0.0 | Model Context Protocol SDK พร้อม CLI สำหรับสร้าง MCP Server |
| `pydantic` | >= 2.0.0 | Data validation และ structured output |

## การติดตั้ง

```bash
# สร้าง virtual environment (แนะนำ)
python -m venv venv

# เปิดใช้งาน virtual environment
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

## การรัน Server

```bash
# ผ่าน Python โดยตรง
python server.py

# หรือผ่าน uv
uv run server.py
```

Server จะเริ่มทำงานด้วย transport แบบ `streamable-http` (default port: `8000`, endpoint: `/mcp`)

---

## การทดสอบด้วย MCP Inspector

[MCP Inspector](https://github.com/modelcontextprotocol/inspector) เป็น Web UI สำหรับทดสอบและ debug MCP Server โดยไม่ต้องเขียน client code

### Prerequisites

- **Node.js** >= 18 (แนะนำ 22.x)
- ไม่ต้องติดตั้งแยก — ใช้ `npx` รันได้เลย

### ขั้นตอนการใช้งาน

#### 1. เริ่ม server ก่อน

เปิด terminal แรกแล้วรัน server:

```bash
python server.py
```

Server จะรอรับ request ที่ `http://localhost:8000/mcp`

#### 2. เปิด MCP Inspector

เปิด terminal ที่สองแล้วรัน:

```bash
npx @modelcontextprotocol/inspector
```

Inspector จะเปิด Web UI ที่ **http://localhost:6274** ในเบราว์เซอร์อัตโนมัติ

#### 3. เชื่อมต่อกับ server

1. ที่หน้า Inspector เปลี่ยน **Transport Type** เป็น `Streamable HTTP`
2. ใส่ URL: `http://localhost:8000/mcp`
3. กดปุ่ม **Connect**

#### 4. ทดสอบ Tools

1. คลิกแท็บ **Tools** ด้านบน
2. คลิก **List Tools** — จะเห็น `create_order` และ `verify_address`
3. คลิกเลือก tool ที่ต้องการทดสอบ
4. กรอกค่า parameter ในฟอร์มด้านขวา
5. กดปุ่ม **Run Tool** เพื่อดูผลลัพธ์

### ตัวอย่างการทดสอบ

**ทดสอบ `create_order`:**

| Field | ตัวอย่างค่า |
|-------|------------|
| name | `สมชาย ใจดี` |
| tel | `0812345678` |
| address | `123 ถ.สุขุมวิท กรุงเทพฯ 10110` |
| payment_method | `cash_on_delivery` |

**ทดสอบ `verify_address`:**

| Field | ตัวอย่างค่า |
|-------|------------|
| name | `สมชาย ใจดี` |
| tel | `0812345678` |
| provinces | `กรุงเทพมหานคร` |
| postcode | `10110` |

### เปลี่ยน Port (ถ้าจำเป็น)

หาก port default ชนกับ service อื่น:

```bash
# เปลี่ยน port ของ Inspector UI และ proxy
CLIENT_PORT=8080 SERVER_PORT=9000 npx @modelcontextprotocol/inspector
```

### Troubleshooting

| ปัญหา | วิธีแก้ |
|--------|--------|
| Inspector ขึ้น "Connection Error" | ตรวจสอบว่า `server.py` กำลังรันอยู่ และ URL ถูกต้อง |
| Port 6274 หรือ 6277 ถูกใช้งาน | ใช้ `CLIENT_PORT` / `SERVER_PORT` เปลี่ยน port |
| Port 8000 ถูกใช้งาน | ปิด process อื่นที่ใช้ port 8000 หรือแก้ port ใน server.py |

---

## Tools ที่มีใน Server

### 1. `create_order` - สร้างคำสั่งซื้อ

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | ชื่อลูกค้า |
| `tel` | `str` | เบอร์โทรศัพท์ |
| `address` | `str` | ที่อยู่จัดส่ง |
| `payment_method` | `str` | วิธีชำระเงิน (credit_card, cash_on_delivery, bank_transfer) |

**Return:** `OrderResult` - มี `success`, `order_id`, `message`

### 2. `verify_address` - ตรวจสอบที่อยู่

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str \| None` | ชื่อลูกค้า |
| `tel` | `str \| None` | เบอร์โทรศัพท์ |
| `provinces` | `str \| None` | จังหวัด |
| `postcode` | `str \| None` | รหัสไปรษณีย์ |

**Return:** `AddressVerificationResult` - มี `is_valid`, `missing_fields`, `message`
