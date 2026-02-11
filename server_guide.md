# MCP Server for Order Management — คู่มือการใช้งาน

## ภาพรวม

`server.py` เป็น MCP Server (Model Context Protocol) ที่ให้ AI เช่น Claude เรียกใช้เครื่องมือจัดการคำสั่งซื้อได้ 2 ตัว ผ่าน stdio transport

---

## Tools ที่มี

### 1. `create_order` — สร้างคำสั่งซื้อ

| Parameter        | Type   | Required | Description                                              |
| ---------------- | ------ | -------- | -------------------------------------------------------- |
| `name`           | string | Yes      | ชื่อลูกค้า                                               |
| `tel`            | string | Yes      | เบอร์โทรศัพท์                                            |
| `address`        | string | Yes      | ที่อยู่จัดส่ง                                             |
| `payment_method` | string | Yes      | วิธีชำระเงิน (`credit_card`, `cash_on_delivery`, `bank_transfer`) |

**ผลลัพธ์:** `OrderResult` — มี `success`, `order_id` (เช่น `ORD-A1B2C3D4`), `message`

### 2. `verify_address` — ตรวจสอบความครบถ้วนของที่อยู่

| Parameter   | Type           | Required | Description    |
| ----------- | -------------- | -------- | -------------- |
| `name`      | string \| null | No       | ชื่อลูกค้า     |
| `tel`       | string \| null | No       | เบอร์โทรศัพท์  |
| `provinces` | string \| null | No       | จังหวัด        |
| `postcode`  | string \| null | No       | รหัสไปรษณีย์   |

**ผลลัพธ์:** `AddressVerificationResult` — มี `is_valid`, `missing_fields`, `message`

---

## วิธีรัน Server

```bash
# รันตรง
python server.py

# หรือผ่าน uv
uv run server.py
```

Server ทำงานแบบ **stdio transport** (รับ-ส่งข้อมูลผ่าน stdin/stdout)

---

## การเชื่อมต่อกับ AI Client

### Claude Code — ตั้งค่าใน `.mcp.json`

```json
{
  "mcpServers": {
    "order-management": {
      "command": "python",
      "args": ["server.py"],
      "cwd": "C:\\Users\\boatr\\MyBoat\\RealFactory\\ProjectRealFactory\\AI-Workshop"
    }
  }
}
```

### Claude Desktop — ตั้งค่าใน `claude_desktop_config.json`

```json
{
  "mcpServers": {
    "order-management": {
      "command": "python",
      "args": ["C:\\Users\\boatr\\MyBoat\\RealFactory\\ProjectRealFactory\\AI-Workshop\\server.py"]
    }
  }
}
```

---

## Flow การทำงาน

```
ผู้ใช้พิมพ์: "สั่งซื้อสินค้า ชื่อ สมชาย เบอร์ 0812345678"
        │
        ▼
   AI (Claude) รับข้อความ
        │
        ├─► เรียก verify_address(name="สมชาย", tel="0812345678")
        │   └─► ผลลัพธ์: ขาด provinces, postcode → ถามผู้ใช้เพิ่ม
        │
        ▼
   ผู้ใช้ให้ข้อมูลครบ
        │
        ├─► เรียก create_order(name="สมชาย", tel="0812345678",
        │       address="...", payment_method="cash_on_delivery")
        │   └─► ผลลัพธ์: ORD-A1B2C3D4 สร้างสำเร็จ
        │
        ▼
   AI ตอบกลับผู้ใช้: "สั่งซื้อเรียบร้อย เลขที่ ORD-A1B2C3D4"
```

---

## ข้อควรรู้

- **ข้อมูลเก็บใน memory เท่านั้น** — ปิด server แล้วข้อมูลจะหายไป หากใช้งานจริงต้องเชื่อมต่อ database
- **Dependencies** — ต้องติดตั้งก่อนรัน:
  ```bash
  pip install "mcp[cli]" pydantic
  ```
