"""Tests for guardrail/models.py — Pydantic models for Guardrail Proxy."""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Ensure imports resolve
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GUARDRAIL_DIR = PROJECT_ROOT / "guardrail"
for p in [str(PROJECT_ROOT), str(GUARDRAIL_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from models import GuardCheckResult, GuardRequest, GuardResponse


# ════════════════════════════════════════════════════════════
#  GuardRequest
# ════════════════════════════════════════════════════════════

class TestGuardRequest:
    """Tests for GuardRequest model."""

    def test_create_with_all_fields(self):
        req = GuardRequest(message="hello", session_id="sess_123")
        assert req.message == "hello"
        assert req.session_id == "sess_123"

    def test_create_without_session_id(self):
        req = GuardRequest(message="hello")
        assert req.message == "hello"
        assert req.session_id is None

    def test_session_id_defaults_to_none(self):
        req = GuardRequest(message="test")
        assert req.session_id is None

    def test_message_is_required(self):
        with pytest.raises(ValidationError):
            GuardRequest()

    def test_empty_message_accepted(self):
        req = GuardRequest(message="")
        assert req.message == ""

    def test_long_message(self):
        long_msg = "x" * 10000
        req = GuardRequest(message=long_msg, session_id="s1")
        assert len(req.message) == 10000

    def test_thai_message(self):
        req = GuardRequest(message="สวัสดีค่ะ ขอสอบถามราคาสินค้า")
        assert "สวัสดี" in req.message

    def test_serialization_roundtrip(self):
        req = GuardRequest(message="hi", session_id="s1")
        data = req.model_dump()
        assert data == {"message": "hi", "session_id": "s1"}
        restored = GuardRequest(**data)
        assert restored == req

    def test_json_roundtrip(self):
        req = GuardRequest(message="test", session_id="abc")
        json_str = req.model_dump_json()
        restored = GuardRequest.model_validate_json(json_str)
        assert restored == req

    def test_session_id_none_in_dict(self):
        req = GuardRequest(message="hi")
        data = req.model_dump()
        assert data["session_id"] is None


# ════════════════════════════════════════════════════════════
#  GuardCheckResult
# ════════════════════════════════════════════════════════════

class TestGuardCheckResult:
    """Tests for GuardCheckResult model."""

    def test_create_passed(self):
        result = GuardCheckResult(
            passed=True,
            check_name="vector_similarity",
            score=0.85,
            reason="matched topic",
        )
        assert result.passed is True
        assert result.check_name == "vector_similarity"
        assert result.score == 0.85
        assert result.reason == "matched topic"

    def test_create_failed(self):
        result = GuardCheckResult(
            passed=False,
            check_name="llm_policy",
            score=0.30,
            reason="off-topic request",
        )
        assert result.passed is False
        assert result.score == 0.30

    def test_score_defaults_to_none(self):
        result = GuardCheckResult(passed=True, check_name="test_check")
        assert result.score is None

    def test_reason_defaults_to_empty(self):
        result = GuardCheckResult(passed=True, check_name="test_check")
        assert result.reason == ""

    def test_passed_is_required(self):
        with pytest.raises(ValidationError):
            GuardCheckResult(check_name="test")

    def test_check_name_is_required(self):
        with pytest.raises(ValidationError):
            GuardCheckResult(passed=True)

    def test_score_none_explicit(self):
        result = GuardCheckResult(passed=True, check_name="vec", score=None)
        assert result.score is None

    def test_score_zero(self):
        result = GuardCheckResult(passed=False, check_name="vec", score=0.0)
        assert result.score == 0.0

    def test_score_one(self):
        result = GuardCheckResult(passed=True, check_name="vec", score=1.0)
        assert result.score == 1.0

    def test_serialization(self):
        result = GuardCheckResult(
            passed=True, check_name="llm_policy", score=0.9, reason="ok"
        )
        data = result.model_dump()
        assert data["passed"] is True
        assert data["check_name"] == "llm_policy"
        assert data["score"] == 0.9
        assert data["reason"] == "ok"

    def test_json_roundtrip(self):
        result = GuardCheckResult(
            passed=False, check_name="vector_similarity", score=0.3, reason="blocked"
        )
        json_str = result.model_dump_json()
        restored = GuardCheckResult.model_validate_json(json_str)
        assert restored == result


# ════════════════════════════════════════════════════════════
#  GuardResponse
# ════════════════════════════════════════════════════════════

class TestGuardResponse:
    """Tests for GuardResponse model."""

    def test_create_passed_response(self):
        resp = GuardResponse(
            session_id="s1",
            response="สวัสดีค่ะ",
            passed=True,
        )
        assert resp.session_id == "s1"
        assert resp.response == "สวัสดีค่ะ"
        assert resp.passed is True

    def test_create_blocked_response(self):
        resp = GuardResponse(
            session_id="s2",
            response="ขออภัย ไม่สามารถตอบคำถามนี้ได้ค่ะ",
            passed=False,
        )
        assert resp.passed is False

    def test_session_id_defaults_to_none(self):
        resp = GuardResponse(response="test", passed=True)
        assert resp.session_id is None

    def test_vector_check_defaults_to_none(self):
        resp = GuardResponse(response="test", passed=True)
        assert resp.vector_check is None

    def test_llm_check_defaults_to_none(self):
        resp = GuardResponse(response="test", passed=True)
        assert resp.llm_check is None

    def test_memory_count_defaults_to_zero(self):
        resp = GuardResponse(response="test", passed=True)
        assert resp.memory_count == 0

    def test_image_ids_defaults_to_empty_list(self):
        resp = GuardResponse(response="test", passed=True)
        assert resp.image_ids == []

    def test_with_check_results(self):
        vec = GuardCheckResult(
            passed=True, check_name="vector_similarity", score=0.85, reason="topic1"
        )
        llm = GuardCheckResult(
            passed=True, check_name="llm_policy", score=0.95, reason="ok"
        )
        resp = GuardResponse(
            session_id="s1",
            response="reply",
            passed=True,
            vector_check=vec,
            llm_check=llm,
            memory_count=5,
        )
        assert resp.vector_check.passed is True
        assert resp.llm_check.score == 0.95
        assert resp.memory_count == 5

    def test_with_image_ids(self):
        resp = GuardResponse(
            response="reply",
            passed=True,
            image_ids=["IMG_PROD_001", "IMG_REVIEW_001"],
        )
        assert len(resp.image_ids) == 2
        assert "IMG_PROD_001" in resp.image_ids

    def test_response_is_required(self):
        with pytest.raises(ValidationError):
            GuardResponse(passed=True)

    def test_passed_is_required(self):
        with pytest.raises(ValidationError):
            GuardResponse(response="test")

    def test_full_serialization(self):
        vec = GuardCheckResult(
            passed=True, check_name="vector_similarity", score=0.8, reason="topic"
        )
        llm = GuardCheckResult(
            passed=True, check_name="llm_policy", score=0.9, reason="allowed"
        )
        resp = GuardResponse(
            session_id="s1",
            response="reply text",
            passed=True,
            vector_check=vec,
            llm_check=llm,
            memory_count=3,
            image_ids=["IMG_001"],
        )
        data = resp.model_dump()
        assert data["session_id"] == "s1"
        assert data["vector_check"]["score"] == 0.8
        assert data["llm_check"]["check_name"] == "llm_policy"
        assert data["image_ids"] == ["IMG_001"]

    def test_json_roundtrip(self):
        resp = GuardResponse(
            session_id="s1",
            response="test reply",
            passed=True,
            memory_count=2,
            image_ids=["IMG_PROD_001"],
        )
        json_str = resp.model_dump_json()
        restored = GuardResponse.model_validate_json(json_str)
        assert restored == resp

    def test_nested_check_json_roundtrip(self):
        vec = GuardCheckResult(
            passed=False, check_name="vector_similarity", score=0.2, reason="low"
        )
        llm = GuardCheckResult(
            passed=True, check_name="llm_policy", score=0.9, reason="ok"
        )
        resp = GuardResponse(
            session_id="s1",
            response="reply",
            passed=False,
            vector_check=vec,
            llm_check=llm,
        )
        json_str = resp.model_dump_json()
        restored = GuardResponse.model_validate_json(json_str)
        assert restored.vector_check.score == 0.2
        assert restored.llm_check.passed is True

    def test_empty_image_ids_serializes(self):
        resp = GuardResponse(response="test", passed=True, image_ids=[])
        data = resp.model_dump()
        assert data["image_ids"] == []
