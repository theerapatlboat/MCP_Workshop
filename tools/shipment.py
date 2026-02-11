"""Shipment tools — shipping status and shipment details."""

from mcp.server.fastmcp import FastMCP
from .config import api_get


def register(mcp: FastMCP) -> None:

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

        return api_get("/shipment/shipping-status", params)

    @mcp.tool()
    def get_shipment(order_draft_id: int) -> dict:
        """
        ดึงข้อมูล shipment ตาม order_draft_id.

        Args:
            order_draft_id: ID ของ order draft

        Returns:
            Shipment details
        """
        return api_get("/shipment", {"order_draft_id": str(order_draft_id)})
