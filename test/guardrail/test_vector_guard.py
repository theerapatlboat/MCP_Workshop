"""Tests for guardrail/vector_guard.py — vector similarity guardrail."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import faiss
import numpy as np
import pytest

# Ensure imports resolve
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GUARDRAIL_DIR = PROJECT_ROOT / "guardrail"
for p in [str(PROJECT_ROOT), str(GUARDRAIL_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import vector_guard
from vector_guard import check_vector_similarity, init_vector_guard


# ════════════════════════════════════════════════════════════
#  init_vector_guard
# ════════════════════════════════════════════════════════════

class TestInitVectorGuard:
    """Tests for init_vector_guard().

    Note: OpenAI is imported locally inside init_vector_guard via
    ``from openai import OpenAI``, so we patch ``openai.OpenAI`` (the
    source module) rather than ``vector_guard.OpenAI``.
    """

    def test_initializes_topic_index(self, mock_sync_openai_client):
        """After init, _topic_index should be a FAISS index."""
        with patch("openai.OpenAI", return_value=mock_sync_openai_client), \
             patch("vector_guard.AsyncOpenAI") as MockAsync:
            MockAsync.return_value = AsyncMock()
            init_vector_guard()

        assert vector_guard._topic_index is not None
        assert isinstance(vector_guard._topic_index, faiss.IndexFlatIP)

    def test_initializes_async_client(self, mock_sync_openai_client):
        """After init, _async_client should be set."""
        with patch("openai.OpenAI", return_value=mock_sync_openai_client), \
             patch("vector_guard.AsyncOpenAI") as MockAsync:
            mock_async = AsyncMock()
            MockAsync.return_value = mock_async
            init_vector_guard()

        assert vector_guard._async_client is mock_async

    def test_loads_topic_texts(self, mock_sync_openai_client):
        """After init, _topic_texts should be populated from topics.json."""
        with patch("openai.OpenAI", return_value=mock_sync_openai_client), \
             patch("vector_guard.AsyncOpenAI") as MockAsync:
            MockAsync.return_value = AsyncMock()
            init_vector_guard()

        assert len(vector_guard._topic_texts) > 0
        assert isinstance(vector_guard._topic_texts, list)

    def test_topic_texts_match_json(self, mock_sync_openai_client):
        """_topic_texts should match allowed_topics from topics.json."""
        topics_path = GUARDRAIL_DIR / "topics.json"
        with open(topics_path, "r", encoding="utf-8") as f:
            expected = json.load(f)["allowed_topics"]

        with patch("openai.OpenAI", return_value=mock_sync_openai_client), \
             patch("vector_guard.AsyncOpenAI") as MockAsync:
            MockAsync.return_value = AsyncMock()
            init_vector_guard()

        assert vector_guard._topic_texts == expected

    def test_faiss_index_has_correct_count(self, mock_sync_openai_client):
        """FAISS index should have same count as allowed_topics."""
        topics_path = GUARDRAIL_DIR / "topics.json"
        with open(topics_path, "r", encoding="utf-8") as f:
            expected_count = len(json.load(f)["allowed_topics"])

        with patch("openai.OpenAI", return_value=mock_sync_openai_client), \
             patch("vector_guard.AsyncOpenAI") as MockAsync:
            MockAsync.return_value = AsyncMock()
            init_vector_guard()

        assert vector_guard._topic_index.ntotal == expected_count

    def test_uses_openai_api_key(self, mock_sync_openai_client):
        """Verify the OpenAI clients are created during init."""
        with patch("openai.OpenAI") as MockSync, \
             patch("vector_guard.AsyncOpenAI") as MockAsync:
            MockSync.return_value = mock_sync_openai_client
            MockAsync.return_value = AsyncMock()
            init_vector_guard()

        MockSync.assert_called_once()
        MockAsync.assert_called_once()

    def test_calls_embeddings_batch(self, mock_sync_openai_client):
        """init should call get_embeddings_batch with the topic texts."""
        with patch("openai.OpenAI", return_value=mock_sync_openai_client), \
             patch("vector_guard.AsyncOpenAI") as MockAsync, \
             patch("vector_guard.get_embeddings_batch", wraps=vector_guard.get_embeddings_batch) as mock_embed:
            MockAsync.return_value = AsyncMock()
            init_vector_guard()

        mock_embed.assert_called_once()
        args = mock_embed.call_args
        assert args[0][0] is mock_sync_openai_client  # client
        assert isinstance(args[0][1], list)  # topics list


# ════════════════════════════════════════════════════════════
#  check_vector_similarity — fail-open
# ════════════════════════════════════════════════════════════

class TestCheckVectorSimilarityFailOpen:
    """Tests for fail-open behavior when guard is not initialized."""

    @pytest.mark.asyncio
    async def test_not_initialized_returns_true(self):
        """When guard is not initialized, should fail-open (pass)."""
        passed, score, reason = await check_vector_similarity("any message")
        assert passed is True
        assert score == 0.0
        assert reason == "guard_not_initialized"

    @pytest.mark.asyncio
    async def test_index_none_fails_open(self):
        """Explicitly None index means fail-open."""
        vector_guard._topic_index = None
        vector_guard._async_client = AsyncMock()
        passed, score, reason = await check_vector_similarity("test")
        assert passed is True

    @pytest.mark.asyncio
    async def test_client_none_fails_open(self, mock_faiss_index, sample_topic_texts):
        """Explicitly None client means fail-open."""
        vector_guard._topic_index = mock_faiss_index
        vector_guard._topic_texts = sample_topic_texts
        vector_guard._async_client = None
        passed, score, reason = await check_vector_similarity("test")
        assert passed is True


# ════════════════════════════════════════════════════════════
#  check_vector_similarity — initialized behavior
# ════════════════════════════════════════════════════════════

class TestCheckVectorSimilarityInitialized:
    """Tests for check_vector_similarity when guard is properly initialized."""

    @pytest.fixture(autouse=True)
    def setup_guard(self, mock_faiss_index, sample_topic_texts, mock_async_openai_client):
        """Set up vector guard module state for each test."""
        vector_guard._topic_index = mock_faiss_index
        vector_guard._topic_texts = sample_topic_texts
        vector_guard._async_client = mock_async_openai_client

    @pytest.mark.asyncio
    async def test_returns_tuple_of_three(self):
        result = await check_vector_similarity("ราคาสินค้า")
        assert isinstance(result, tuple)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_returns_bool_float_str(self):
        passed, score, topic = await check_vector_similarity("ราคาสินค้า")
        assert isinstance(passed, bool)
        assert isinstance(score, float)
        assert isinstance(topic, str)

    @pytest.mark.asyncio
    async def test_score_in_valid_range(self):
        """Score should be between -1 and 1 (cosine similarity)."""
        _, score, _ = await check_vector_similarity("ราคาสินค้า")
        assert -1.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_calls_embeddings_api(self, mock_async_openai_client):
        await check_vector_similarity("test message")
        mock_async_openai_client.embeddings.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_embedding_uses_correct_model(self, mock_async_openai_client):
        await check_vector_similarity("test message")
        call_kwargs = mock_async_openai_client.embeddings.create.call_args
        assert call_kwargs.kwargs.get("model") == "text-embedding-3-small" or \
               (call_kwargs.args and call_kwargs.args[0] == "text-embedding-3-small") or \
               "text-embedding-3-small" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_returns_matched_topic_text(self):
        """The reason field should be one of the topic texts."""
        _, _, topic = await check_vector_similarity("ราคาสินค้า")
        assert topic in vector_guard._topic_texts or topic == "unknown"

    @pytest.mark.asyncio
    async def test_high_threshold_blocks(self, monkeypatch):
        """With a very high threshold, most messages should be blocked."""
        monkeypatch.setattr("vector_guard.VECTOR_SIMILARITY_THRESHOLD", 0.999)
        passed, score, _ = await check_vector_similarity("random text")
        # With random embeddings, score is unlikely to exceed 0.999
        # but we still verify the logic
        if score < 0.999:
            assert passed is False

    @pytest.mark.asyncio
    async def test_zero_threshold_passes(self, monkeypatch):
        """With threshold=0, everything should pass."""
        monkeypatch.setattr("vector_guard.VECTOR_SIMILARITY_THRESHOLD", 0.0)
        passed, _, _ = await check_vector_similarity("absolutely anything")
        assert passed is True

    @pytest.mark.asyncio
    async def test_negative_threshold_passes(self, monkeypatch):
        """With threshold=-1, everything should pass."""
        monkeypatch.setattr("vector_guard.VECTOR_SIMILARITY_THRESHOLD", -1.0)
        passed, _, _ = await check_vector_similarity("anything at all")
        assert passed is True

    @pytest.mark.asyncio
    async def test_empty_message(self):
        """Empty message should still return a result."""
        passed, score, topic = await check_vector_similarity("")
        assert isinstance(passed, bool)
        assert isinstance(score, float)

    @pytest.mark.asyncio
    async def test_long_message(self):
        """Long messages should not crash."""
        long_msg = "สินค้า " * 1000
        passed, score, topic = await check_vector_similarity(long_msg)
        assert isinstance(passed, bool)

    @pytest.mark.asyncio
    async def test_best_topic_index_negative_returns_unknown(self):
        """If FAISS returns -1 index, should handle gracefully."""
        # Create a mock index that returns -1
        mock_idx = MagicMock()
        mock_idx.search.return_value = (
            np.array([[0.5, 0.3, 0.1]], dtype=np.float32),
            np.array([[-1, -1, -1]], dtype=np.int64),
        )
        vector_guard._topic_index = mock_idx
        _, _, topic = await check_vector_similarity("test")
        assert topic == "unknown"
