"""Fixtures for webhook test suite."""

import hashlib
import hmac
import importlib
import json
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make project modules importable
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WEBHOOK_DIR = PROJECT_ROOT / "webhook"

# Ensure webhook dir is at the VERY FRONT so its main.py wins over guardrail's
_webhook_str = str(WEBHOOK_DIR)
if _webhook_str in sys.path:
    sys.path.remove(_webhook_str)
sys.path.insert(0, _webhook_str)

_project_str = str(PROJECT_ROOT)
if _project_str not in sys.path:
    sys.path.insert(0, _project_str)

# Force-(re)import webhook main so it picks up the correct module
if "main" in sys.modules:
    # If guardrail's main was loaded first by root conftest, remove it
    _existing = sys.modules["main"]
    _existing_file = getattr(_existing, "__file__", "") or ""
    if "webhook" not in _existing_file:
        del sys.modules["main"]

import main as webhook_main  # noqa: E402


# ---------------------------------------------------------------------------
# Constants used across tests
# ---------------------------------------------------------------------------
TEST_FB_APP_SECRET = "test-fb-app-secret"
TEST_FB_VERIFY_TOKEN = "test-fb-verify-token"
TEST_FB_PAGE_ACCESS_TOKEN = "test-fb-page-token"
TEST_AI_AGENT_URL = "http://localhost:3000/chat"
TEST_SENDER_ID = "1234567890"
TEST_RECIPIENT_ID = "9876543210"
TEST_MID = "mid.1234567890"


# ---------------------------------------------------------------------------
# Signature helper
# ---------------------------------------------------------------------------
def compute_fb_signature(payload: bytes, secret: str = TEST_FB_APP_SECRET) -> str:
    """Compute a valid X-Hub-Signature-256 header value."""
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def valid_fb_signature():
    """Return a callable that computes a valid Facebook signature for a payload."""
    return compute_fb_signature


@pytest.fixture
def sample_text_message_event():
    """A single text messaging event from Facebook."""
    return {
        "sender": {"id": TEST_SENDER_ID},
        "recipient": {"id": TEST_RECIPIENT_ID},
        "timestamp": 1234567890,
        "message": {
            "mid": TEST_MID,
            "text": "Hello, bot!",
        },
    }


@pytest.fixture
def sample_echo_event():
    """An echo messaging event (bot's own messages echoed back)."""
    return {
        "sender": {"id": TEST_SENDER_ID},
        "recipient": {"id": TEST_RECIPIENT_ID},
        "timestamp": 1234567890,
        "message": {
            "mid": "mid.echo.111",
            "text": "Echo message",
            "is_echo": True,
        },
    }


@pytest.fixture
def sample_postback_event():
    """A postback event from a button tap."""
    return {
        "sender": {"id": TEST_SENDER_ID},
        "recipient": {"id": TEST_RECIPIENT_ID},
        "timestamp": 1234567890,
        "postback": {
            "title": "Get Started",
            "payload": "GET_STARTED",
        },
    }


@pytest.fixture
def sample_attachment_event():
    """An attachment messaging event."""
    return {
        "sender": {"id": TEST_SENDER_ID},
        "recipient": {"id": TEST_RECIPIENT_ID},
        "timestamp": 1234567890,
        "message": {
            "mid": "mid.attach.222",
            "attachments": [
                {"type": "image", "payload": {"url": "https://example.com/photo.jpg"}},
            ],
        },
    }


@pytest.fixture
def sample_webhook_payload(sample_text_message_event):
    """A full webhook POST body containing one text message."""
    return {
        "object": "page",
        "entry": [
            {
                "id": "PAGE_ID",
                "time": 1234567890,
                "messaging": [sample_text_message_event],
            }
        ],
    }


@pytest.fixture
def sample_postback_payload(sample_postback_event):
    """A full webhook POST body containing one postback."""
    return {
        "object": "page",
        "entry": [
            {
                "id": "PAGE_ID",
                "time": 1234567890,
                "messaging": [sample_postback_event],
            }
        ],
    }


@pytest.fixture(autouse=True)
def clear_dedup_state():
    """Clear deduplication state before each test."""
    webhook_main._seen_mids.clear()
    yield
    webhook_main._seen_mids.clear()


@pytest.fixture(autouse=True)
def clear_debounce_state():
    """Clear debounce state before each test."""
    webhook_main._debounce_state.clear()
    yield
    webhook_main._debounce_state.clear()


@pytest.fixture(autouse=True)
def set_webhook_env(monkeypatch):
    """Set environment variables for webhook module globals."""
    monkeypatch.setattr(webhook_main, "FB_APP_SECRET", TEST_FB_APP_SECRET)
    monkeypatch.setattr(webhook_main, "FB_VERIFY_TOKEN", TEST_FB_VERIFY_TOKEN)
    monkeypatch.setattr(webhook_main, "FB_PAGE_ACCESS_TOKEN", TEST_FB_PAGE_ACCESS_TOKEN)
    monkeypatch.setattr(webhook_main, "AI_AGENT_URL", TEST_AI_AGENT_URL)
    monkeypatch.setattr(webhook_main, "fb_attachment_ids", {
        "IMG_001": "attach_001",
        "IMG_002": "attach_002",
        "IMG_003": "attach_003",
    })


@pytest.fixture
def mock_httpx_post():
    """Mock httpx.AsyncClient().post for Graph API calls."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"message_id": "mid.sent"}'
    mock_resp.json.return_value = {"message_id": "mid.sent"}

    with patch.object(webhook_main, "httpx") as mock_httpx_mod:
        instance = AsyncMock()
        instance.post.return_value = mock_resp
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_httpx_mod.AsyncClient.return_value = instance
        yield instance, mock_resp


@pytest.fixture
def mock_forward_to_agent():
    """Mock the _forward_to_agent function imported from shared.http_client."""
    with patch.object(webhook_main, "_forward_to_agent", new_callable=AsyncMock) as mock:
        mock.return_value = {
            "response": "Test reply from agent",
            "image_ids": [],
            "memory_count": 1,
        }
        yield mock
