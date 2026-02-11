"""MCP Server for Order Management — GoSaaS OPEN-API.

This server provides tools for:
─── Order Draft ───
 1. create_order_draft    — สร้างคำสั่งซื้อฉบับร่าง
 2. get_order_draft_meta  — ข้อมูลสำหรับสร้าง order-draft (channels, carriers, payments …)
 3. get_order_draft       — ดึง order draft ตาม id
 4. delete_order_draft    — ลบ order draft ตาม id
 5. attach_order_draft_payment — แนบข้อมูลการชำระเงิน

─── Product ───
 6. list_product           — ค้นหา/แสดงรายการสินค้า
 7. get_product            — ดึงสินค้าตาม ID

─── Shipment ───
 8. get_shipping_status    — ตรวจสอบสถานะจัดส่ง
 9. get_shipment           — ดึงข้อมูล shipment ตาม order_draft_id

─── Report ───
10. get_sales_summary      — รายงานยอดขายตามช่วงเวลา
11. get_sales_summary_today— ยอดขายวันนี้
12. get_sales_filter       — ตัวกรองสำหรับรายงาน

─── Order (WIP) ───
13. get_order_meta         — metadata สำหรับสร้าง order

─── Utilities ───
14. verify_address         — ตรวจสอบข้อมูลที่อยู่ครบถ้วน
15. faq                    — ตอบคำถามที่พบบ่อย (OpenAI)
16. intent_classify        — จัดประเภทข้อความผู้ใช้ (OpenAI)

Run the server:
    python server.py
"""

import os
import httpx
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

load_dotenv()

# ── MCP Server ──────────────────────────────────
mcp = FastMCP("Order Management")

# ── API Config ──────────────────────────────────
UAT_API_KEY = os.getenv("UAT_API_KEY", "")
UAT_API_URL = os.getenv("UAT_API_URL", "").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

AUTH_HEADERS = {
    "Authorization": f"Bearer {UAT_API_KEY}",
    "Content-Type": "application/json",
}


# ── Pydantic Models ────────────────────────────
class AddressVerificationResult(BaseModel):
    """Result of address verification."""
    is_valid: bool = Field(description="Whether the address has sufficient data")
    missing_fields: list[str] = Field(description="List of missing required fields")
    message: str = Field(description="Verification status message")


# ════════════════════════════════════════════════
#  ORDER DRAFT
# ════════════════════════════════════════════════

# ── Tool 1: create_order_draft ──────────────────
@mcp.tool()
def create_order_draft(
    sales_channel_id: int,
    carrier_id: int,
    customer_name: str,
    phone: str,
    address: str,
    sub_district: str,
    district: str,
    province: str,
    postal_code: str,
    items: list[dict],
    payment_method_id: int,
    staff_id: int,
    note: str = "",
) -> dict:
    """
    สร้างคำสั่งซื้อฉบับร่าง (Create Order Draft) ผ่าน GoSaaS API.

    Args:
        sales_channel_id: ID ของช่องทางการขาย
        carrier_id: ID ของขนส่ง
        customer_name: ชื่อลูกค้า
        phone: เบอร์โทรลูกค้า
        address: ที่อยู่จัดส่ง
        sub_district: ตำบล/แขวง
        district: อำเภอ/เขต
        province: จังหวัด
        postal_code: รหัสไปรษณีย์
        items: รายการสินค้า — list of dict with keys: id, sku, quantity, price
        payment_method_id: ID วิธีชำระเงิน
        staff_id: ID พนักงาน
        note: หมายเหตุ (optional)

    Returns:
        API response with order draft details
    """
    body = {
        "salesChannelId": sales_channel_id,
        "carrierId": carrier_id,
        "customerName": customer_name,
        "phone": phone,
        "address": address,
        "subDistrict": sub_district,
        "district": district,
        "province": province,
        "postalCode": postal_code,
        "items": items,
        "paymentMethodId": payment_method_id,
        "staffId": staff_id,
        "note": note,
    }

    with httpx.Client(timeout=15, follow_redirects=True) as client:
        resp = client.post(
            f"{UAT_API_URL}/order-draft",
            headers=AUTH_HEADERS,
            json=body,
        )
        resp.raise_for_status()
        return resp.json()


# ── Tool 2: get_order_draft_meta ────────────────
@mcp.tool()
def get_order_draft_meta() -> dict:
    """
    ดึงข้อมูล meta สำหรับสร้าง order-draft เช่น channels, carriers, payment methods.

    Returns:
        Meta data dict (sales channels, carriers, payment methods, staff …)
    """
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        resp = client.get(
            f"{UAT_API_URL}/order-draft/meta",
            headers=AUTH_HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


# ── Tool 3: get_order_draft ─────────────────────
@mcp.tool()
def get_order_draft(order_draft_id: int) -> dict:
    """
    ดึงข้อมูลคำสั่งซื้อฉบับร่างด้วย ID.

    Args:
        order_draft_id: ID ของ order draft

    Returns:
        Order draft details
    """
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        resp = client.get(
            f"{UAT_API_URL}/order-draft/{order_draft_id}",
            headers=AUTH_HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


# ── Tool 4: delete_order_draft ──────────────────
@mcp.tool()
def delete_order_draft(order_draft_id: int) -> dict:
    """
    ลบคำสั่งซื้อฉบับร่างด้วย ID.

    Args:
        order_draft_id: ID ของ order draft ที่ต้องการลบ

    Returns:
        API response confirming deletion
    """
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        resp = client.delete(
            f"{UAT_API_URL}/order-draft/{order_draft_id}",
            headers=AUTH_HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


# ── Tool 5: attach_order_draft_payment ──────────
@mcp.tool()
def attach_order_draft_payment(
    order_draft_id: int,
    payment_method_id: int,
    bank_account_id: int,
    s3_bucket: str,
    s3_key: str,
    paid: float,
    paid_date: str,
) -> dict:
    """
    แนบข้อมูลการชำระเงินกับ order draft.

    Args:
        order_draft_id: ID ของ order draft
        payment_method_id: ID วิธีชำระเงิน
        bank_account_id: ID บัญชีธนาคาร
        s3_bucket: S3 bucket ของสลิป
        s3_key: S3 key ของสลิป
        paid: จำนวนเงินที่ชำระ
        paid_date: วันที่ชำระเงิน (ISO format, e.g. "2025-01-15T10:30:00Z")

    Returns:
        API response confirming payment attachment
    """
    body = {
        "payment_method_id": payment_method_id,
        "bank_account_id": bank_account_id,
        "s3_bucket": s3_bucket,
        "s3_key": s3_key,
        "paid": paid,
        "paid_date": paid_date,
    }

    with httpx.Client(timeout=15, follow_redirects=True) as client:
        resp = client.post(
            f"{UAT_API_URL}/order-draft/{order_draft_id}/payment",
            headers=AUTH_HEADERS,
            json=body,
        )
        resp.raise_for_status()
        return resp.json()


# ════════════════════════════════════════════════
#  PRODUCT
# ════════════════════════════════════════════════

# ── Tool 6: list_product ────────────────────────
@mcp.tool()
def list_product(find: str = "") -> dict:
    """
    ค้นหา/แสดงรายการสินค้าจาก GoSaaS API.

    Args:
        find: คำค้นหาชื่อสินค้าหรือ SKU (optional — ว่างเปล่า = แสดงทั้งหมด)

    Returns:
        List of products
    """
    params = {}
    if find:
        params["find"] = find

    with httpx.Client(timeout=15, follow_redirects=True) as client:
        resp = client.get(
            f"{UAT_API_URL}/product",
            headers=AUTH_HEADERS,
            params=params,
        )
        resp.raise_for_status()
        raw = resp.json()

    products = []
    for p in raw.get("data", []):
        products.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "sku": p.get("sku"),
            "price": p.get("price"),
            "available_quantity": p.get("quantity", "0"),
            "total_stock": p.get("stock_quantity", "0"),
            "status": p.get("status"),
        })

    return {"success": True, "count": len(products), "products": products}


# ── Tool 7: get_product ─────────────────────────
@mcp.tool()
def get_product(product_id: int) -> dict:
    """
    ดึงสินค้าตาม ID โดยค้นหาจากรายการสินค้าทั้งหมด.

    Args:
        product_id: ID ของสินค้า

    Returns:
        Product details or not-found message
    """
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        resp = client.get(
            f"{UAT_API_URL}/product",
            headers=AUTH_HEADERS,
        )
        resp.raise_for_status()
        data = resp.json()

    for product in data.get("data", []):
        if product.get("id") == product_id:
            return {
                "success": True,
                "product": {
                    "id": product.get("id"),
                    "name": product.get("name"),
                    "sku": product.get("sku"),
                    "barcode": product.get("barcode"),
                    "price": product.get("price"),
                    "original_price": product.get("original_price"),
                    "cost": product.get("cost"),
                    "available_quantity": product.get("quantity", "0"),
                    "reserved_quantity": product.get("reserved_quantity", "0"),
                    "total_stock": product.get("stock_quantity", "0"),
                    "live_quantity": product.get("live_quantity", "0"),
                    "status": product.get("status"),
                    "weight": product.get("weight"),
                    "unit_id": product.get("unit_id"),
                    "description": product.get("description"),
                },
            }

    return {"success": False, "message": f"Product with ID {product_id} not found"}


# ════════════════════════════════════════════════
#  SHIPMENT
# ════════════════════════════════════════════════

# ── Tool 8: get_shipping_status ─────────────────
@mcp.tool()
def get_shipping_status(
    code: str,
    type: str = "auto",
    list_text: int = 0,
) -> dict:
    """
    ตรวจสอบสถานะจัดส่งพัสดุ.

    Args:
        code: tracking code หรือ order number
        type: ประเภทการค้นหา — "auto", "tracking_code", หรือ "order_number"
        list_text: แสดงรายการเป็นข้อความ (0 = ไม่, 1 = ใช่)

    Returns:
        Shipping status details
    """
    params = {"type": type, "code": code}
    if list_text:
        params["list"] = list_text

    with httpx.Client(timeout=15, follow_redirects=True) as client:
        resp = client.get(
            f"{UAT_API_URL}/shipment/shipping-status",
            headers=AUTH_HEADERS,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()


# ── Tool 9: get_shipment ────────────────────────
@mcp.tool()
def get_shipment(order_draft_id: int) -> dict:
    """
    ดึงข้อมูล shipment ตาม order_draft_id.

    Args:
        order_draft_id: ID ของ order draft

    Returns:
        Shipment details
    """
    params = {"order_draft_id": str(order_draft_id)}

    with httpx.Client(timeout=15, follow_redirects=True) as client:
        resp = client.get(
            f"{UAT_API_URL}/shipment",
            headers=AUTH_HEADERS,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()


# ════════════════════════════════════════════════
#  REPORT
# ════════════════════════════════════════════════

# ── Tool 10: get_sales_summary ──────────────────
@mcp.tool()
def get_sales_summary(
    start_date_time: str,
    end_date_time: str,
    channel_type_name: str = "",
    payment_method_name: str = "",
) -> dict:
    """
    ดึงรายงานยอดขายตามช่วงเวลา.

    Args:
        start_date_time: วันเริ่มต้น (ISO format, e.g. "2025-01-01T00:00:00Z")
        end_date_time: วันสิ้นสุด (ISO format, e.g. "2025-01-31T23:59:59Z")
        channel_type_name: กรองตามช่องทาง (optional)
        payment_method_name: กรองตามวิธีชำระเงิน (optional)

    Returns:
        Sales summary data
    """
    params = {
        "startDateTime": start_date_time,
        "endDateTime": end_date_time,
    }
    if channel_type_name:
        params["channelTypeName"] = channel_type_name
    if payment_method_name:
        params["paymentMethodName"] = payment_method_name

    with httpx.Client(timeout=15, follow_redirects=True) as client:
        resp = client.get(
            f"{UAT_API_URL}/report/sales/summary",
            headers=AUTH_HEADERS,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()


# ── Tool 11: get_sales_summary_today ────────────
@mcp.tool()
def get_sales_summary_today() -> dict:
    """
    ดึงรายงานยอดขายภายในวันนี้.

    Returns:
        Today's sales summary data
    """
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        resp = client.get(
            f"{UAT_API_URL}/report/sales/summary-today",
            headers=AUTH_HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


# ── Tool 12: get_sales_filter ───────────────────
@mcp.tool()
def get_sales_filter() -> dict:
    """
    ดึงตัวเลือกตัวกรองสำหรับรายงานยอดขาย (channels, payment methods …).

    Returns:
        Available filter options for sales reports
    """
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        resp = client.get(
            f"{UAT_API_URL}/report/sales/filter",
            headers=AUTH_HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


# ════════════════════════════════════════════════
#  ORDER (WIP)
# ════════════════════════════════════════════════

# ── Tool 13: get_order_meta ─────────────────────
@mcp.tool()
def get_order_meta() -> dict:
    """
    ดึง metadata สำหรับสร้าง order (carriers, channels, payment methods, users, warehouses).

    Returns:
        Order metadata
    """
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        resp = client.get(
            f"{UAT_API_URL}/order/meta",
            headers=AUTH_HEADERS,
        )
        resp.raise_for_status()
        return resp.json()


# ════════════════════════════════════════════════
#  UTILITIES
# ════════════════════════════════════════════════

# ── Tool 14: verify_address ─────────────────────
@mcp.tool()
def verify_address(
    name: str | None = None,
    tel: str | None = None,
    address: str | None = None,
    sub_district: str | None = None,
    district: str | None = None,
    province: str | None = None,
    postal_code: str | None = None,
) -> AddressVerificationResult:
    """
    ตรวจสอบว่าข้อมูลที่อยู่ครบถ้วนสำหรับจัดส่ง.

    Args:
        name: ชื่อลูกค้า
        tel: เบอร์โทร
        address: ที่อยู่
        sub_district: ตำบล/แขวง
        district: อำเภอ/เขต
        province: จังหวัด
        postal_code: รหัสไปรษณีย์

    Returns:
        AddressVerificationResult with validation status and missing fields
    """
    required_fields = {
        "name": name,
        "tel": tel,
        "address": address,
        "sub_district": sub_district,
        "district": district,
        "province": province,
        "postal_code": postal_code,
    }

    missing_fields = [
        field for field, value in required_fields.items()
        if value is None or (isinstance(value, str) and value.strip() == "")
    ]

    is_valid = len(missing_fields) == 0

    if is_valid:
        message = "Address verification passed. All required fields are present."
    else:
        message = f"Address verification failed. Missing fields: {', '.join(missing_fields)}"

    return AddressVerificationResult(
        is_valid=is_valid,
        missing_fields=missing_fields,
        message=message,
    )


# ── Tool 15: faq ────────────────────────────────
@mcp.tool()
def faq(question: str) -> dict:
    """
    ตอบคำถามที่พบบ่อยเกี่ยวกับคำสั่งซื้อ สินค้า และบริการ โดยใช้ AI.

    Args:
        question: คำถามของลูกค้า

    Returns:
        AI-generated answer based on FAQ knowledge
    """
    system_prompt = (
        "You are a helpful customer support assistant for an e-commerce store. "
        "Answer questions about orders, shipping, returns, payments, and products. "
        "Keep answers concise and friendly. Answer in the same language as the question. "
        "If you don't know the answer, say so honestly."
    )

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        max_tokens=500,
    )

    answer = response.choices[0].message.content
    return {"success": True, "question": question, "answer": answer}


# ── Tool 16: intent_classify ────────────────────
@mcp.tool()
def intent_classify(message: str) -> dict:
    """
    จัดประเภท intent ของข้อความผู้ใช้ด้วย AI.

    Possible intents: order, inquiry, complaint, return, tracking, greeting, other

    Args:
        message: ข้อความที่ต้องการจัดประเภท

    Returns:
        Classified intent and confidence
    """
    import json

    system_prompt = (
        "You are an intent classifier. Classify the user message into exactly one intent.\n"
        "Possible intents: order, inquiry, complaint, return, tracking, greeting, other\n\n"
        'Respond in JSON format only: {"intent": "...", "confidence": 0.0-1.0}\n'
        "Do not include any other text."
    )

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        max_tokens=50,
    )

    raw = response.choices[0].message.content.strip()
    try:
        result = json.loads(raw)
        return {
            "success": True,
            "message": message,
            "intent": result.get("intent", "other"),
            "confidence": result.get("confidence", 0.0),
        }
    except json.JSONDecodeError:
        return {
            "success": True,
            "message": message,
            "intent": raw,
            "confidence": 0.0,
        }


# ── Run ─────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
