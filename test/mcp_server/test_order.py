"""Tests for mcp-server/tools/order.py — get_order_meta."""

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

class TestOrderRegistration:

    def test_single_tool_registered(self, order_tools):
        assert "get_order_meta" in order_tools
        assert len(order_tools) == 1


# ---------------------------------------------------------------------------
# get_order_meta
# ---------------------------------------------------------------------------

class TestGetOrderMeta:

    def test_returns_meta_data(self, order_tools, mock_api_get):
        expected = {
            "carriers": [{"id": 1, "name": "Kerry"}],
            "channels": [{"id": 1, "name": "Facebook"}],
            "payment_methods": [{"id": 1, "name": "COD"}],
            "users": [],
            "warehouses": [],
        }
        mock_api_get.return_value = expected

        result = order_tools["get_order_meta"]()

        assert result == expected
        mock_api_get.assert_called_once_with("/order/meta")

    def test_no_parameters_passed(self, order_tools, mock_api_get):
        mock_api_get.return_value = {}

        order_tools["get_order_meta"]()

        args = mock_api_get.call_args[0]
        assert len(args) == 1
        assert args[0] == "/order/meta"

    def test_propagates_full_response(self, order_tools, mock_api_get):
        complex_resp = {
            "carriers": [{"id": 1}, {"id": 2}],
            "channels": [{"id": 10}],
            "payment_methods": [],
            "users": [{"id": 100, "name": "Admin"}],
            "warehouses": [{"id": 50, "location": "BKK"}],
        }
        mock_api_get.return_value = complex_resp

        result = order_tools["get_order_meta"]()

        assert len(result["carriers"]) == 2
        assert len(result["users"]) == 1
        assert result["users"][0]["name"] == "Admin"
