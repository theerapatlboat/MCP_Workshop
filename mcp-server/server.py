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

from mcp.server.fastmcp import FastMCP
from tools import order_draft, product, shipment, report, order, utilities

# ── MCP Server ──────────────────────────────────
mcp = FastMCP("Order Management")

# ── Register all tools ──────────────────────────
order_draft.register(mcp)
product.register(mcp)
shipment.register(mcp)
report.register(mcp)
order.register(mcp)
utilities.register(mcp)

# ── Run ─────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
