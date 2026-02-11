"""Pydantic models shared across MCP tools."""

from pydantic import BaseModel, Field


class AddressVerificationResult(BaseModel):
    """Result of address verification."""
    is_valid: bool = Field(description="Whether the address has sufficient data")
    missing_fields: list[str] = Field(description="List of missing required fields")
    message: str = Field(description="Verification status message")
