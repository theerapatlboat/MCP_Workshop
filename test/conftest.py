"""Root conftest.py — shared fixtures for the entire test suite."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Make project modules importable
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
for sub in ["", "agent", "mcp-server", "webhook", "guardrail"]:
    p = str(PROJECT_ROOT / sub) if sub else str(PROJECT_ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# Common fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_sqlite_db(tmp_path):
    """Temporary SQLite database file."""
    return tmp_path / "test_sessions.db"


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client with embeddings and chat completions."""
    client = MagicMock()

    # Embeddings
    def _make_embedding(*args, **kwargs):
        resp = MagicMock()
        inp = kwargs.get("input", args[1] if len(args) > 1 else "text")
        texts = inp if isinstance(inp, list) else [inp]
        items = []
        for i, _ in enumerate(texts):
            item = MagicMock()
            item.embedding = np.random.rand(1536).astype(np.float32).tolist()
            item.index = i
            items.append(item)
        resp.data = items
        return resp

    client.embeddings.create = MagicMock(side_effect=_make_embedding)

    # Chat completions
    def _make_chat(*args, **kwargs):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = '{"answer": "test"}'
        return resp

    client.chat.completions.create = MagicMock(side_effect=_make_chat)

    return client


@pytest.fixture
def mock_async_openai_client():
    """Mock AsyncOpenAI client."""
    client = AsyncMock()

    async def _make_embedding(*args, **kwargs):
        resp = MagicMock()
        item = MagicMock()
        item.embedding = np.random.rand(1536).astype(np.float32).tolist()
        item.index = 0
        resp.data = [item]
        return resp

    client.embeddings.create = AsyncMock(side_effect=_make_embedding)

    async def _make_chat(*args, **kwargs):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = '{"allowed": true, "confidence": 0.95, "reason": "ok"}'
        return resp

    client.chat.completions.create = AsyncMock(side_effect=_make_chat)

    return client


@pytest.fixture
def mock_embedding_response():
    """Factory returning mock embedding API responses."""
    def _make(n: int = 1, dim: int = 1536):
        resp = MagicMock()
        items = []
        for i in range(n):
            item = MagicMock()
            item.embedding = np.random.rand(dim).astype(np.float32).tolist()
            item.index = i
            items.append(item)
        resp.data = items
        return resp
    return _make


@pytest.fixture
def mock_chat_response():
    """Factory returning mock chat completion responses."""
    def _make(content: str):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = content
        return resp
    return _make


@pytest.fixture
def sample_product_data():
    """Realistic product API response."""
    return {
        "data": [
            {
                "id": 1, "name": "ผงเครื่องเทศหอมรักกัน 30g", "sku": "RG-30",
                "price": 79.0, "quantity": "10.0",
                "stock_quantity": "20", "status": "active",
                "barcode": "8851234", "original_price": 89.0,
                "cost": 35.0, "reserved_quantity": "3",
                "live_quantity": "7", "weight": 0.03,
                "unit_id": 1, "description": "ผงเครื่องเทศสำหรับทำน้ำซุป",
            },
            {
                "id": 2, "name": "ผงเครื่องเทศหอมรักกัน 15g", "sku": "RG-15",
                "price": 45.0, "quantity": None,
                "stock_quantity": "0", "status": "active",
                "barcode": None, "original_price": None,
                "cost": None, "reserved_quantity": "0",
                "live_quantity": "0", "weight": None,
                "unit_id": None, "description": None,
            },
        ]
    }


@pytest.fixture
def sample_order_draft_body():
    """Common order draft creation payload."""
    return {
        "sales_channel_id": 1, "carrier_id": 2,
        "customer_name": "สมชาย ใจดี", "phone": "0812345678",
        "address": "123 ถ.สุขุมวิท", "sub_district": "บางรัก",
        "district": "บางรัก", "province": "กรุงเทพมหานคร",
        "postal_code": "10500",
        "items": [{"id": 1, "sku": "RG-30", "quantity": 2, "price": 79.0}],
        "payment_method_id": 1, "staff_id": 1, "note": "",
    }


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set all required env vars to safe test values."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-123")
    monkeypatch.setenv("UAT_API_KEY", "test-uat-key-456")
    monkeypatch.setenv("UAT_API_URL", "https://test.api.example.com/api/v1")
    monkeypatch.setenv("MCP_SERVER_URL", "http://localhost:8000/mcp")
    monkeypatch.setenv("AGENT_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("FB_VERIFY_TOKEN", "test-fb-verify-token")
    monkeypatch.setenv("FB_APP_SECRET", "test-fb-app-secret")
    monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", "test-fb-page-token")
    monkeypatch.setenv("AI_AGENT_URL", "http://localhost:3000/chat")
