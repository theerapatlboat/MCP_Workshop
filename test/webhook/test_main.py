"""Tests for webhook/main.py — Facebook Messenger webhook server.

Covers:
  - verify_signature (valid, invalid, missing header)
  - _is_duplicate (first/second occurrence, cleanup)
  - send_message, send_image, send_images, send_typing_indicator
  - forward_to_agent
  - GET /webhook verification endpoint
  - POST /webhook receive endpoint
  - Debounce system (enqueue, process, combine messages, max buffer/chars/wait)
  - Static pages (/privacy, /terms)
"""

import asyncio
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# Path setup (conftest.py already ensures webhook dir is at sys.path[0])
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WEBHOOK_DIR = PROJECT_ROOT / "webhook"
for p in [str(WEBHOOK_DIR), str(PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Import webhook module — conftest guarantees the right "main" is loaded
import main as webhook_main
from main import (
    app,
    verify_signature,
    _is_duplicate,
    send_message,
    send_image,
    send_images,
    send_typing_indicator,
    forward_to_agent,
    _debounce_enqueue,
    _debounce_process,
    _debounce_wait_and_process,
    _UserDebounceState,
    GRAPH_API_URL,
)

# ---------------------------------------------------------------------------
# Test constants (must match conftest.py values)
# ---------------------------------------------------------------------------
TEST_FB_APP_SECRET = "test-fb-app-secret"
TEST_FB_VERIFY_TOKEN = "test-fb-verify-token"
TEST_FB_PAGE_ACCESS_TOKEN = "test-fb-page-token"
TEST_AI_AGENT_URL = "http://localhost:3000/chat"
TEST_SENDER_ID = "1234567890"
TEST_RECIPIENT_ID = "9876543210"
TEST_MID = "mid.1234567890"


def compute_fb_signature(payload: bytes, secret: str = TEST_FB_APP_SECRET) -> str:
    """Compute a valid X-Hub-Signature-256 header value."""
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


# ===================================================================
# verify_signature
# ===================================================================
class TestVerifySignature:
    """Tests for the HMAC SHA-256 signature verification."""

    def test_valid_signature(self):
        payload = b'{"test": "data"}'
        sig = compute_fb_signature(payload)
        assert verify_signature(payload, sig) is True

    def test_invalid_signature(self):
        payload = b'{"test": "data"}'
        assert verify_signature(payload, "sha256=badhash") is False

    def test_missing_header_empty_string(self):
        payload = b'{"test": "data"}'
        assert verify_signature(payload, "") is False

    def test_missing_sha256_prefix(self):
        payload = b'{"test": "data"}'
        sig_hex = hmac.new(
            TEST_FB_APP_SECRET.encode(), payload, hashlib.sha256
        ).hexdigest()
        # Missing "sha256=" prefix
        assert verify_signature(payload, sig_hex) is False

    def test_wrong_secret_produces_invalid(self):
        payload = b'{"test": "data"}'
        wrong_sig = compute_fb_signature(payload, secret="wrong-secret")
        assert verify_signature(payload, wrong_sig) is False

    def test_empty_payload(self):
        payload = b""
        sig = compute_fb_signature(payload)
        assert verify_signature(payload, sig) is True

    def test_unicode_payload(self):
        payload = json.dumps({"msg": "Hello"}).encode("utf-8")
        sig = compute_fb_signature(payload)
        assert verify_signature(payload, sig) is True

    def test_none_signature(self):
        payload = b'{"test": "data"}'
        assert verify_signature(payload, None) is False


# ===================================================================
# _is_duplicate
# ===================================================================
class TestIsDuplicate:
    """Tests for message deduplication."""

    def test_first_occurrence_returns_false(self):
        assert _is_duplicate("mid.new.001") is False

    def test_second_occurrence_returns_true(self):
        _is_duplicate("mid.dup.002")
        assert _is_duplicate("mid.dup.002") is True

    def test_different_mids_are_independent(self):
        assert _is_duplicate("mid.a") is False
        assert _is_duplicate("mid.b") is False
        assert _is_duplicate("mid.a") is True
        assert _is_duplicate("mid.b") is True

    def test_stores_timestamp(self):
        before = time.time()
        _is_duplicate("mid.ts.001")
        after = time.time()
        ts = webhook_main._seen_mids["mid.ts.001"]
        assert before <= ts <= after

    def test_cleanup_expired_entries(self):
        """Expired entries are cleaned when dict exceeds 100 items."""
        old_time = time.time() - 600  # 10 minutes ago (> 5 min TTL)
        for i in range(101):
            webhook_main._seen_mids[f"mid.old.{i}"] = old_time

        result = _is_duplicate("mid.trigger")
        assert result is False
        # Expired entries should be removed
        assert "mid.old.0" not in webhook_main._seen_mids
        # New entry should be present
        assert "mid.trigger" in webhook_main._seen_mids

    def test_no_cleanup_under_threshold(self):
        """No cleanup when dict has <= 100 entries."""
        old_time = time.time() - 600
        for i in range(50):
            webhook_main._seen_mids[f"mid.old.{i}"] = old_time

        _is_duplicate("mid.new")
        # Old entries remain because threshold not met
        assert "mid.old.0" in webhook_main._seen_mids

    def test_cleanup_keeps_non_expired(self):
        """Cleanup only removes expired entries, keeps recent ones."""
        old_time = time.time() - 600
        for i in range(101):
            webhook_main._seen_mids[f"mid.old.{i}"] = old_time
        # Add one fresh entry
        webhook_main._seen_mids["mid.fresh"] = time.time()

        _is_duplicate("mid.trigger2")
        assert "mid.fresh" in webhook_main._seen_mids
        assert "mid.trigger2" in webhook_main._seen_mids
        assert "mid.old.50" not in webhook_main._seen_mids


# ===================================================================
# send_message
# ===================================================================
class TestSendMessage:
    """Tests for the Facebook Send API text message helper."""

    @pytest.mark.asyncio
    async def test_send_message_success(self, mock_httpx_post):
        instance, mock_resp = mock_httpx_post
        await send_message(TEST_SENDER_ID, "Hello!")
        instance.post.assert_called_once()
        call_kwargs = instance.post.call_args
        assert call_kwargs.args[0] == GRAPH_API_URL
        assert call_kwargs.kwargs["json"]["recipient"]["id"] == TEST_SENDER_ID
        assert call_kwargs.kwargs["json"]["message"]["text"] == "Hello!"
        assert call_kwargs.kwargs["params"]["access_token"] == TEST_FB_PAGE_ACCESS_TOKEN

    @pytest.mark.asyncio
    async def test_send_message_includes_timeout(self, mock_httpx_post):
        instance, _ = mock_httpx_post
        await send_message(TEST_SENDER_ID, "test")
        assert instance.post.call_args.kwargs["timeout"] == 10

    @pytest.mark.asyncio
    async def test_send_message_api_error_logged(self, mock_httpx_post):
        instance, mock_resp = mock_httpx_post
        mock_resp.status_code = 400
        mock_resp.text = "Bad Request"
        await send_message(TEST_SENDER_ID, "fail")
        # Should not raise, just log error
        instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_empty_text(self, mock_httpx_post):
        instance, _ = mock_httpx_post
        await send_message(TEST_SENDER_ID, "")
        payload = instance.post.call_args.kwargs["json"]
        assert payload["message"]["text"] == ""


# ===================================================================
# send_image
# ===================================================================
class TestSendImage:
    """Tests for the Facebook Send API image attachment helper."""

    @pytest.mark.asyncio
    async def test_send_image_success(self, mock_httpx_post):
        instance, _ = mock_httpx_post
        result = await send_image(TEST_SENDER_ID, "attach_001")
        assert result is True
        payload = instance.post.call_args.kwargs["json"]
        assert payload["recipient"]["id"] == TEST_SENDER_ID
        assert payload["message"]["attachment"]["type"] == "image"
        assert payload["message"]["attachment"]["payload"]["attachment_id"] == "attach_001"

    @pytest.mark.asyncio
    async def test_send_image_failure_returns_false(self, mock_httpx_post):
        instance, mock_resp = mock_httpx_post
        mock_resp.status_code = 400
        mock_resp.text = "Bad attachment"
        result = await send_image(TEST_SENDER_ID, "bad_attach")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_image_uses_correct_url(self, mock_httpx_post):
        instance, _ = mock_httpx_post
        await send_image(TEST_SENDER_ID, "attach_002")
        assert instance.post.call_args.args[0] == GRAPH_API_URL

    @pytest.mark.asyncio
    async def test_send_image_uses_access_token(self, mock_httpx_post):
        instance, _ = mock_httpx_post
        await send_image(TEST_SENDER_ID, "attach_002")
        assert instance.post.call_args.kwargs["params"]["access_token"] == TEST_FB_PAGE_ACCESS_TOKEN


# ===================================================================
# send_images
# ===================================================================
class TestSendImages:
    """Tests for sending multiple images via attachment ID lookup."""

    @pytest.mark.asyncio
    async def test_send_images_all_found(self, mock_httpx_post):
        instance, _ = mock_httpx_post
        await send_images(TEST_SENDER_ID, ["IMG_001", "IMG_002"])
        assert instance.post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_images_skips_missing(self, mock_httpx_post):
        instance, _ = mock_httpx_post
        await send_images(TEST_SENDER_ID, ["IMG_001", "IMG_MISSING"])
        # Only IMG_001 should be sent
        assert instance.post.call_count == 1

    @pytest.mark.asyncio
    async def test_send_images_all_missing(self, mock_httpx_post):
        instance, _ = mock_httpx_post
        await send_images(TEST_SENDER_ID, ["NOPE_1", "NOPE_2"])
        instance.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_images_empty_list(self, mock_httpx_post):
        instance, _ = mock_httpx_post
        await send_images(TEST_SENDER_ID, [])
        instance.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_images_sends_correct_attachment_ids(self, mock_httpx_post):
        instance, _ = mock_httpx_post
        await send_images(TEST_SENDER_ID, ["IMG_001", "IMG_003"])
        calls = instance.post.call_args_list
        att_ids = [
            c.kwargs["json"]["message"]["attachment"]["payload"]["attachment_id"]
            for c in calls
        ]
        assert att_ids == ["attach_001", "attach_003"]


# ===================================================================
# send_typing_indicator
# ===================================================================
class TestSendTypingIndicator:
    """Tests for the typing indicator sender action."""

    @pytest.mark.asyncio
    async def test_sends_typing_on(self, mock_httpx_post):
        instance, _ = mock_httpx_post
        await send_typing_indicator(TEST_SENDER_ID)
        payload = instance.post.call_args.kwargs["json"]
        assert payload["sender_action"] == "typing_on"
        assert payload["recipient"]["id"] == TEST_SENDER_ID

    @pytest.mark.asyncio
    async def test_timeout_is_5_seconds(self, mock_httpx_post):
        instance, _ = mock_httpx_post
        await send_typing_indicator(TEST_SENDER_ID)
        assert instance.post.call_args.kwargs["timeout"] == 5

    @pytest.mark.asyncio
    async def test_exception_is_suppressed(self):
        """Network errors should not propagate."""
        with patch.object(webhook_main, "httpx") as mock_httpx_mod:
            instance = AsyncMock()
            instance.post.side_effect = httpx.ConnectError("Connection refused")
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_httpx_mod.AsyncClient.return_value = instance
            # Should not raise
            await send_typing_indicator(TEST_SENDER_ID)


# ===================================================================
# forward_to_agent
# ===================================================================
class TestForwardToAgent:
    """Tests for the agent forwarding wrapper."""

    @pytest.mark.asyncio
    async def test_success_returns_reply_and_images(self, mock_forward_to_agent):
        mock_forward_to_agent.return_value = {
            "response": "Agent says hi",
            "image_ids": ["IMG_001"],
            "memory_count": 2,
        }
        reply, images = await forward_to_agent(TEST_SENDER_ID, "hello")
        assert reply == "Agent says hi"
        assert images == ["IMG_001"]

    @pytest.mark.asyncio
    async def test_calls_shared_forward(self, mock_forward_to_agent):
        await forward_to_agent(TEST_SENDER_ID, "test msg")
        mock_forward_to_agent.assert_called_once_with(
            TEST_AI_AGENT_URL, TEST_SENDER_ID, "test msg"
        )

    @pytest.mark.asyncio
    async def test_exception_returns_error_message(self, mock_forward_to_agent):
        mock_forward_to_agent.side_effect = Exception("Network down")
        reply, images = await forward_to_agent(TEST_SENDER_ID, "hello")
        from shared.constants import ERROR_SYSTEM_UNAVAILABLE_SHORT
        assert reply == ERROR_SYSTEM_UNAVAILABLE_SHORT
        assert images == []

    @pytest.mark.asyncio
    async def test_returns_empty_images_on_no_images(self, mock_forward_to_agent):
        mock_forward_to_agent.return_value = {
            "response": "No images here",
            "image_ids": [],
            "memory_count": 0,
        }
        reply, images = await forward_to_agent(TEST_SENDER_ID, "hi")
        assert images == []

    @pytest.mark.asyncio
    async def test_returns_multiple_image_ids(self, mock_forward_to_agent):
        mock_forward_to_agent.return_value = {
            "response": "Here are images",
            "image_ids": ["IMG_001", "IMG_002", "IMG_003"],
            "memory_count": 3,
        }
        reply, images = await forward_to_agent(TEST_SENDER_ID, "show products")
        assert len(images) == 3


# ===================================================================
# GET /webhook — verification endpoint
# ===================================================================
class TestGetWebhook:
    """Tests for the webhook verification GET endpoint."""

    @pytest.mark.asyncio
    async def test_valid_verification(self):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/webhook", params={
                "hub.mode": "subscribe",
                "hub.verify_token": TEST_FB_VERIFY_TOKEN,
                "hub.challenge": "CHALLENGE_ACCEPTED",
            })
        assert resp.status_code == 200
        assert resp.text == "CHALLENGE_ACCEPTED"

    @pytest.mark.asyncio
    async def test_wrong_verify_token(self):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/webhook", params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "CHALLENGE",
            })
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_wrong_mode(self):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/webhook", params={
                "hub.mode": "unsubscribe",
                "hub.verify_token": TEST_FB_VERIFY_TOKEN,
                "hub.challenge": "CHALLENGE",
            })
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_missing_all_params(self):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/webhook")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_missing_challenge(self):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/webhook", params={
                "hub.mode": "subscribe",
                "hub.verify_token": TEST_FB_VERIFY_TOKEN,
            })
        # hub.challenge is None => returns PlainTextResponse("None")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_plain_text(self):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/webhook", params={
                "hub.mode": "subscribe",
                "hub.verify_token": TEST_FB_VERIFY_TOKEN,
                "hub.challenge": "12345",
            })
        assert resp.headers["content-type"].startswith("text/plain")


# ===================================================================
# POST /webhook — receive endpoint
# ===================================================================
class TestPostWebhook:
    """Tests for the webhook receive POST endpoint."""

    @pytest.mark.asyncio
    async def test_valid_page_event_returns_200(self, valid_fb_signature):
        from httpx import ASGITransport, AsyncClient
        payload = json.dumps({
            "object": "page",
            "entry": [{"id": "P1", "time": 1, "messaging": []}],
        }).encode()
        sig = valid_fb_signature(payload)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/webhook",
                content=payload,
                headers={
                    "X-Hub-Signature-256": sig,
                    "Content-Type": "application/json",
                },
            )
        assert resp.status_code == 200
        assert resp.text == "EVENT_RECEIVED"

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_403(self):
        from httpx import ASGITransport, AsyncClient
        payload = json.dumps({"object": "page", "entry": []}).encode()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/webhook",
                content=payload,
                headers={
                    "X-Hub-Signature-256": "sha256=invalid",
                    "Content-Type": "application/json",
                },
            )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_non_page_object_returns_404(self, valid_fb_signature):
        from httpx import ASGITransport, AsyncClient
        payload = json.dumps({"object": "user", "entry": []}).encode()
        sig = valid_fb_signature(payload)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/webhook",
                content=payload,
                headers={
                    "X-Hub-Signature-256": sig,
                    "Content-Type": "application/json",
                },
            )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_missing_signature_header_with_secret(self):
        """When FB_APP_SECRET is set, missing signature header triggers 403."""
        from httpx import ASGITransport, AsyncClient
        payload = json.dumps({"object": "page", "entry": []}).encode()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/webhook",
                content=payload,
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_empty_secret_skips_verification(self, monkeypatch):
        """When FB_APP_SECRET is empty, signature check is skipped."""
        monkeypatch.setattr(webhook_main, "FB_APP_SECRET", "")
        from httpx import ASGITransport, AsyncClient
        payload = json.dumps({
            "object": "page",
            "entry": [{"id": "P1", "time": 1, "messaging": []}],
        }).encode()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/webhook",
                content=payload,
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_text_message_spawns_background_task(
        self, valid_fb_signature, sample_webhook_payload
    ):
        """Text message events are dispatched to background tasks."""
        from httpx import ASGITransport, AsyncClient

        with patch.object(webhook_main, "_debounce_enqueue", new_callable=AsyncMock) as mock_enqueue, \
             patch.object(webhook_main, "send_typing_indicator", new_callable=AsyncMock):
            payload = json.dumps(sample_webhook_payload).encode()
            sig = valid_fb_signature(payload)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post(
                    "/webhook",
                    content=payload,
                    headers={
                        "X-Hub-Signature-256": sig,
                        "Content-Type": "application/json",
                    },
                )
            assert resp.status_code == 200
            # Give background tasks a moment to run
            await asyncio.sleep(0.1)
            mock_enqueue.assert_called_once_with(TEST_SENDER_ID, "Hello, bot!")

    @pytest.mark.asyncio
    async def test_echo_message_is_skipped(self, valid_fb_signature, sample_echo_event):
        """Echo messages should not trigger any processing."""
        from httpx import ASGITransport, AsyncClient

        event_payload = {
            "object": "page",
            "entry": [{"id": "P1", "time": 1, "messaging": [sample_echo_event]}],
        }

        with patch.object(webhook_main, "_debounce_enqueue", new_callable=AsyncMock) as mock_enqueue:
            payload = json.dumps(event_payload).encode()
            sig = valid_fb_signature(payload)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post(
                    "/webhook",
                    content=payload,
                    headers={
                        "X-Hub-Signature-256": sig,
                        "Content-Type": "application/json",
                    },
                )
            await asyncio.sleep(0.1)
            mock_enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_mid_is_skipped(
        self, valid_fb_signature, sample_webhook_payload
    ):
        """Duplicate messages (same mid) should be dropped."""
        from httpx import ASGITransport, AsyncClient

        # Pre-mark mid as seen
        _is_duplicate(TEST_MID)

        with patch.object(webhook_main, "_debounce_enqueue", new_callable=AsyncMock) as mock_enqueue:
            payload = json.dumps(sample_webhook_payload).encode()
            sig = valid_fb_signature(payload)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post(
                    "/webhook",
                    content=payload,
                    headers={
                        "X-Hub-Signature-256": sig,
                        "Content-Type": "application/json",
                    },
                )
            await asyncio.sleep(0.1)
            mock_enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_postback_event_forwarded(
        self, valid_fb_signature, sample_postback_payload, mock_forward_to_agent, mock_httpx_post
    ):
        """Postback events should be forwarded directly to the agent."""
        from httpx import ASGITransport, AsyncClient

        payload = json.dumps(sample_postback_payload).encode()
        sig = valid_fb_signature(payload)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/webhook",
                content=payload,
                headers={
                    "X-Hub-Signature-256": sig,
                    "Content-Type": "application/json",
                },
            )
        await asyncio.sleep(0.1)
        mock_forward_to_agent.assert_called_once_with(
            TEST_AI_AGENT_URL, TEST_SENDER_ID, "GET_STARTED"
        )

    @pytest.mark.asyncio
    async def test_multiple_entries(self, valid_fb_signature):
        """Multiple entries/messaging events in one payload."""
        from httpx import ASGITransport, AsyncClient

        event_payload = {
            "object": "page",
            "entry": [
                {
                    "id": "P1", "time": 1,
                    "messaging": [
                        {
                            "sender": {"id": "user1"},
                            "recipient": {"id": "page1"},
                            "message": {"mid": "mid.a1", "text": "msg1"},
                        },
                        {
                            "sender": {"id": "user2"},
                            "recipient": {"id": "page1"},
                            "message": {"mid": "mid.a2", "text": "msg2"},
                        },
                    ],
                },
            ],
        }

        with patch.object(webhook_main, "_debounce_enqueue", new_callable=AsyncMock) as mock_enqueue, \
             patch.object(webhook_main, "send_typing_indicator", new_callable=AsyncMock):
            payload = json.dumps(event_payload).encode()
            sig = valid_fb_signature(payload)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post(
                    "/webhook",
                    content=payload,
                    headers={
                        "X-Hub-Signature-256": sig,
                        "Content-Type": "application/json",
                    },
                )
            assert resp.status_code == 200
            await asyncio.sleep(0.1)
            assert mock_enqueue.call_count == 2


# ===================================================================
# Debounce system
# ===================================================================
class TestDebounceEnqueue:
    """Tests for _debounce_enqueue — message buffering logic."""

    @pytest.mark.asyncio
    async def test_enqueue_creates_state(self):
        with patch.object(webhook_main, "_debounce_wait_and_process", new_callable=AsyncMock), \
             patch.object(webhook_main, "send_typing_indicator", new_callable=AsyncMock):
            await _debounce_enqueue("user1", "hello")
        assert "user1" in webhook_main._debounce_state
        assert webhook_main._debounce_state["user1"].messages == ["hello"]

    @pytest.mark.asyncio
    async def test_enqueue_multiple_messages(self):
        with patch.object(webhook_main, "_debounce_wait_and_process", new_callable=AsyncMock), \
             patch.object(webhook_main, "send_typing_indicator", new_callable=AsyncMock):
            await _debounce_enqueue("user1", "msg1")
            await _debounce_enqueue("user1", "msg2")
            await _debounce_enqueue("user1", "msg3")
        assert webhook_main._debounce_state["user1"].messages == ["msg1", "msg2", "msg3"]

    @pytest.mark.asyncio
    async def test_enqueue_sets_first_message_time(self):
        before = time.time()
        with patch.object(webhook_main, "_debounce_wait_and_process", new_callable=AsyncMock), \
             patch.object(webhook_main, "send_typing_indicator", new_callable=AsyncMock):
            await _debounce_enqueue("user1", "hello")
        after = time.time()
        state = webhook_main._debounce_state["user1"]
        assert before <= state.first_message_time <= after

    @pytest.mark.asyncio
    async def test_enqueue_updates_last_message_time(self):
        with patch.object(webhook_main, "_debounce_wait_and_process", new_callable=AsyncMock), \
             patch.object(webhook_main, "send_typing_indicator", new_callable=AsyncMock):
            await _debounce_enqueue("user1", "msg1")
            t1 = webhook_main._debounce_state["user1"].last_message_time
            await asyncio.sleep(0.01)
            await _debounce_enqueue("user1", "msg2")
            t2 = webhook_main._debounce_state["user1"].last_message_time
        assert t2 > t1

    @pytest.mark.asyncio
    async def test_enqueue_sends_typing_indicator(self):
        with patch.object(webhook_main, "_debounce_wait_and_process", new_callable=AsyncMock), \
             patch.object(webhook_main, "send_typing_indicator", new_callable=AsyncMock) as mock_typing:
            await _debounce_enqueue("user1", "hello")
            await asyncio.sleep(0.05)
        mock_typing.assert_called_with("user1")

    @pytest.mark.asyncio
    async def test_enqueue_different_users_independent(self):
        with patch.object(webhook_main, "_debounce_wait_and_process", new_callable=AsyncMock), \
             patch.object(webhook_main, "send_typing_indicator", new_callable=AsyncMock):
            await _debounce_enqueue("userA", "A says hi")
            await _debounce_enqueue("userB", "B says hi")
        assert webhook_main._debounce_state["userA"].messages == ["A says hi"]
        assert webhook_main._debounce_state["userB"].messages == ["B says hi"]


class TestDebounceMaxBuffer:
    """Tests for debounce buffer size limit flush."""

    @pytest.mark.asyncio
    async def test_buffer_size_limit_triggers_flush(self, monkeypatch):
        monkeypatch.setattr(webhook_main, "DEBOUNCE_MAX_BUFFER_SIZE", 3)

        with patch.object(webhook_main, "_debounce_process", new_callable=AsyncMock) as mock_process, \
             patch.object(webhook_main, "send_typing_indicator", new_callable=AsyncMock), \
             patch.object(webhook_main, "_debounce_wait_and_process", new_callable=AsyncMock):
            # Fill buffer to max
            await _debounce_enqueue("user1", "msg1")
            await _debounce_enqueue("user1", "msg2")
            await _debounce_enqueue("user1", "msg3")
            # 4th message triggers force flush (buffer already at 3 = max)
            await _debounce_enqueue("user1", "msg4")
            await asyncio.sleep(0.05)
        # _debounce_process should have been called via create_task
        mock_process.assert_called_with("user1")

    @pytest.mark.asyncio
    async def test_buffer_size_limit_appends_message_before_flush(self, monkeypatch):
        monkeypatch.setattr(webhook_main, "DEBOUNCE_MAX_BUFFER_SIZE", 2)

        process_calls = []

        async def capture_process(sender_id):
            state = webhook_main._debounce_state.get(sender_id)
            if state:
                process_calls.append(list(state.messages))

        with patch.object(webhook_main, "_debounce_process", side_effect=capture_process), \
             patch.object(webhook_main, "send_typing_indicator", new_callable=AsyncMock), \
             patch.object(webhook_main, "_debounce_wait_and_process", new_callable=AsyncMock):
            await _debounce_enqueue("user1", "msg1")
            await _debounce_enqueue("user1", "msg2")
            # 3rd triggers flush; the message should be in buffer before process
            await _debounce_enqueue("user1", "msg3")
            await asyncio.sleep(0.05)

        assert len(process_calls) > 0
        assert "msg3" in process_calls[0]


class TestDebounceMaxChars:
    """Tests for debounce character limit flush."""

    @pytest.mark.asyncio
    async def test_char_limit_triggers_flush(self, monkeypatch):
        monkeypatch.setattr(webhook_main, "DEBOUNCE_MAX_BUFFER_CHARS", 20)
        monkeypatch.setattr(webhook_main, "DEBOUNCE_MAX_BUFFER_SIZE", 100)

        with patch.object(webhook_main, "_debounce_process", new_callable=AsyncMock) as mock_process, \
             patch.object(webhook_main, "send_typing_indicator", new_callable=AsyncMock), \
             patch.object(webhook_main, "_debounce_wait_and_process", new_callable=AsyncMock):
            await _debounce_enqueue("user1", "a" * 10)  # 10 chars
            await _debounce_enqueue("user1", "b" * 11)  # total 21 > 20 chars
            await asyncio.sleep(0.05)
        mock_process.assert_called_with("user1")


class TestDebounceMaxWait:
    """Tests for debounce max wait time flush."""

    @pytest.mark.asyncio
    async def test_max_wait_triggers_flush(self, monkeypatch):
        monkeypatch.setattr(webhook_main, "DEBOUNCE_MAX_WAIT_SECONDS", 0.05)
        monkeypatch.setattr(webhook_main, "DEBOUNCE_MAX_BUFFER_SIZE", 100)
        monkeypatch.setattr(webhook_main, "DEBOUNCE_MAX_BUFFER_CHARS", 10000)

        with patch.object(webhook_main, "_debounce_process", new_callable=AsyncMock) as mock_process, \
             patch.object(webhook_main, "send_typing_indicator", new_callable=AsyncMock), \
             patch.object(webhook_main, "_debounce_wait_and_process", new_callable=AsyncMock):
            await _debounce_enqueue("user1", "msg1")
            await asyncio.sleep(0.1)  # Exceed max wait
            await _debounce_enqueue("user1", "msg2")
            await asyncio.sleep(0.05)
        mock_process.assert_called_with("user1")


class TestDebounceProcess:
    """Tests for _debounce_process — draining and forwarding."""

    @pytest.mark.asyncio
    async def test_process_combines_messages(self, mock_forward_to_agent, mock_httpx_post):
        state = _UserDebounceState()
        state.messages = ["hello", "how are you", "thanks"]
        state.first_message_time = time.time() - 5
        webhook_main._debounce_state["user1"] = state

        await _debounce_process("user1")

        mock_forward_to_agent.assert_called_once()
        call_args = mock_forward_to_agent.call_args
        # The wrapper in main.py calls _forward_to_agent(AI_AGENT_URL, sender_id, text)
        assert call_args[0][1] == "user1"
        assert "hello\nhow are you\nthanks" == call_args[0][2]

    @pytest.mark.asyncio
    async def test_process_clears_buffer(self, mock_forward_to_agent, mock_httpx_post):
        state = _UserDebounceState()
        state.messages = ["test"]
        state.first_message_time = time.time()
        webhook_main._debounce_state["user1"] = state

        await _debounce_process("user1")

        # State should be cleaned up
        assert "user1" not in webhook_main._debounce_state

    @pytest.mark.asyncio
    async def test_process_sends_reply(self, mock_forward_to_agent, mock_httpx_post):
        instance, _ = mock_httpx_post
        mock_forward_to_agent.return_value = {
            "response": "Agent reply",
            "image_ids": [],
            "memory_count": 1,
        }

        state = _UserDebounceState()
        state.messages = ["hi"]
        state.first_message_time = time.time()
        webhook_main._debounce_state["user1"] = state

        await _debounce_process("user1")

        # Should call send_message (via httpx post) and send_typing_indicator
        assert instance.post.call_count >= 1

    @pytest.mark.asyncio
    async def test_process_sends_images(self, mock_forward_to_agent, mock_httpx_post):
        instance, _ = mock_httpx_post
        mock_forward_to_agent.return_value = {
            "response": "Here",
            "image_ids": ["IMG_001", "IMG_002"],
            "memory_count": 1,
        }

        state = _UserDebounceState()
        state.messages = ["show images"]
        state.first_message_time = time.time()
        webhook_main._debounce_state["user1"] = state

        await _debounce_process("user1")

        # typing + text + 2 images = 4 posts total
        assert instance.post.call_count >= 3

    @pytest.mark.asyncio
    async def test_process_no_state_is_noop(self):
        """If state doesn't exist, process is a no-op."""
        await _debounce_process("nonexistent_user")
        # Should not raise

    @pytest.mark.asyncio
    async def test_process_empty_messages_is_noop(self):
        state = _UserDebounceState()
        state.messages = []
        webhook_main._debounce_state["user1"] = state

        with patch.object(webhook_main, "forward_to_agent", new_callable=AsyncMock) as mock_fwd:
            await _debounce_process("user1")
            mock_fwd.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_error_sends_error_message(self, mock_httpx_post):
        instance, _ = mock_httpx_post

        with patch.object(webhook_main, "forward_to_agent", new_callable=AsyncMock) as mock_fwd:
            mock_fwd.side_effect = Exception("Agent down")

            state = _UserDebounceState()
            state.messages = ["help"]
            state.first_message_time = time.time()
            webhook_main._debounce_state["user1"] = state

            await _debounce_process("user1")

        # Should have tried to send error message (typing + error)
        assert instance.post.call_count >= 1

    @pytest.mark.asyncio
    async def test_process_sets_timer_task_none(self, mock_forward_to_agent, mock_httpx_post):
        mock_task = MagicMock()
        state = _UserDebounceState()
        state.messages = ["test"]
        state.first_message_time = time.time()
        state.timer_task = mock_task
        webhook_main._debounce_state["user1"] = state

        await _debounce_process("user1")
        # State is cleaned up entirely since messages became empty
        assert "user1" not in webhook_main._debounce_state


class TestDebounceWaitAndProcess:
    """Tests for _debounce_wait_and_process."""

    @pytest.mark.asyncio
    async def test_waits_then_processes(self, monkeypatch):
        monkeypatch.setattr(webhook_main, "DEBOUNCE_DELAY_SECONDS", 0.01)

        with patch.object(webhook_main, "_debounce_process", new_callable=AsyncMock) as mock_process:
            await _debounce_wait_and_process("user1")
        mock_process.assert_called_once_with("user1")

    @pytest.mark.asyncio
    async def test_cancelled_does_not_process(self):
        with patch.object(webhook_main, "_debounce_process", new_callable=AsyncMock) as mock_process:
            task = asyncio.create_task(_debounce_wait_and_process("user1"))
            await asyncio.sleep(0.01)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        mock_process.assert_not_called()


# ===================================================================
# Static pages
# ===================================================================
class TestStaticPages:
    """Tests for /privacy and /terms HTML pages."""

    @pytest.mark.asyncio
    async def test_privacy_page_returns_html(self):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/privacy")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "<!DOCTYPE html>" in resp.text

    @pytest.mark.asyncio
    async def test_terms_page_returns_html(self):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/terms")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "<!DOCTYPE html>" in resp.text

    @pytest.mark.asyncio
    async def test_privacy_contains_lang_th(self):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/privacy")
        assert 'lang="th"' in resp.text

    @pytest.mark.asyncio
    async def test_terms_contains_lang_th(self):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/terms")
        assert 'lang="th"' in resp.text


# ===================================================================
# _process_messaging_event edge cases
# ===================================================================
class TestProcessMessagingEvent:
    """Tests for _process_messaging_event internal function."""

    @pytest.mark.asyncio
    async def test_attachment_event_does_not_crash(self, sample_attachment_event):
        with patch.object(webhook_main, "_debounce_enqueue", new_callable=AsyncMock):
            await webhook_main._process_messaging_event(sample_attachment_event)

    @pytest.mark.asyncio
    async def test_empty_event_does_not_crash(self):
        await webhook_main._process_messaging_event({})

    @pytest.mark.asyncio
    async def test_event_with_no_text_no_postback(self):
        event = {
            "sender": {"id": "user1"},
            "recipient": {"id": "page1"},
            "message": {"mid": "mid.notext"},
        }
        with patch.object(webhook_main, "_debounce_enqueue", new_callable=AsyncMock) as mock_enqueue:
            await webhook_main._process_messaging_event(event)
            mock_enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_postback_sends_reply_and_images(
        self, sample_postback_event, mock_forward_to_agent, mock_httpx_post
    ):
        mock_forward_to_agent.return_value = {
            "response": "Welcome!",
            "image_ids": ["IMG_001"],
            "memory_count": 0,
        }
        instance, _ = mock_httpx_post

        await webhook_main._process_messaging_event(sample_postback_event)

        mock_forward_to_agent.assert_called_once()
        # text reply + image send = 2 posts
        assert instance.post.call_count == 2

    @pytest.mark.asyncio
    async def test_postback_no_reply_no_images(
        self, sample_postback_event, mock_forward_to_agent, mock_httpx_post
    ):
        mock_forward_to_agent.return_value = {
            "response": "",
            "image_ids": [],
            "memory_count": 0,
        }
        instance, _ = mock_httpx_post

        await webhook_main._process_messaging_event(sample_postback_event)

        # No send_message or send_images should be called
        instance.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_postback_with_empty_payload(self, mock_forward_to_agent, mock_httpx_post):
        event = {
            "sender": {"id": "user1"},
            "recipient": {"id": "page1"},
            "postback": {"title": "Button", "payload": ""},
        }
        await webhook_main._process_messaging_event(event)
        mock_forward_to_agent.assert_called_once()
        assert mock_forward_to_agent.call_args[0][2] == ""


# ===================================================================
# UserDebounceState dataclass
# ===================================================================
class TestUserDebounceState:
    """Tests for the _UserDebounceState dataclass."""

    def test_default_values(self):
        state = _UserDebounceState()
        assert state.messages == []
        assert state.timer_task is None
        assert state.first_message_time == 0.0
        assert state.last_message_time == 0.0

    def test_lock_is_created(self):
        state = _UserDebounceState()
        assert isinstance(state.lock, asyncio.Lock)

    def test_independent_message_lists(self):
        s1 = _UserDebounceState()
        s2 = _UserDebounceState()
        s1.messages.append("hello")
        assert s2.messages == []


# ===================================================================
# App metadata
# ===================================================================
class TestAppMeta:
    """Tests for FastAPI app metadata."""

    def test_app_title(self):
        assert app.title == "Facebook Messenger Webhook"

    def test_webhook_routes_exist(self):
        routes = [r.path for r in app.routes]
        assert "/webhook" in routes
        assert "/privacy" in routes
        assert "/terms" in routes
