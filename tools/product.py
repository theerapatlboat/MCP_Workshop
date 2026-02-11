"""Product tools — list and get products."""

from mcp.server.fastmcp import FastMCP
from .config import api_get


def register(mcp: FastMCP) -> None:

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

        raw = api_get("/product", params or None)

        products = []
        for p in raw.get("data", []):
            raw_qty = p.get("quantity", 0)
            available = max(0, int(float(raw_qty))) if raw_qty is not None else 0
            products.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "sku": p.get("sku"),
                "price": p.get("price"),
                "available_quantity": available,
                "total_stock": p.get("stock_quantity", "0"),
                "status": p.get("status"),
            })

        return {"success": True, "count": len(products), "products": products}

    @mcp.tool()
    def get_product(product_id: int) -> dict:
        """
        ดึงสินค้าตาม ID โดยค้นหาจากรายการสินค้าทั้งหมด.

        Args:
            product_id: ID ของสินค้า

        Returns:
            Product details or not-found message
        """
        data = api_get("/product")

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
                        "available_quantity": max(0, int(float(product.get("quantity", 0) or 0))),
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
