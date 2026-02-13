"""Vector similarity guardrail — check if user message is within allowed topics."""

import json
import logging
from pathlib import Path

import faiss
import numpy as np
from openai import AsyncOpenAI

from config import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    OPENAI_API_KEY,
    VECTOR_SIMILARITY_THRESHOLD,
)

logger = logging.getLogger("guardrail.vector")

# Module-level state (initialized at startup)
_topic_index: faiss.IndexFlatIP | None = None
_topic_texts: list[str] = []
_async_client: AsyncOpenAI | None = None


def init_vector_guard() -> None:
    """Load topics from JSON, embed them, build FAISS index.

    Called once at startup in the FastAPI lifespan.
    Uses synchronous OpenAI client for the one-time startup embedding.
    """
    global _topic_index, _topic_texts, _async_client

    from openai import OpenAI

    sync_client = OpenAI(api_key=OPENAI_API_KEY)
    _async_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    # Load topics
    topics_path = Path(__file__).parent / "topics.json"
    with open(topics_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _topic_texts = data["allowed_topics"]

    # Batch embed all topics
    response = sync_client.embeddings.create(model=EMBEDDING_MODEL, input=_topic_texts)
    embeddings = np.array(
        [item.embedding for item in sorted(response.data, key=lambda x: x.index)],
        dtype=np.float32,
    )

    # Build FAISS index (cosine similarity via normalize + inner product)
    faiss.normalize_L2(embeddings)
    _topic_index = faiss.IndexFlatIP(EMBEDDING_DIM)
    _topic_index.add(embeddings)

    logger.info(
        "Vector guard initialized: %d topics, threshold=%.2f",
        len(_topic_texts),
        VECTOR_SIMILARITY_THRESHOLD,
    )


async def check_vector_similarity(message: str) -> tuple[bool, float, str]:
    """Check if message is similar to any allowed topic.

    Returns:
        (passed, max_score, matched_topic_or_reason)
    """
    if _topic_index is None or _async_client is None:
        logger.error("Vector guard not initialized")
        return True, 0.0, "guard_not_initialized"  # Fail-open

    # Embed user message (async)
    response = await _async_client.embeddings.create(
        model=EMBEDDING_MODEL, input=message
    )
    query_vec = np.array(response.data[0].embedding, dtype=np.float32).reshape(1, -1)
    faiss.normalize_L2(query_vec)

    # Search for most similar topic
    scores, indices = _topic_index.search(query_vec, 3)  # Top 3 for logging
    max_score = float(scores[0][0])
    best_topic_idx = int(indices[0][0])
    best_topic = _topic_texts[best_topic_idx] if best_topic_idx >= 0 else "unknown"

    passed = max_score >= VECTOR_SIMILARITY_THRESHOLD

    logger.info(
        "Vector check: score=%.4f threshold=%.2f passed=%s topic='%s' message='%s'",
        max_score,
        VECTOR_SIMILARITY_THRESHOLD,
        passed,
        best_topic,
        message[:100],
    )

    return passed, max_score, best_topic
