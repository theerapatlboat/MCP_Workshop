"""Tests for mcp-server/tools/shipment.py — shipping status and shipment details."""

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

class TestShipmentRegistration:

    def test_both_tools_are_registered(self, shipment_tools):
        assert "get_shipping_status" in shipment_tools
        assert "get_shipment" in shipment_tools
        assert len(shipment_tools) == 2


# ---------------------------------------------------------------------------
# get_shipping_status
# ---------------------------------------------------------------------------

class TestGetShippingStatus:

    def test_basic_tracking_code_lookup(self, shipment_tools, mock_api_get):
        expected = {"status": "delivered", "tracking_code": "TH123"}
        mock_api_get.return_value = expected

        result = shipment_tools["get_shipping_status"](code="TH123")

        assert result == expected
        mock_api_get.assert_called_once()
        path, params = mock_api_get.call_args[0]
        assert path == "/shipment/shipping-status"
        assert params["code"] == "TH123"
        assert params["type"] == "auto"
        assert "list" not in params

    def test_explicit_type_tracking_code(self, shipment_tools, mock_api_get):
        mock_api_get.return_value = {}

        shipment_tools["get_shipping_status"](
            code="TRACK001", type="tracking_code"
        )

        params = mock_api_get.call_args[0][1]
        assert params["type"] == "tracking_code"

    def test_explicit_type_order_number(self, shipment_tools, mock_api_get):
        mock_api_get.return_value = {}

        shipment_tools["get_shipping_status"](
            code="ORD-2025-001", type="order_number"
        )

        params = mock_api_get.call_args[0][1]
        assert params["type"] == "order_number"

    def test_list_text_included_when_nonzero(self, shipment_tools, mock_api_get):
        mock_api_get.return_value = {}

        shipment_tools["get_shipping_status"](code="TH123", list_text=1)

        params = mock_api_get.call_args[0][1]
        assert params["list"] == 1

    def test_list_text_excluded_when_zero(self, shipment_tools, mock_api_get):
        mock_api_get.return_value = {}

        shipment_tools["get_shipping_status"](code="TH123", list_text=0)

        params = mock_api_get.call_args[0][1]
        assert "list" not in params

    def test_default_params(self, shipment_tools, mock_api_get):
        """Defaults: type='auto', list_text=0."""
        mock_api_get.return_value = {}

        shipment_tools["get_shipping_status"](code="ABC")

        params = mock_api_get.call_args[0][1]
        assert params["type"] == "auto"
        assert "list" not in params


# ---------------------------------------------------------------------------
# get_shipment
# ---------------------------------------------------------------------------

class TestGetShipment:

    def test_fetches_by_order_draft_id(self, shipment_tools, mock_api_get):
        expected = {"shipment": {"tracking": "TH999"}}
        mock_api_get.return_value = expected

        result = shipment_tools["get_shipment"](
            order_draft_id="68690f09bd2ab611975b4df6"
        )

        assert result == expected
        mock_api_get.assert_called_once_with(
            "/shipment",
            {"order_draft_id": "68690f09bd2ab611975b4df6"},
        )

    def test_different_order_draft_ids(self, shipment_tools, mock_api_get):
        mock_api_get.return_value = {}

        shipment_tools["get_shipment"](order_draft_id="aaa111bbb222ccc333ddd444")

        params = mock_api_get.call_args[0][1]
        assert params["order_draft_id"] == "aaa111bbb222ccc333ddd444"

    def test_propagates_response(self, shipment_tools, mock_api_get):
        mock_api_get.return_value = {
            "data": {
                "id": "ship_001",
                "carrier": "Kerry Express",
                "tracking_code": "KEX123",
            }
        }

        result = shipment_tools["get_shipment"](order_draft_id="abc123def456ghi789jkl012")

        assert result["data"]["carrier"] == "Kerry Express"
        assert result["data"]["tracking_code"] == "KEX123"
