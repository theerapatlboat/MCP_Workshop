"""Tests for mcp-server/models.py — Pydantic models.

NOTE: The mcp-server ``models`` module is pre-imported by conftest.py
via the utilities tool module (which does ``from models import ...``).
We access the class through sys.modules to avoid import conflicts with
guardrail/models.py.
"""

import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Get AddressVerificationResult from the pre-imported mcp-server models
# ---------------------------------------------------------------------------

def _get_avr_class():
    """Return the AddressVerificationResult class from the mcp-server models module."""
    # The utilities module imported it; find it there
    utilities_mod = sys.modules.get("tools.utilities")
    if utilities_mod is not None:
        avr = getattr(utilities_mod, "AddressVerificationResult", None)
        if avr is not None:
            return avr

    # Fallback: try to find the models module from mcp-server
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    MCP_SERVER_DIR = str(PROJECT_ROOT / "mcp-server")

    # Temporarily add mcp-server to path
    added = False
    if MCP_SERVER_DIR not in sys.path:
        sys.path.insert(0, MCP_SERVER_DIR)
        added = True

    # Remove cached wrong models if any
    old_models = sys.modules.pop("models", None)
    try:
        import models as mcp_models
        return mcp_models.AddressVerificationResult
    finally:
        # Restore
        if old_models is not None:
            sys.modules["models"] = old_models
        elif "models" in sys.modules:
            del sys.modules["models"]
        if added:
            sys.path.remove(MCP_SERVER_DIR)


AddressVerificationResult = _get_avr_class()


# ---------------------------------------------------------------------------
# AddressVerificationResult
# ---------------------------------------------------------------------------

class TestAddressVerificationResult:

    def test_valid_address(self):
        result = AddressVerificationResult(
            is_valid=True, missing_fields=[], message="All fields present",
        )
        assert result.is_valid is True
        assert result.missing_fields == []
        assert result.message == "All fields present"

    def test_invalid_address_with_missing_fields(self):
        result = AddressVerificationResult(
            is_valid=False,
            missing_fields=["name", "tel", "postal_code"],
            message="Missing required fields",
        )
        assert result.is_valid is False
        assert len(result.missing_fields) == 3
        assert "name" in result.missing_fields

    def test_serialization_round_trip(self):
        original = AddressVerificationResult(
            is_valid=False, missing_fields=["address"],
            message="Address verification failed",
        )
        data = original.model_dump()
        assert data["is_valid"] is False
        assert data["missing_fields"] == ["address"]

        restored = AddressVerificationResult(**data)
        assert restored == original

    def test_json_serialization(self):
        result = AddressVerificationResult(
            is_valid=True, missing_fields=[], message="OK",
        )
        json_str = result.model_dump_json()
        assert '"is_valid":true' in json_str or '"is_valid": true' in json_str

    def test_empty_missing_fields_list(self):
        result = AddressVerificationResult(
            is_valid=True, missing_fields=[], message="All good",
        )
        assert isinstance(result.missing_fields, list)
        assert len(result.missing_fields) == 0

    def test_multiple_missing_fields(self):
        fields = ["name", "tel", "address", "sub_district",
                   "district", "province", "postal_code"]
        result = AddressVerificationResult(
            is_valid=False, missing_fields=fields, message="All fields missing",
        )
        assert len(result.missing_fields) == 7

    def test_model_has_field_descriptions(self):
        schema = AddressVerificationResult.model_json_schema()
        props = schema["properties"]
        assert "description" in props["is_valid"]
        assert "description" in props["missing_fields"]
        assert "description" in props["message"]

    def test_model_requires_all_fields(self):
        with pytest.raises(Exception):
            AddressVerificationResult()  # type: ignore[call-arg]

    def test_model_rejects_invalid_is_valid_type(self):
        with pytest.raises(Exception):
            AddressVerificationResult(
                is_valid="not_a_bool_string",  # type: ignore[arg-type]
                missing_fields=[], message="test",
            )
