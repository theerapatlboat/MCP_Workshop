"""Tests for mcp-server/config.py — api_get, api_post, api_delete helpers.

NOTE: The mcp-server config module is imported by the conftest.py and
exposed via the ``mcp_config`` fixture. We test the helper functions by
calling them through that fixture to avoid module-resolution conflicts
with guardrail/config.py.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def _mock_httpx_client(mock_client_cls, method_name, response):
    """Set up a mock httpx.Client context manager."""
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    getattr(mock_client, method_name).return_value = response
    mock_client_cls.return_value = mock_client
    return mock_client


# ---------------------------------------------------------------------------
# Tests for api_get
# ---------------------------------------------------------------------------

class TestApiGet:

    def test_basic_get_returns_json(self, mcp_config):
        expected = {"data": [{"id": 1}]}
        with patch.object(mcp_config, "httpx") as mock_httpx:
            mc = _mock_httpx_client(mock_httpx.Client, "get", _make_mock_response(expected))
            result = mcp_config.api_get("/product")
        assert result == expected
        mc.get.assert_called_once()

    def test_get_with_params(self, mcp_config):
        expected = {"data": []}
        with patch.object(mcp_config, "httpx") as mock_httpx:
            mc = _mock_httpx_client(mock_httpx.Client, "get", _make_mock_response(expected))
            result = mcp_config.api_get("/product", params={"find": "spice"})
        assert result == expected
        call_kwargs = mc.get.call_args
        assert call_kwargs.kwargs.get("params") == {"find": "spice"} or \
               call_kwargs[1].get("params") == {"find": "spice"}

    def test_get_raises_on_http_error(self, mcp_config):
        with patch.object(mcp_config, "httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock()
            )
            _mock_httpx_client(mock_httpx.Client, "get", mock_resp)
            with pytest.raises(httpx.HTTPStatusError):
                mcp_config.api_get("/nonexistent")

    def test_get_with_none_params(self, mcp_config):
        expected = {"ok": True}
        with patch.object(mcp_config, "httpx") as mock_httpx:
            _mock_httpx_client(mock_httpx.Client, "get", _make_mock_response(expected))
            result = mcp_config.api_get("/test", params=None)
        assert result == expected


# ---------------------------------------------------------------------------
# Tests for api_post
# ---------------------------------------------------------------------------

class TestApiPost:

    def test_basic_post_returns_json(self, mcp_config):
        expected = {"id": 42, "status": "created"}
        with patch.object(mcp_config, "httpx") as mock_httpx:
            _mock_httpx_client(mock_httpx.Client, "post", _make_mock_response(expected))
            result = mcp_config.api_post("/order-draft", {"name": "test"})
        assert result == expected

    def test_post_sends_json_body(self, mcp_config):
        body = {"key": "value"}
        with patch.object(mcp_config, "httpx") as mock_httpx:
            mc = _mock_httpx_client(mock_httpx.Client, "post", _make_mock_response({"ok": True}))
            mcp_config.api_post("/endpoint", body)
        call_kwargs = mc.post.call_args
        assert call_kwargs.kwargs.get("json") == body or \
               call_kwargs[1].get("json") == body

    def test_post_raises_on_http_error(self, mcp_config):
        with patch.object(mcp_config, "httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500", request=MagicMock(), response=MagicMock()
            )
            _mock_httpx_client(mock_httpx.Client, "post", mock_resp)
            with pytest.raises(httpx.HTTPStatusError):
                mcp_config.api_post("/fail", {"data": "bad"})


# ---------------------------------------------------------------------------
# Tests for api_delete
# ---------------------------------------------------------------------------

class TestApiDelete:

    def test_basic_delete_returns_json(self, mcp_config):
        expected = {"success": True}
        with patch.object(mcp_config, "httpx") as mock_httpx:
            _mock_httpx_client(mock_httpx.Client, "delete", _make_mock_response(expected))
            result = mcp_config.api_delete("/order-draft/123")
        assert result == expected

    def test_delete_raises_on_http_error(self, mcp_config):
        with patch.object(mcp_config, "httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock()
            )
            _mock_httpx_client(mock_httpx.Client, "delete", mock_resp)
            with pytest.raises(httpx.HTTPStatusError):
                mcp_config.api_delete("/order-draft/999")

    def test_delete_sends_auth_headers(self, mcp_config):
        with patch.object(mcp_config, "httpx") as mock_httpx:
            mc = _mock_httpx_client(mock_httpx.Client, "delete", _make_mock_response({"ok": True}))
            mcp_config.api_delete("/test")
        call_kwargs = mc.delete.call_args
        assert call_kwargs.kwargs.get("headers") == mcp_config.AUTH_HEADERS or \
               call_kwargs[1].get("headers") == mcp_config.AUTH_HEADERS


# ---------------------------------------------------------------------------
# Tests for module-level constants
# ---------------------------------------------------------------------------

class TestConfigConstants:

    def test_auth_headers_has_authorization(self, mcp_config):
        assert "Authorization" in mcp_config.AUTH_HEADERS

    def test_auth_headers_has_content_type(self, mcp_config):
        assert mcp_config.AUTH_HEADERS["Content-Type"] == "application/json"

    def test_uat_api_url_no_trailing_slash(self, mcp_config):
        assert not mcp_config.UAT_API_URL.endswith("/")
