"""Fixtures for guardrail test suite."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Make guardrail modules importable WITH highest priority
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GUARDRAIL_DIR = str(PROJECT_ROOT / "guardrail")

# Ensure guardrail is the VERY FIRST entry so its config.py, models.py win
if GUARDRAIL_DIR in sys.path:
    sys.path.remove(GUARDRAIL_DIR)
sys.path.insert(0, GUARDRAIL_DIR)

# Also keep project root (for shared/ etc.) but after guardrail
_proj_root_str = str(PROJECT_ROOT)
if _proj_root_str not in sys.path:
    sys.path.insert(1, _proj_root_str)

# Evict cached modules that may have been loaded from the wrong directory
# (mcp-server also has config.py and models.py).
for _mod_name in ["config", "models", "main", "vector_guard", "llm_guard"]:
    cached = sys.modules.get(_mod_name)
    if cached is not None:
        mod_file = getattr(cached, "__file__", "") or ""
        if "guardrail" not in mod_file.replace("\\", "/"):
            del sys.modules[_mod_name]


def _ensure_guardrail_modules():
    """Evict cached modules from other directories and ensure guardrail wins."""
    # Re-prioritize guardrail dir
    if GUARDRAIL_DIR in sys.path:
        sys.path.remove(GUARDRAIL_DIR)
    sys.path.insert(0, GUARDRAIL_DIR)

    for mod_name in ["config", "models", "main"]:
        cached = sys.modules.get(mod_name)
        if cached is not None:
            mod_file = getattr(cached, "__file__", "") or ""
            if "guardrail" not in mod_file.replace("\\", "/"):
                del sys.modules[mod_name]


@pytest.fixture(autouse=True)
def _ensure_guardrail_imports():
    """Per-test fixture to ensure guardrail modules are imported correctly."""
    _ensure_guardrail_modules()
    yield
    # No cleanup needed — other test directories handle their own modules


# ---------------------------------------------------------------------------
# Constants used across tests
# ---------------------------------------------------------------------------
TEST_OPENAI_API_KEY = "sk-test-guardrail-key"
TEST_AGENT_API_URL = "http://localhost:3000/chat"
TEST_GUARDRAIL_PORT = 8002
TEST_VECTOR_SIMILARITY_THRESHOLD = 0.45
TEST_POLICY_MODEL = "gpt-4o-mini"
TEST_SESSION_ID = "session_abc123"

# Thai rejection message matching topics.json
TEST_REJECTION_MESSAGE_TH = (
    "ขออภัยค่ะ ดิฉันเป็นผู้ช่วยขายผงเครื่องเทศหอมรักกัน "
    "สามารถช่วยเรื่องสินค้า สูตรอาหาร ราคา คำสั่งซื้อ "
    "และการจัดส่งได้ค่ะ กรุณาสอบถามเกี่ยวกับบริการของเราได้เลยค่ะ"
)


# ---------------------------------------------------------------------------
# Guard module state reset
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def reset_vector_guard_state():
    """Reset vector_guard module-level state before each test."""
    import vector_guard

    original_index = vector_guard._topic_index
    original_texts = vector_guard._topic_texts
    original_client = vector_guard._async_client

    vector_guard._topic_index = None
    vector_guard._topic_texts = []
    vector_guard._async_client = None

    yield

    vector_guard._topic_index = original_index
    vector_guard._topic_texts = original_texts
    vector_guard._async_client = original_client


@pytest.fixture(autouse=True)
def reset_llm_guard_state():
    """Reset llm_guard module-level state before each test."""
    import llm_guard

    original_client = llm_guard._async_client

    llm_guard._async_client = None

    yield

    llm_guard._async_client = original_client


# ---------------------------------------------------------------------------
# Mock OpenAI clients
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_sync_openai_client():
    """Mock synchronous OpenAI client for init_vector_guard."""
    client = MagicMock()

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
    return client


@pytest.fixture
def mock_async_openai_client():
    """Mock AsyncOpenAI client for vector and LLM guards."""
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
        resp.choices[0].message.content = json.dumps(
            {"allowed": True, "confidence": 0.95, "reason": "product inquiry"}
        )
        return resp

    client.chat.completions.create = AsyncMock(side_effect=_make_chat)
    return client


@pytest.fixture
def mock_async_openai_client_blocked():
    """Mock AsyncOpenAI client that returns a blocked policy result."""
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
        resp.choices[0].message.content = json.dumps(
            {"allowed": False, "confidence": 0.90, "reason": "off-topic request"}
        )
        return resp

    client.chat.completions.create = AsyncMock(side_effect=_make_chat)
    return client


# ---------------------------------------------------------------------------
# FAISS index fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_faiss_index():
    """Build a small FAISS index with known topics."""
    import faiss

    n_topics = 5
    dim = 1536
    embeddings = np.random.rand(n_topics, dim).astype(np.float32)
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    return index


# ---------------------------------------------------------------------------
# Sample topic texts
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_topic_texts():
    """Subset of topics for testing."""
    return [
        "สอบถามราคาสินค้า ราคาผงเครื่องเทศ ราคาซอง",
        "สอบถามข้อมูลสินค้า ผงเครื่องเทศ หอมรักกัน ผงสามเกลอ",
        "สั่งซื้อสินค้า สร้างออเดอร์ ซื้อ ยืนยันคำสั่งซื้อ order",
        "สอบถามสูตรทำน้ำซุป วิธีทำ สูตรอาหาร วัตถุดิบ",
        "ทักทาย สวัสดี hello hi สนใจสินค้า",
    ]


# ---------------------------------------------------------------------------
# Environment fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def guardrail_env_vars(monkeypatch):
    """Set environment variables for guardrail config."""
    monkeypatch.setenv("OPENAI_API_KEY", TEST_OPENAI_API_KEY)
    monkeypatch.setenv("AGENT_API_URL", TEST_AGENT_API_URL)
    monkeypatch.setenv("GUARDRAIL_PORT", str(TEST_GUARDRAIL_PORT))
    monkeypatch.setenv("VECTOR_SIMILARITY_THRESHOLD", str(TEST_VECTOR_SIMILARITY_THRESHOLD))


# ---------------------------------------------------------------------------
# Mock forward_to_agent
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_forward_to_agent():
    """Mock shared.http_client.forward_to_agent imported in main."""
    with patch("main._forward_to_agent", new_callable=AsyncMock) as mock:
        mock.return_value = {
            "response": "สวัสดีค่ะ ยินดีให้บริการค่ะ",
            "image_ids": [],
            "memory_count": 1,
        }
        yield mock


# ---------------------------------------------------------------------------
# Async test client fixture for FastAPI
# ---------------------------------------------------------------------------
@pytest.fixture
async def async_test_client():
    """Create httpx.AsyncClient with ASGITransport for the guardrail app.

    The lifespan is NOT triggered — guards are patched individually in tests.
    """
    import httpx
    from httpx import ASGITransport

    from main import app

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
