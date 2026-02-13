"""Tests for mcp-server/tools/product.py — list_product, get_product."""

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MCP_SERVER_DIR = PROJECT_ROOT / "mcp-server"
for p in [str(PROJECT_ROOT), str(MCP_SERVER_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestProductRegistration:

    def test_both_tools_are_registered(self, product_tools):
        assert "list_product" in product_tools
        assert "get_product" in product_tools
        assert len(product_tools) == 2


# ---------------------------------------------------------------------------
# list_product
# ---------------------------------------------------------------------------

class TestListProduct:

    def test_returns_products_with_correct_structure(self, product_tools, mock_api_get):
        mock_api_get.return_value = {
            "data": [
                {"id": 1, "name": "Spice 30g", "sku": "RG-30",
                 "price": 79.0, "quantity": "10.0",
                 "stock_quantity": "20", "status": "active"},
            ]
        }

        result = product_tools["list_product"]()

        assert result["success"] is True
        assert result["count"] == 1
        assert len(result["products"]) == 1

        p = result["products"][0]
        assert p["id"] == 1
        assert p["name"] == "Spice 30g"
        assert p["sku"] == "RG-30"
        assert p["price"] == 79.0
        assert p["available_quantity"] == 10
        assert p["total_stock"] == "20"
        assert p["status"] == "active"

    def test_empty_find_passes_no_params(self, product_tools, mock_api_get):
        mock_api_get.return_value = {"data": []}

        product_tools["list_product"]()

        mock_api_get.assert_called_once_with("/product", None)

    def test_find_passes_search_param(self, product_tools, mock_api_get):
        mock_api_get.return_value = {"data": []}

        product_tools["list_product"](find="spice")

        mock_api_get.assert_called_once_with("/product", {"find": "spice"})

    def test_handles_null_quantity_as_zero(self, product_tools, mock_api_get):
        mock_api_get.return_value = {
            "data": [
                {"id": 2, "name": "X", "sku": "X", "price": 10,
                 "quantity": None, "stock_quantity": "0", "status": "active"},
            ]
        }

        result = product_tools["list_product"]()
        assert result["products"][0]["available_quantity"] == 0

    def test_handles_negative_quantity_as_zero(self, product_tools, mock_api_get):
        mock_api_get.return_value = {
            "data": [
                {"id": 3, "name": "Y", "sku": "Y", "price": 5,
                 "quantity": "-3.0", "stock_quantity": "0", "status": "active"},
            ]
        }

        result = product_tools["list_product"]()
        assert result["products"][0]["available_quantity"] == 0

    def test_handles_float_quantity(self, product_tools, mock_api_get):
        mock_api_get.return_value = {
            "data": [
                {"id": 4, "name": "Z", "sku": "Z", "price": 10,
                 "quantity": "7.5", "stock_quantity": "10", "status": "active"},
            ]
        }

        result = product_tools["list_product"]()
        assert result["products"][0]["available_quantity"] == 7

    def test_empty_data_returns_zero_count(self, product_tools, mock_api_get):
        mock_api_get.return_value = {"data": []}

        result = product_tools["list_product"]()

        assert result["success"] is True
        assert result["count"] == 0
        assert result["products"] == []

    def test_multiple_products(self, product_tools, mock_api_get):
        mock_api_get.return_value = {
            "data": [
                {"id": 1, "name": "A", "sku": "A1", "price": 10,
                 "quantity": "5", "stock_quantity": "10", "status": "active"},
                {"id": 2, "name": "B", "sku": "B1", "price": 20,
                 "quantity": "3", "stock_quantity": "6", "status": "active"},
                {"id": 3, "name": "C", "sku": "C1", "price": 30,
                 "quantity": "0", "stock_quantity": "0", "status": "inactive"},
            ]
        }

        result = product_tools["list_product"]()

        assert result["count"] == 3
        assert result["products"][0]["id"] == 1
        assert result["products"][1]["id"] == 2
        assert result["products"][2]["id"] == 3


# ---------------------------------------------------------------------------
# get_product
# ---------------------------------------------------------------------------

class TestGetProduct:

    def test_found_product_returns_details(self, product_tools, mock_api_get):
        mock_api_get.return_value = {
            "data": [
                {
                    "id": 1, "name": "Spice 30g", "sku": "RG-30",
                    "barcode": "8851234", "price": 79.0,
                    "original_price": 89.0, "cost": 35.0,
                    "quantity": "10.0", "reserved_quantity": "3",
                    "stock_quantity": "20", "live_quantity": "7",
                    "status": "active", "weight": 0.03,
                    "unit_id": 1, "description": "Spice for soup",
                },
            ]
        }

        result = product_tools["get_product"](product_id=1)

        assert result["success"] is True
        prod = result["product"]
        assert prod["id"] == 1
        assert prod["name"] == "Spice 30g"
        assert prod["sku"] == "RG-30"
        assert prod["barcode"] == "8851234"
        assert prod["price"] == 79.0
        assert prod["original_price"] == 89.0
        assert prod["cost"] == 35.0
        assert prod["available_quantity"] == 10
        assert prod["reserved_quantity"] == "3"
        assert prod["total_stock"] == "20"
        assert prod["live_quantity"] == "7"
        assert prod["status"] == "active"
        assert prod["weight"] == 0.03
        assert prod["unit_id"] == 1
        assert prod["description"] == "Spice for soup"

    def test_not_found_product(self, product_tools, mock_api_get):
        mock_api_get.return_value = {"data": []}

        result = product_tools["get_product"](product_id=999)

        assert result["success"] is False
        assert "999" in result["message"]

    def test_product_with_null_optional_fields(self, product_tools, mock_api_get):
        mock_api_get.return_value = {
            "data": [
                {
                    "id": 2, "name": "Small", "sku": "SM-1",
                    "barcode": None, "price": 45.0,
                    "original_price": None, "cost": None,
                    "quantity": None, "reserved_quantity": "0",
                    "stock_quantity": "0", "live_quantity": "0",
                    "status": "active", "weight": None,
                    "unit_id": None, "description": None,
                },
            ]
        }

        result = product_tools["get_product"](product_id=2)

        assert result["success"] is True
        prod = result["product"]
        assert prod["barcode"] is None
        assert prod["available_quantity"] == 0
        assert prod["weight"] is None

    def test_calls_api_without_params(self, product_tools, mock_api_get):
        """get_product always fetches all products (no ID in URL)."""
        mock_api_get.return_value = {"data": []}

        product_tools["get_product"](product_id=5)

        mock_api_get.assert_called_once_with("/product")

    def test_finds_correct_product_among_many(self, product_tools, mock_api_get):
        mock_api_get.return_value = {
            "data": [
                {"id": 1, "name": "A", "sku": "A1", "price": 10,
                 "quantity": "5", "stock_quantity": "10", "status": "active"},
                {"id": 2, "name": "B", "sku": "B1", "price": 20,
                 "quantity": "3", "stock_quantity": "6", "status": "active"},
                {"id": 3, "name": "C", "sku": "C1", "price": 30,
                 "quantity": "8", "stock_quantity": "15", "status": "active"},
            ]
        }

        result = product_tools["get_product"](product_id=2)

        assert result["success"] is True
        assert result["product"]["id"] == 2
        assert result["product"]["name"] == "B"
