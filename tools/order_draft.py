"""Order Draft tools — create, get, delete, attach payment."""

from mcp.server.fastmcp import FastMCP
from .config import api_get, api_post, api_delete


def register(mcp: FastMCP) -> None:

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
        return api_post("/order-draft", body)

    @mcp.tool()
    def get_order_draft_meta() -> dict:
        """
        ดึงข้อมูล meta สำหรับสร้าง order-draft เช่น channels, carriers, payment methods.

        Returns:
            Meta data dict (sales channels, carriers, payment methods, staff …)
        """
        return api_get("/order-draft/meta")

    @mcp.tool()
    def get_order_draft(order_draft_id: int) -> dict:
        """
        ดึงข้อมูลคำสั่งซื้อฉบับร่างด้วย ID.

        Args:
            order_draft_id: ID ของ order draft

        Returns:
            Order draft details
        """
        return api_get(f"/order-draft/{order_draft_id}")

    @mcp.tool()
    def delete_order_draft(order_draft_id: int) -> dict:
        """
        ลบคำสั่งซื้อฉบับร่างด้วย ID.

        Args:
            order_draft_id: ID ของ order draft ที่ต้องการลบ

        Returns:
            API response confirming deletion
        """
        return api_delete(f"/order-draft/{order_draft_id}")

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
        return api_post(f"/order-draft/{order_draft_id}/payment", body)
