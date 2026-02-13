"""Pydantic models for Guardrail Proxy."""

from pydantic import BaseModel, Field


class GuardRequest(BaseModel):
    """Incoming request — same shape as agent ChatRequest."""

    message: str
    session_id: str | None = Field(
        default=None, description="Session ID from webhook"
    )


class GuardCheckResult(BaseModel):
    """Result of a single guard check."""

    passed: bool
    check_name: str
    score: float | None = Field(
        default=None, description="Similarity score or confidence"
    )
    reason: str = ""


class GuardResponse(BaseModel):
    """Response from the guardrail proxy."""

    session_id: str | None = None
    response: str
    passed: bool
    vector_check: GuardCheckResult | None = None
    llm_check: GuardCheckResult | None = None
    memory_count: int = 0
