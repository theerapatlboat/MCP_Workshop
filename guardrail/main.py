"""Guardrail Proxy API — sits between webhook and agent API.

Validates incoming messages through:
  1. Vector similarity check (is the topic allowed?)
  2. LLM policy check (does it follow business rules?)

Both must pass for the message to reach the agent.

Usage:
    cd guardrail && python main.py
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI

from config import AGENT_API_URL, GUARDRAIL_PORT
from llm_guard import check_llm_policy, init_llm_guard
from models import GuardCheckResult, GuardRequest, GuardResponse
from vector_guard import check_vector_similarity, init_vector_guard

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("guardrail")
logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s")

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = RotatingFileHandler(
    LOG_DIR / "guardrail.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Load rejection message from topics.json
_topics_path = Path(__file__).parent / "topics.json"
with open(_topics_path, "r", encoding="utf-8") as f:
    _topics_data = json.load(f)
REJECTION_MESSAGE_TH = _topics_data.get(
    "rejection_message_th", "ขออภัย ไม่สามารถตอบคำถามนี้ได้ค่ะ"
)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # -- Startup --
    logger.info("Initializing guardrail systems...")
    init_vector_guard()
    init_llm_guard()
    logger.info(
        "Guardrail proxy ready on port %d -> Agent API at %s",
        GUARDRAIL_PORT,
        AGENT_API_URL,
    )
    yield
    # -- Shutdown --
    logger.info("Guardrail proxy shutting down")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Guardrail Proxy API", lifespan=lifespan)


# ---------------------------------------------------------------------------
# POST /guard — main endpoint
# ---------------------------------------------------------------------------
@app.post("/guard", response_model=GuardResponse)
async def guard(req: GuardRequest):
    """Validate message through both guard systems, forward if passed."""
    logger.info(
        "Guard request: session=%s message='%s'", req.session_id, req.message[:100]
    )

    # Run both checks in parallel
    (vec_passed, vec_score, vec_topic), (llm_passed, llm_confidence, llm_reason) = (
        await asyncio.gather(
            check_vector_similarity(req.message),
            check_llm_policy(req.message),
        )
    )

    vector_result = GuardCheckResult(
        passed=vec_passed,
        check_name="vector_similarity",
        score=vec_score,
        reason=vec_topic,
    )
    llm_result = GuardCheckResult(
        passed=llm_passed,
        check_name="llm_policy",
        score=llm_confidence,
        reason=llm_reason,
    )

    # Both must pass
    overall_passed = vec_passed and llm_passed

    if not overall_passed:
        blocked_by = []
        if not vec_passed:
            blocked_by.append(f"vector(score={vec_score:.4f})")
        if not llm_passed:
            blocked_by.append(f"llm(reason={llm_reason})")
        logger.warning(
            "BLOCKED: session=%s blocked_by=%s message='%s'",
            req.session_id,
            ", ".join(blocked_by),
            req.message[:100],
        )

        return GuardResponse(
            session_id=req.session_id,
            response=REJECTION_MESSAGE_TH,
            passed=False,
            vector_check=vector_result,
            llm_check=llm_result,
        )

    # Forward to agent API
    logger.info("PASSED: session=%s forwarding to agent", req.session_id)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                AGENT_API_URL,
                json={"session_id": req.session_id, "message": req.message},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            agent_reply = data.get("response", data.get("reply", ""))
            memory_count = data.get("memory_count", 0)
            image_ids = data.get("image_ids", [])
    except Exception as exc:
        logger.error("Agent API request failed: %s", exc)
        agent_reply = "ขออภัย ระบบไม่สามารถประมวลผลได้ในขณะนี้"
        memory_count = 0
        image_ids = []

    return GuardResponse(
        session_id=req.session_id,
        response=agent_reply,
        passed=True,
        vector_check=vector_result,
        llm_check=llm_result,
        memory_count=memory_count,
        image_ids=image_ids,
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "service": "guardrail-proxy"}


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=GUARDRAIL_PORT, reload=True)
