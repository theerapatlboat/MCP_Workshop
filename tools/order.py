"""Order tools — order metadata (WIP)."""

from mcp.server.fastmcp import FastMCP
from config import api_get


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def get_order_meta() -> dict:
        """
        ดึง metadata สำหรับสร้าง order (carriers, channels, payment methods, users, warehouses).

        Returns:
            Order metadata
        """
        return api_get("/order/meta")
