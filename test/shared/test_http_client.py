"""Tests for shared/http_client.py — async HTTP forwarding utility."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from shared.http_client import forward_to_agent


@pytest.mark.asyncio
async def test_forward_to_agent_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "response": "สวัสดีครับ",
        "image_ids": ["IMG_PROD_001"],
        "memory_count": 5,
    }
    mock_response.raise_for_status = MagicMock()

    with patch("shared.http_client.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await forward_to_agent("http://test:3000/chat", "sess1", "hello")

    assert result["response"] == "สวัสดีครับ"
    assert result["image_ids"] == ["IMG_PROD_001"]
    assert result["memory_count"] == 5


@pytest.mark.asyncio
async def test_forward_to_agent_sends_correct_payload():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "ok", "image_ids": [], "memory_count": 0}
    mock_response.raise_for_status = MagicMock()

    with patch("shared.http_client.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        await forward_to_agent("http://test/chat", "s123", "สวัสดี")

        instance.post.assert_called_once_with(
            "http://test/chat",
            json={"session_id": "s123", "message": "สวัสดี"},
            timeout=30,
        )


@pytest.mark.asyncio
async def test_forward_to_agent_reply_key_fallback():
    """When 'response' key missing, falls back to 'reply' key."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"reply": "from reply key"}
    mock_response.raise_for_status = MagicMock()

    with patch("shared.http_client.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await forward_to_agent("http://test/chat", "s1", "hi")

    assert result["response"] == "from reply key"


@pytest.mark.asyncio
async def test_forward_to_agent_both_keys_missing():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_response.raise_for_status = MagicMock()

    with patch("shared.http_client.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await forward_to_agent("http://test/chat", "s1", "hi")

    assert result["response"] == ""


@pytest.mark.asyncio
async def test_forward_to_agent_missing_image_ids():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "text"}
    mock_response.raise_for_status = MagicMock()

    with patch("shared.http_client.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await forward_to_agent("http://test/chat", "s1", "hi")

    assert result["image_ids"] == []


@pytest.mark.asyncio
async def test_forward_to_agent_missing_memory_count():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "text"}
    mock_response.raise_for_status = MagicMock()

    with patch("shared.http_client.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await forward_to_agent("http://test/chat", "s1", "hi")

    assert result["memory_count"] == 0


@pytest.mark.asyncio
async def test_forward_to_agent_custom_timeout():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "ok"}
    mock_response.raise_for_status = MagicMock()

    with patch("shared.http_client.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        await forward_to_agent("http://test/chat", "s1", "hi", timeout=60)

        _, kwargs = instance.post.call_args
        assert kwargs["timeout"] == 60


@pytest.mark.asyncio
async def test_forward_to_agent_http_error_raises():
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error", request=MagicMock(), response=mock_response
    )

    with patch("shared.http_client.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        with pytest.raises(httpx.HTTPStatusError):
            await forward_to_agent("http://test/chat", "s1", "hi")


@pytest.mark.asyncio
async def test_forward_to_agent_network_error_raises():
    with patch("shared.http_client.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.side_effect = httpx.ConnectError("Connection refused")
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        with pytest.raises(httpx.ConnectError):
            await forward_to_agent("http://test/chat", "s1", "hi")


@pytest.mark.asyncio
async def test_forward_to_agent_timeout_raises():
    with patch("shared.http_client.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.side_effect = httpx.ReadTimeout("Timeout")
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        with pytest.raises(httpx.ReadTimeout):
            await forward_to_agent("http://test/chat", "s1", "hi")
