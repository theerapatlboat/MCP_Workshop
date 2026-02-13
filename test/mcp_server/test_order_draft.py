"""Tests for mcp-server/tools/order_draft.py — 5 order-draft tools."""

import sys
from pathlib import Path
from unittest.mock import patch

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
# Registration sanity check
# ---------------------------------------------------------------------------

class TestOrderDraftRegistration:

    def test_all_five_tools_are_registered(self, order_draft_tools):
        expected = {
            "create_order_draft",
            "get_order_draft_meta",
            "get_order_draft",
            "delete_order_draft",
            "attach_order_draft_payment",
        }
        assert set(order_draft_tools.keys()) == expected


# ---------------------------------------------------------------------------
# create_order_draft
# ---------------------------------------------------------------------------

class TestCreateOrderDraft:

    def test_creates_draft_with_correct_body(self, order_draft_tools, mock_api_post):
        mock_api_post.return_value = {"id": 99, "status": "draft"}

        result = order_draft_tools["create_order_draft"](
            sales_channel_id=1,
            carrier_id=2,
            customer_name="John",
            phone="0800000000",
            address="123 Main St",
            sub_district="Bangrak",
            district="Bangrak",
            province="Bangkok",
            postal_code="10500",
            items=[{"id": 1, "sku": "RG-30", "quantity": 2, "price": 79.0}],
            payment_method_id=1,
            staff_id=5,
        )

        assert result == {"id": 99, "status": "draft"}
        mock_api_post.assert_called_once()
        call_args = mock_api_post.call_args
        assert call_args[0][0] == "/order-draft"

        body = call_args[0][1]
        assert body["salesChannelId"] == 1
        assert body["carrierId"] == 2
        assert body["customerName"] == "John"
        assert body["phone"] == "0800000000"
        assert body["postalCode"] == "10500"
        assert len(body["items"]) == 1
        assert body["paymentMethodId"] == 1
        assert body["staffId"] == 5
        assert body["note"] == ""

    def test_creates_draft_with_note(self, order_draft_tools, mock_api_post):
        mock_api_post.return_value = {"id": 100}

        order_draft_tools["create_order_draft"](
            sales_channel_id=1,
            carrier_id=2,
            customer_name="Jane",
            phone="0811111111",
            address="456 Side St",
            sub_district="Silom",
            district="Bangrak",
            province="Bangkok",
            postal_code="10500",
            items=[],
            payment_method_id=2,
            staff_id=3,
            note="Rush delivery please",
        )

        body = mock_api_post.call_args[0][1]
        assert body["note"] == "Rush delivery please"

    def test_creates_draft_with_multiple_items(self, order_draft_tools, mock_api_post):
        mock_api_post.return_value = {"id": 101}
        items = [
            {"id": 1, "sku": "RG-30", "quantity": 2, "price": 79.0},
            {"id": 2, "sku": "RG-15", "quantity": 5, "price": 45.0},
        ]

        order_draft_tools["create_order_draft"](
            sales_channel_id=1,
            carrier_id=1,
            customer_name="Test",
            phone="0899999999",
            address="789 Rd",
            sub_district="A",
            district="B",
            province="C",
            postal_code="10100",
            items=items,
            payment_method_id=1,
            staff_id=1,
        )

        body = mock_api_post.call_args[0][1]
        assert len(body["items"]) == 2
        assert body["items"][0]["sku"] == "RG-30"
        assert body["items"][1]["sku"] == "RG-15"

    def test_body_maps_camelcase_keys(self, order_draft_tools, mock_api_post):
        """Verify snake_case params are converted to camelCase in the API body."""
        mock_api_post.return_value = {}

        order_draft_tools["create_order_draft"](
            sales_channel_id=10,
            carrier_id=20,
            customer_name="X",
            phone="0",
            address="A",
            sub_district="S",
            district="D",
            province="P",
            postal_code="99999",
            items=[],
            payment_method_id=3,
            staff_id=4,
        )

        body = mock_api_post.call_args[0][1]
        camel_keys = {"salesChannelId", "carrierId", "customerName", "phone",
                      "address", "subDistrict", "district", "province",
                      "postalCode", "items", "paymentMethodId", "staffId", "note"}
        assert set(body.keys()) == camel_keys


# ---------------------------------------------------------------------------
# get_order_draft_meta
# ---------------------------------------------------------------------------

class TestGetOrderDraftMeta:

    def test_returns_meta_data(self, order_draft_tools, mock_api_get):
        expected = {"channels": [1, 2], "carriers": [3]}
        mock_api_get.return_value = expected

        result = order_draft_tools["get_order_draft_meta"]()

        assert result == expected
        mock_api_get.assert_called_once_with("/order-draft/meta")


# ---------------------------------------------------------------------------
# get_order_draft
# ---------------------------------------------------------------------------

class TestGetOrderDraft:

    def test_fetches_draft_by_id(self, order_draft_tools, mock_api_get):
        expected = {"id": 42, "customerName": "Bob"}
        mock_api_get.return_value = expected

        result = order_draft_tools["get_order_draft"](order_draft_id=42)

        assert result == expected
        mock_api_get.assert_called_once_with("/order-draft/42")

    def test_different_ids_produce_different_paths(self, order_draft_tools, mock_api_get):
        mock_api_get.return_value = {}

        order_draft_tools["get_order_draft"](order_draft_id=1)
        assert mock_api_get.call_args[0][0] == "/order-draft/1"

        order_draft_tools["get_order_draft"](order_draft_id=999)
        assert mock_api_get.call_args[0][0] == "/order-draft/999"


# ---------------------------------------------------------------------------
# delete_order_draft
# ---------------------------------------------------------------------------

class TestDeleteOrderDraft:

    def test_deletes_draft_by_id(self, order_draft_tools, mock_api_delete):
        expected = {"success": True}
        mock_api_delete.return_value = expected

        result = order_draft_tools["delete_order_draft"](order_draft_id=55)

        assert result == expected
        mock_api_delete.assert_called_once_with("/order-draft/55")

    def test_propagates_api_response(self, order_draft_tools, mock_api_delete):
        mock_api_delete.return_value = {"deleted": True, "id": 10}

        result = order_draft_tools["delete_order_draft"](order_draft_id=10)
        assert result["deleted"] is True
        assert result["id"] == 10


# ---------------------------------------------------------------------------
# attach_order_draft_payment
# ---------------------------------------------------------------------------

class TestAttachOrderDraftPayment:

    def test_attaches_payment_with_correct_body(self, order_draft_tools, mock_api_post):
        mock_api_post.return_value = {"success": True}

        result = order_draft_tools["attach_order_draft_payment"](
            order_draft_id=42,
            payment_method_id=1,
            bank_account_id=10,
            s3_bucket="my-bucket",
            s3_key="slips/receipt.png",
            paid=500.0,
            paid_date="2025-01-15T10:30:00Z",
        )

        assert result == {"success": True}
        mock_api_post.assert_called_once()

        path = mock_api_post.call_args[0][0]
        assert path == "/order-draft/42/payment"

        body = mock_api_post.call_args[0][1]
        assert body["payment_method_id"] == 1
        assert body["bank_account_id"] == 10
        assert body["s3_bucket"] == "my-bucket"
        assert body["s3_key"] == "slips/receipt.png"
        assert body["paid"] == 500.0
        assert body["paid_date"] == "2025-01-15T10:30:00Z"

    def test_different_order_draft_ids(self, order_draft_tools, mock_api_post):
        mock_api_post.return_value = {}

        order_draft_tools["attach_order_draft_payment"](
            order_draft_id=7,
            payment_method_id=1,
            bank_account_id=1,
            s3_bucket="b",
            s3_key="k",
            paid=100.0,
            paid_date="2025-06-01T00:00:00Z",
        )

        path = mock_api_post.call_args[0][0]
        assert path == "/order-draft/7/payment"

    def test_body_does_not_include_order_draft_id(self, order_draft_tools, mock_api_post):
        """order_draft_id goes into the URL path, not the request body."""
        mock_api_post.return_value = {}

        order_draft_tools["attach_order_draft_payment"](
            order_draft_id=42,
            payment_method_id=1,
            bank_account_id=1,
            s3_bucket="b",
            s3_key="k",
            paid=1.0,
            paid_date="2025-01-01T00:00:00Z",
        )

        body = mock_api_post.call_args[0][1]
        assert "order_draft_id" not in body
        assert "orderDraftId" not in body
