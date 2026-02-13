"""Tests for mcp-server/tools/utilities.py — verify_address, faq, intent_classify."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MCP_SERVER_DIR = PROJECT_ROOT / "mcp-server"
for p in [str(PROJECT_ROOT), str(MCP_SERVER_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestUtilitiesRegistration:

    def test_all_three_tools_registered(self, utility_tools):
        expected = {"verify_address", "faq", "intent_classify"}
        assert set(utility_tools.keys()) == expected


# ---------------------------------------------------------------------------
# verify_address
# ---------------------------------------------------------------------------

class TestVerifyAddress:

    def test_all_fields_present(self, utility_tools):
        result = utility_tools["verify_address"](
            name="John",
            tel="0800000000",
            address="123 St",
            sub_district="Bangrak",
            district="Bangrak",
            province="Bangkok",
            postal_code="10500",
        )

        assert result.is_valid is True
        assert result.missing_fields == []
        assert "passed" in result.message.lower() or "present" in result.message.lower()

    def test_all_fields_missing(self, utility_tools):
        result = utility_tools["verify_address"]()

        assert result.is_valid is False
        assert len(result.missing_fields) == 7
        expected_fields = {"name", "tel", "address", "sub_district",
                           "district", "province", "postal_code"}
        assert set(result.missing_fields) == expected_fields

    def test_partial_fields_missing(self, utility_tools):
        result = utility_tools["verify_address"](
            name="Jane",
            tel="0811111111",
            address="456 Ave",
        )

        assert result.is_valid is False
        assert "sub_district" in result.missing_fields
        assert "district" in result.missing_fields
        assert "province" in result.missing_fields
        assert "postal_code" in result.missing_fields
        assert "name" not in result.missing_fields
        assert "tel" not in result.missing_fields
        assert "address" not in result.missing_fields

    def test_empty_string_treated_as_missing(self, utility_tools):
        result = utility_tools["verify_address"](
            name="",
            tel="0800000000",
            address="123",
            sub_district="A",
            district="B",
            province="C",
            postal_code="10000",
        )

        assert result.is_valid is False
        assert "name" in result.missing_fields

    def test_whitespace_only_treated_as_missing(self, utility_tools):
        result = utility_tools["verify_address"](
            name="  ",
            tel="0800000000",
            address="123",
            sub_district="A",
            district="B",
            province="C",
            postal_code="10000",
        )

        assert result.is_valid is False
        assert "name" in result.missing_fields

    def test_none_value_treated_as_missing(self, utility_tools):
        result = utility_tools["verify_address"](
            name=None,
            tel="0800000000",
            address="123",
            sub_district="A",
            district="B",
            province="C",
            postal_code="10000",
        )

        assert result.is_valid is False
        assert "name" in result.missing_fields

    def test_message_lists_missing_fields(self, utility_tools):
        result = utility_tools["verify_address"](
            name="John",
            tel=None,
            address="123",
            postal_code="10000",
        )

        assert "tel" in result.message
        assert "sub_district" in result.message
        assert "district" in result.message
        assert "province" in result.message

    def test_returns_address_verification_result_type(self, utility_tools):
        result = utility_tools["verify_address"](name="X")
        # Use type name check to avoid cross-module isinstance issues
        assert type(result).__name__ == "AddressVerificationResult"
        assert hasattr(result, "is_valid")
        assert hasattr(result, "missing_fields")
        assert hasattr(result, "message")


# ---------------------------------------------------------------------------
# faq
# ---------------------------------------------------------------------------

class TestFaq:

    def test_returns_answer(self, utility_tools, mock_openai):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = "You can track your order on our website."
        mock_openai.chat.completions.create.return_value = resp

        result = utility_tools["faq"](question="How do I track my order?")

        assert result["success"] is True
        assert result["question"] == "How do I track my order?"
        assert result["answer"] == "You can track your order on our website."

    def test_calls_openai_with_correct_model(self, utility_tools, mock_openai):
        utility_tools["faq"](question="test")

        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-mini"

    def test_system_prompt_is_support_assistant(self, utility_tools, mock_openai):
        utility_tools["faq"](question="What is your return policy?")

        messages = mock_openai.chat.completions.create.call_args.kwargs["messages"]
        system_msg = messages[0]
        assert system_msg["role"] == "system"
        assert "customer support" in system_msg["content"].lower()

    def test_user_question_passed_in_messages(self, utility_tools, mock_openai):
        utility_tools["faq"](question="Where is my package?")

        messages = mock_openai.chat.completions.create.call_args.kwargs["messages"]
        user_msg = messages[1]
        assert user_msg["role"] == "user"
        assert user_msg["content"] == "Where is my package?"

    def test_max_tokens_is_500(self, utility_tools, mock_openai):
        utility_tools["faq"](question="test")

        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 500


# ---------------------------------------------------------------------------
# intent_classify
# ---------------------------------------------------------------------------

class TestIntentClassify:

    def test_valid_json_response(self, utility_tools, mock_openai):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = '{"intent": "order", "confidence": 0.95}'
        mock_openai.chat.completions.create.return_value = resp

        result = utility_tools["intent_classify"](message="I want to place an order")

        assert result["success"] is True
        assert result["message"] == "I want to place an order"
        assert result["intent"] == "order"
        assert result["confidence"] == 0.95

    def test_tracking_intent(self, utility_tools, mock_openai):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = '{"intent": "tracking", "confidence": 0.88}'
        mock_openai.chat.completions.create.return_value = resp

        result = utility_tools["intent_classify"](message="Where is my package?")

        assert result["intent"] == "tracking"
        assert result["confidence"] == 0.88

    def test_greeting_intent(self, utility_tools, mock_openai):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = '{"intent": "greeting", "confidence": 0.99}'
        mock_openai.chat.completions.create.return_value = resp

        result = utility_tools["intent_classify"](message="Hello!")

        assert result["intent"] == "greeting"

    def test_invalid_json_fallback(self, utility_tools, mock_openai):
        """When LLM returns non-JSON, intent_classify falls back gracefully."""
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = "order"
        mock_openai.chat.completions.create.return_value = resp

        result = utility_tools["intent_classify"](message="Buy product")

        assert result["success"] is True
        assert result["intent"] == "order"
        assert result["confidence"] == 0.0

    def test_missing_intent_key_defaults_to_other(self, utility_tools, mock_openai):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = '{"confidence": 0.5}'
        mock_openai.chat.completions.create.return_value = resp

        result = utility_tools["intent_classify"](message="hmm")

        assert result["intent"] == "other"

    def test_missing_confidence_defaults_to_zero(self, utility_tools, mock_openai):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = '{"intent": "complaint"}'
        mock_openai.chat.completions.create.return_value = resp

        result = utility_tools["intent_classify"](message="This is broken!")

        assert result["confidence"] == 0.0

    def test_uses_gpt4o_mini(self, utility_tools, mock_openai):
        utility_tools["intent_classify"](message="test")

        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-mini"

    def test_max_tokens_is_50(self, utility_tools, mock_openai):
        utility_tools["intent_classify"](message="test")

        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 50

    def test_whitespace_in_response_is_stripped(self, utility_tools, mock_openai):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = '  {"intent": "inquiry", "confidence": 0.7}  '
        mock_openai.chat.completions.create.return_value = resp

        result = utility_tools["intent_classify"](message="What products do you have?")

        assert result["intent"] == "inquiry"
        assert result["confidence"] == 0.7
