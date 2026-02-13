"""Tests for mcp-server/tools/report.py — sales summary and filter tools."""

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

class TestReportRegistration:

    def test_all_three_tools_are_registered(self, report_tools):
        expected = {"get_sales_summary", "get_sales_summary_today", "get_sales_filter"}
        assert set(report_tools.keys()) == expected


# ---------------------------------------------------------------------------
# get_sales_summary
# ---------------------------------------------------------------------------

class TestGetSalesSummary:

    def test_basic_date_range(self, report_tools, mock_api_get):
        expected = {"total": 15000, "orders": 5}
        mock_api_get.return_value = expected

        result = report_tools["get_sales_summary"](
            start_date_time="2025-01-01T00:00:00Z",
            end_date_time="2025-01-31T23:59:59Z",
        )

        assert result == expected
        mock_api_get.assert_called_once()
        path, params = mock_api_get.call_args[0]
        assert path == "/report/sales/summary"
        assert params["startDateTime"] == "2025-01-01T00:00:00Z"
        assert params["endDateTime"] == "2025-01-31T23:59:59Z"
        assert "channelTypeName" not in params
        assert "paymentMethodName" not in params

    def test_with_channel_filter(self, report_tools, mock_api_get):
        mock_api_get.return_value = {}

        report_tools["get_sales_summary"](
            start_date_time="2025-01-01T00:00:00Z",
            end_date_time="2025-01-31T23:59:59Z",
            channel_type_name="Facebook",
        )

        params = mock_api_get.call_args[0][1]
        assert params["channelTypeName"] == "Facebook"
        assert "paymentMethodName" not in params

    def test_with_payment_filter(self, report_tools, mock_api_get):
        mock_api_get.return_value = {}

        report_tools["get_sales_summary"](
            start_date_time="2025-06-01T00:00:00Z",
            end_date_time="2025-06-30T23:59:59Z",
            payment_method_name="COD",
        )

        params = mock_api_get.call_args[0][1]
        assert params["paymentMethodName"] == "COD"
        assert "channelTypeName" not in params

    def test_with_both_filters(self, report_tools, mock_api_get):
        mock_api_get.return_value = {}

        report_tools["get_sales_summary"](
            start_date_time="2025-01-01T00:00:00Z",
            end_date_time="2025-12-31T23:59:59Z",
            channel_type_name="LINE",
            payment_method_name="Transfer",
        )

        params = mock_api_get.call_args[0][1]
        assert params["channelTypeName"] == "LINE"
        assert params["paymentMethodName"] == "Transfer"

    def test_empty_strings_not_included(self, report_tools, mock_api_get):
        """Empty string filters should NOT be sent to the API."""
        mock_api_get.return_value = {}

        report_tools["get_sales_summary"](
            start_date_time="2025-01-01T00:00:00Z",
            end_date_time="2025-01-31T23:59:59Z",
            channel_type_name="",
            payment_method_name="",
        )

        params = mock_api_get.call_args[0][1]
        assert "channelTypeName" not in params
        assert "paymentMethodName" not in params


# ---------------------------------------------------------------------------
# get_sales_summary_today
# ---------------------------------------------------------------------------

class TestGetSalesSummaryToday:

    def test_returns_todays_summary(self, report_tools, mock_api_get):
        expected = {"total": 500, "orders": 2}
        mock_api_get.return_value = expected

        result = report_tools["get_sales_summary_today"]()

        assert result == expected
        mock_api_get.assert_called_once_with("/report/sales/summary-today")

    def test_no_parameters_sent(self, report_tools, mock_api_get):
        """No arguments should be passed to api_get."""
        mock_api_get.return_value = {}

        report_tools["get_sales_summary_today"]()

        args = mock_api_get.call_args[0]
        assert len(args) == 1  # only the path
        assert args[0] == "/report/sales/summary-today"


# ---------------------------------------------------------------------------
# get_sales_filter
# ---------------------------------------------------------------------------

class TestGetSalesFilter:

    def test_returns_filter_options(self, report_tools, mock_api_get):
        expected = {
            "channels": ["Facebook", "LINE"],
            "payment_methods": ["COD", "Transfer"],
        }
        mock_api_get.return_value = expected

        result = report_tools["get_sales_filter"]()

        assert result == expected
        mock_api_get.assert_called_once_with("/report/sales/filter")

    def test_no_parameters_sent(self, report_tools, mock_api_get):
        mock_api_get.return_value = {}

        report_tools["get_sales_filter"]()

        args = mock_api_get.call_args[0]
        assert len(args) == 1
        assert args[0] == "/report/sales/filter"
