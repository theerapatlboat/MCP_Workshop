"""Tests for guardrail/llm_guard.py — LLM policy guardrail."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure imports resolve
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GUARDRAIL_DIR = PROJECT_ROOT / "guardrail"
for p in [str(PROJECT_ROOT), str(GUARDRAIL_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import llm_guard
from llm_guard import POLICY_SYSTEM_PROMPT, check_llm_policy, init_llm_guard


# ════════════════════════════════════════════════════════════
#  POLICY_SYSTEM_PROMPT
# ════════════════════════════════════════════════════════════

class TestPolicySystemPrompt:
    """Verify POLICY_SYSTEM_PROMPT contains key elements."""

    def test_prompt_is_string(self):
        assert isinstance(POLICY_SYSTEM_PROMPT, str)

    def test_prompt_not_empty(self):
        assert len(POLICY_SYSTEM_PROMPT) > 0

    def test_prompt_mentions_allowed(self):
        assert "ALLOWED" in POLICY_SYSTEM_PROMPT

    def test_prompt_mentions_blocked(self):
        assert "BLOCKED" in POLICY_SYSTEM_PROMPT

    def test_prompt_mentions_json_response(self):
        assert "JSON" in POLICY_SYSTEM_PROMPT

    def test_prompt_mentions_product_context(self):
        assert "ผงเครื่องเทศ" in POLICY_SYSTEM_PROMPT or "spice" in POLICY_SYSTEM_PROMPT

    def test_prompt_mentions_fail_open_rule(self):
        """The prompt should bias toward ALLOW when in doubt."""
        assert "ALLOW" in POLICY_SYSTEM_PROMPT

    def test_prompt_mentions_confidence(self):
        assert "confidence" in POLICY_SYSTEM_PROMPT


# ════════════════════════════════════════════════════════════
#  init_llm_guard
# ════════════════════════════════════════════════════════════

class TestInitLlmGuard:
    """Tests for init_llm_guard()."""

    def test_initializes_async_client(self):
        with patch("llm_guard.AsyncOpenAI") as MockAsync:
            mock_client = AsyncMock()
            MockAsync.return_value = mock_client
            init_llm_guard()

        assert llm_guard._async_client is mock_client

    def test_creates_client_with_api_key(self):
        with patch("llm_guard.AsyncOpenAI") as MockAsync:
            MockAsync.return_value = AsyncMock()
            init_llm_guard()

        MockAsync.assert_called_once()

    def test_can_reinitialize(self):
        """Calling init twice should update the client."""
        with patch("llm_guard.AsyncOpenAI") as MockAsync:
            first = AsyncMock()
            second = AsyncMock()
            MockAsync.side_effect = [first, second]
            init_llm_guard()
            assert llm_guard._async_client is first
            init_llm_guard()
            assert llm_guard._async_client is second


# ════════════════════════════════════════════════════════════
#  check_llm_policy — fail-open (not initialized)
# ════════════════════════════════════════════════════════════

class TestCheckLlmPolicyFailOpen:
    """Tests for fail-open behavior when guard is not initialized."""

    @pytest.mark.asyncio
    async def test_not_initialized_returns_true(self):
        """When client is None, should fail-open."""
        passed, confidence, reason = await check_llm_policy("any message")
        assert passed is True
        assert confidence == 0.0
        assert reason == "guard_not_initialized"

    @pytest.mark.asyncio
    async def test_not_initialized_score_zero(self):
        passed, confidence, reason = await check_llm_policy("test")
        assert confidence == 0.0


# ════════════════════════════════════════════════════════════
#  check_llm_policy — allowed response
# ════════════════════════════════════════════════════════════

class TestCheckLlmPolicyAllowed:
    """Tests for allowed messages."""

    @pytest.fixture(autouse=True)
    def setup_client(self, mock_async_openai_client):
        """Set up LLM guard with a mock that returns allowed."""
        llm_guard._async_client = mock_async_openai_client

    @pytest.mark.asyncio
    async def test_allowed_returns_true(self):
        passed, confidence, reason = await check_llm_policy("ราคาสินค้า")
        assert passed is True

    @pytest.mark.asyncio
    async def test_allowed_confidence(self):
        passed, confidence, reason = await check_llm_policy("ราคาสินค้า")
        assert confidence == pytest.approx(0.95)

    @pytest.mark.asyncio
    async def test_allowed_reason(self):
        passed, confidence, reason = await check_llm_policy("ราคาสินค้า")
        assert reason == "product inquiry"

    @pytest.mark.asyncio
    async def test_returns_tuple_of_three(self):
        result = await check_llm_policy("test")
        assert isinstance(result, tuple)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_calls_chat_completions(self, mock_async_openai_client):
        await check_llm_policy("test message")
        mock_async_openai_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_system_prompt(self, mock_async_openai_client):
        await check_llm_policy("test message")
        call_kwargs = mock_async_openai_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        system_msg = next(m for m in messages if m["role"] == "system")
        assert system_msg["content"] == POLICY_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_passes_user_message(self, mock_async_openai_client):
        await check_llm_policy("ราคาผงเครื่องเทศ")
        call_kwargs = mock_async_openai_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        user_msg = next(m for m in messages if m["role"] == "user")
        assert user_msg["content"] == "ราคาผงเครื่องเทศ"

    @pytest.mark.asyncio
    async def test_uses_correct_model(self, mock_async_openai_client):
        await check_llm_policy("test")
        call_kwargs = mock_async_openai_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_temperature_zero(self, mock_async_openai_client):
        await check_llm_policy("test")
        call_kwargs = mock_async_openai_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0

    @pytest.mark.asyncio
    async def test_max_tokens_set(self, mock_async_openai_client):
        await check_llm_policy("test")
        call_kwargs = mock_async_openai_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 100


# ════════════════════════════════════════════════════════════
#  check_llm_policy — blocked response
# ════════════════════════════════════════════════════════════

class TestCheckLlmPolicyBlocked:
    """Tests for blocked messages."""

    @pytest.fixture(autouse=True)
    def setup_client(self, mock_async_openai_client_blocked):
        """Set up LLM guard with a mock that returns blocked."""
        llm_guard._async_client = mock_async_openai_client_blocked

    @pytest.mark.asyncio
    async def test_blocked_returns_false(self):
        passed, confidence, reason = await check_llm_policy("write me an essay")
        assert passed is False

    @pytest.mark.asyncio
    async def test_blocked_confidence(self):
        passed, confidence, reason = await check_llm_policy("write me an essay")
        assert confidence == pytest.approx(0.90)

    @pytest.mark.asyncio
    async def test_blocked_reason(self):
        passed, confidence, reason = await check_llm_policy("write me an essay")
        assert reason == "off-topic request"


# ════════════════════════════════════════════════════════════
#  check_llm_policy — JSON parse error (fail-open)
# ════════════════════════════════════════════════════════════

class TestCheckLlmPolicyParseError:
    """Tests for non-JSON LLM responses (fail-open)."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        """Set up LLM guard with a mock that returns non-JSON."""
        client = AsyncMock()

        async def _make_chat(*args, **kwargs):
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = "I cannot parse this as JSON"
            return resp

        client.chat.completions.create = AsyncMock(side_effect=_make_chat)
        llm_guard._async_client = client

    @pytest.mark.asyncio
    async def test_parse_error_passes(self):
        passed, confidence, reason = await check_llm_policy("test")
        assert passed is True

    @pytest.mark.asyncio
    async def test_parse_error_zero_confidence(self):
        passed, confidence, reason = await check_llm_policy("test")
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_parse_error_reason(self):
        passed, confidence, reason = await check_llm_policy("test")
        assert reason == "parse_error_fail_open"


# ════════════════════════════════════════════════════════════
#  check_llm_policy — API exception (fail-open)
# ════════════════════════════════════════════════════════════

class TestCheckLlmPolicyApiError:
    """Tests for API exceptions (fail-open)."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        """Set up LLM guard with a mock that raises an exception."""
        client = AsyncMock()
        client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("API connection failed")
        )
        llm_guard._async_client = client

    @pytest.mark.asyncio
    async def test_api_error_passes(self):
        passed, confidence, reason = await check_llm_policy("test")
        assert passed is True

    @pytest.mark.asyncio
    async def test_api_error_zero_confidence(self):
        passed, confidence, reason = await check_llm_policy("test")
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_api_error_reason_contains_error(self):
        passed, confidence, reason = await check_llm_policy("test")
        assert "error_fail_open" in reason
        assert "API connection failed" in reason


# ════════════════════════════════════════════════════════════
#  check_llm_policy — edge case responses
# ════════════════════════════════════════════════════════════

class TestCheckLlmPolicyEdgeCases:
    """Tests for edge cases in LLM response parsing."""

    @pytest.mark.asyncio
    async def test_missing_allowed_key_defaults_true(self):
        """If 'allowed' key is missing, default to True."""
        client = AsyncMock()

        async def _make_chat(*args, **kwargs):
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = json.dumps(
                {"confidence": 0.5, "reason": "unsure"}
            )
            return resp

        client.chat.completions.create = AsyncMock(side_effect=_make_chat)
        llm_guard._async_client = client

        passed, confidence, reason = await check_llm_policy("test")
        assert passed is True

    @pytest.mark.asyncio
    async def test_missing_confidence_defaults_zero(self):
        """If 'confidence' key is missing, default to 0.0."""
        client = AsyncMock()

        async def _make_chat(*args, **kwargs):
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = json.dumps(
                {"allowed": True, "reason": "ok"}
            )
            return resp

        client.chat.completions.create = AsyncMock(side_effect=_make_chat)
        llm_guard._async_client = client

        passed, confidence, reason = await check_llm_policy("test")
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_missing_reason_defaults_empty(self):
        """If 'reason' key is missing, default to empty string."""
        client = AsyncMock()

        async def _make_chat(*args, **kwargs):
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = json.dumps(
                {"allowed": True, "confidence": 0.8}
            )
            return resp

        client.chat.completions.create = AsyncMock(side_effect=_make_chat)
        llm_guard._async_client = client

        passed, confidence, reason = await check_llm_policy("test")
        assert reason == ""

    @pytest.mark.asyncio
    async def test_whitespace_in_response(self):
        """LLM response with extra whitespace should still parse."""
        client = AsyncMock()

        async def _make_chat(*args, **kwargs):
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = '  {"allowed": true, "confidence": 0.9, "reason": "ok"}  '
            return resp

        client.chat.completions.create = AsyncMock(side_effect=_make_chat)
        llm_guard._async_client = client

        passed, confidence, reason = await check_llm_policy("test")
        assert passed is True
        assert confidence == pytest.approx(0.9)
