"""MCP Tools package — registers all tools with the MCP server."""

from mcp.server.fastmcp import FastMCP

from . import order_draft, product, shipment, report, order, utilities


def register_all(mcp: FastMCP) -> None:
    """Register every tool module with the given MCP server instance."""
    order_draft.register(mcp)
    product.register(mcp)
    shipment.register(mcp)
    report.register(mcp)
    order.register(mcp)
    utilities.register(mcp)
