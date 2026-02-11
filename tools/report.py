"""Report tools — sales summary and filters."""

from mcp.server.fastmcp import FastMCP
from .config import api_get


def register(mcp: FastMCP) -> None:

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

        return api_get("/report/sales/summary", params)

    @mcp.tool()
    def get_sales_summary_today() -> dict:
        """
        ดึงรายงานยอดขายภายในวันนี้.

        Returns:
            Today's sales summary data
        """
        return api_get("/report/sales/summary-today")

    @mcp.tool()
    def get_sales_filter() -> dict:
        """
        ดึงตัวเลือกตัวกรองสำหรับรายงานยอดขาย (channels, payment methods …).

        Returns:
            Available filter options for sales reports
        """
        return api_get("/report/sales/filter")
