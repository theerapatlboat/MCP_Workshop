"""Tests for agent/agent_api.py — FastAPI chat endpoint and helpers."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "agent"))

from agent.agent_api import parse_image_markers, _filter_history_for_storage, IMG_MARKER_PATTERN


# ════════════════════════════════════════════════════════════
#  parse_image_markers
# ════════════════════════════════════════════════════════════

def test_parse_image_markers_single():
    text = "ข้อมูลสินค้า <<IMG:IMG_PROD_001>>"
    clean, ids = parse_image_markers(text)
    assert clean == "ข้อมูลสินค้า"
    assert ids == ["IMG_PROD_001"]


def test_parse_image_markers_multiple():
    text = "ข้อมูล <<IMG:IMG_PROD_001>> <<IMG:IMG_REVIEW_001>>"
    clean, ids = parse_image_markers(text)
    assert clean == "ข้อมูล"
    assert ids == ["IMG_PROD_001", "IMG_REVIEW_001"]


def test_parse_image_markers_no_markers():
    text = "สวัสดีครับ"
    clean, ids = parse_image_markers(text)
    assert clean == "สวัสดีครับ"
    assert ids == []


def test_parse_image_markers_empty_string():
    clean, ids = parse_image_markers("")
    assert clean == ""
    assert ids == []


def test_parse_image_markers_deduplicates():
    text = "text <<IMG:IMG_PROD_001>> more <<IMG:IMG_PROD_001>>"
    clean, ids = parse_image_markers(text)
    assert ids == ["IMG_PROD_001"]
    assert len(ids) == 1


def test_parse_image_markers_preserves_order():
    text = "<<IMG:IMG_REVIEW_001>> <<IMG:IMG_PROD_001>> <<IMG:IMG_REVIEW_001>>"
    clean, ids = parse_image_markers(text)
    assert ids == ["IMG_REVIEW_001", "IMG_PROD_001"]


def test_parse_image_markers_various_prefixes():
    text = "<<IMG:IMG_CERT_001>> <<IMG:IMG_RECIPE_002>> <<IMG:IMG_MARKETING_001>>"
    clean, ids = parse_image_markers(text)
    assert "IMG_CERT_001" in ids
    assert "IMG_RECIPE_002" in ids
    assert "IMG_MARKETING_001" in ids
    assert len(ids) == 3


def test_parse_image_markers_strips_whitespace():
    text = "text  <<IMG:IMG_PROD_001>>  "
    clean, ids = parse_image_markers(text)
    assert clean == "text"
    assert ids == ["IMG_PROD_001"]


def test_img_marker_pattern_regex():
    matches = IMG_MARKER_PATTERN.findall("<<IMG:IMG_PROD_001>> <<IMG:IMG_REVIEW_002>>")
    assert matches == ["IMG_PROD_001", "IMG_REVIEW_002"]


def test_img_marker_pattern_no_match_lowercase():
    matches = IMG_MARKER_PATTERN.findall("<<IMG:img_prod_001>>")
    assert matches == []


# ════════════════════════════════════════════════════════════
#  _filter_history_for_storage
# ════════════════════════════════════════════════════════════

def test_filter_history_keeps_user_messages():
    items = [{"role": "user", "content": "hello"}]
    assert _filter_history_for_storage(items) == items


def test_filter_history_keeps_assistant_messages():
    items = [{"role": "assistant", "content": "hi"}]
    assert _filter_history_for_storage(items) == items


def test_filter_history_keeps_message_type():
    items = [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "hi"}]}]
    assert _filter_history_for_storage(items) == items


def test_filter_history_removes_function_call():
    items = [{"type": "function_call", "name": "search", "arguments": "{}"}]
    assert _filter_history_for_storage(items) == []


def test_filter_history_removes_function_call_output():
    items = [{"type": "function_call_output", "output": "result"}]
    assert _filter_history_for_storage(items) == []


def test_filter_history_skips_non_dict_items():
    items = ["string_item", None, {"role": "user", "content": "hi"}]
    result = _filter_history_for_storage(items)
    assert len(result) == 1
    assert result[0]["role"] == "user"


def test_filter_history_mixed_items():
    items = [
        {"role": "user", "content": "hello"},
        {"type": "function_call", "name": "search", "arguments": "{}"},
        {"type": "function_call_output", "output": "result"},
        {"role": "assistant", "content": "response"},
    ]
    result = _filter_history_for_storage(items)
    assert len(result) == 2
    assert result[0]["role"] == "user"
    assert result[1]["role"] == "assistant"


def test_filter_history_empty_list():
    assert _filter_history_for_storage([]) == []


# ════════════════════════════════════════════════════════════
#  Pydantic models
# ════════════════════════════════════════════════════════════

def test_chat_request_with_session_id():
    from agent.agent_api import ChatRequest
    req = ChatRequest(message="hi", session_id="test123")
    assert req.message == "hi"
    assert req.session_id == "test123"


def test_chat_request_without_session_id():
    from agent.agent_api import ChatRequest
    req = ChatRequest(message="hi")
    assert req.session_id is None


def test_chat_response_default_image_ids():
    from agent.agent_api import ChatResponse
    resp = ChatResponse(session_id="s1", response="hi", memory_count=0)
    assert resp.image_ids == []


# ════════════════════════════════════════════════════════════
#  POST /chat endpoint
# ════════════════════════════════════════════════════════════

@pytest.fixture
def mock_session_store(tmp_path):
    from agent.session_store import SessionStore
    return SessionStore(db_path=tmp_path / "test_api.db", max_messages=50, ttl_hours=24)


@pytest.fixture
def mock_agent():
    return MagicMock(name="MockAgent")


@pytest.fixture
def mock_runner_result():
    result = MagicMock()
    result.final_output = "สวัสดีครับ"
    result.to_input_list.return_value = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "สวัสดีครับ"},
    ]
    return result


@pytest.mark.asyncio
async def test_chat_endpoint_success(mock_session_store, mock_agent, mock_runner_result):
    import httpx
    from httpx import ASGITransport

    with patch("agent.agent_api.agent", mock_agent), \
         patch("agent.agent_api.session_store", mock_session_store), \
         patch("agent.agent_api.Runner") as MockRunner, \
         patch("agent.agent_api.trace"):
        MockRunner.run = AsyncMock(return_value=mock_runner_result)

        from agent.agent_api import app
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/chat", json={"message": "hello"})

    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["response"] == "สวัสดีครับ"
    assert data["image_ids"] == []


@pytest.mark.asyncio
async def test_chat_endpoint_uses_provided_session_id(mock_session_store, mock_agent, mock_runner_result):
    import httpx
    from httpx import ASGITransport

    with patch("agent.agent_api.agent", mock_agent), \
         patch("agent.agent_api.session_store", mock_session_store), \
         patch("agent.agent_api.Runner") as MockRunner, \
         patch("agent.agent_api.trace"):
        MockRunner.run = AsyncMock(return_value=mock_runner_result)

        from agent.agent_api import app
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/chat", json={"message": "hi", "session_id": "test123"})

    assert resp.json()["session_id"] == "test123"


@pytest.mark.asyncio
async def test_chat_endpoint_with_image_markers(mock_session_store, mock_agent):
    import httpx
    from httpx import ASGITransport

    result = MagicMock()
    result.final_output = "รูปสินค้า <<IMG:IMG_PROD_001>> <<IMG:IMG_REVIEW_001>>"
    result.to_input_list.return_value = [
        {"role": "user", "content": "show"},
        {"role": "assistant", "content": "รูปสินค้า <<IMG:IMG_PROD_001>> <<IMG:IMG_REVIEW_001>>"},
    ]

    with patch("agent.agent_api.agent", mock_agent), \
         patch("agent.agent_api.session_store", mock_session_store), \
         patch("agent.agent_api.Runner") as MockRunner, \
         patch("agent.agent_api.trace"):
        MockRunner.run = AsyncMock(return_value=result)

        from agent.agent_api import app
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/chat", json={"message": "show"})

    data = resp.json()
    assert data["response"] == "รูปสินค้า"
    assert data["image_ids"] == ["IMG_PROD_001", "IMG_REVIEW_001"]


@pytest.mark.asyncio
async def test_chat_endpoint_general_exception(mock_session_store, mock_agent):
    import httpx
    from httpx import ASGITransport
    from shared.constants import ERROR_SYSTEM_UNAVAILABLE

    with patch("agent.agent_api.agent", mock_agent), \
         patch("agent.agent_api.session_store", mock_session_store), \
         patch("agent.agent_api.Runner") as MockRunner, \
         patch("agent.agent_api.trace"):
        MockRunner.run = AsyncMock(side_effect=RuntimeError("unexpected"))

        from agent.agent_api import app
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/chat", json={"message": "hi"})

    data = resp.json()
    assert data["response"] == ERROR_SYSTEM_UNAVAILABLE


@pytest.mark.asyncio
async def test_chat_endpoint_no_final_output(mock_session_store, mock_agent):
    import httpx
    from httpx import ASGITransport
    from shared.constants import ERROR_NO_OUTPUT

    result = MagicMock()
    result.final_output = None
    result.to_input_list.return_value = [{"role": "user", "content": "hi"}]

    with patch("agent.agent_api.agent", mock_agent), \
         patch("agent.agent_api.session_store", mock_session_store), \
         patch("agent.agent_api.Runner") as MockRunner, \
         patch("agent.agent_api.trace"):
        MockRunner.run = AsyncMock(return_value=result)

        from agent.agent_api import app
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/chat", json={"message": "hi"})

    data = resp.json()
    assert ERROR_NO_OUTPUT in data["response"]


@pytest.mark.asyncio
async def test_chat_endpoint_history_save_exception(mock_session_store, mock_agent):
    import httpx
    from httpx import ASGITransport
    from shared.constants import ERROR_PROCESSING

    result = MagicMock()
    result.final_output = "ok"
    result.to_input_list.side_effect = TypeError("bad data")

    with patch("agent.agent_api.agent", mock_agent), \
         patch("agent.agent_api.session_store", mock_session_store), \
         patch("agent.agent_api.Runner") as MockRunner, \
         patch("agent.agent_api.trace"):
        MockRunner.run = AsyncMock(return_value=result)

        from agent.agent_api import app
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/chat", json={"message": "hi"})

    data = resp.json()
    assert ERROR_PROCESSING in data["response"]
