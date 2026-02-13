"""Tests for guardrail/config.py — environment-based configuration loading."""

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure guardrail dir has highest priority on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GUARDRAIL_DIR = str(PROJECT_ROOT / "guardrail")
if GUARDRAIL_DIR in sys.path:
    sys.path.remove(GUARDRAIL_DIR)
sys.path.insert(0, GUARDRAIL_DIR)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(1, str(PROJECT_ROOT))


# ════════════════════════════════════════════════════════════
#  Helper to reimport config with fresh env
# ════════════════════════════════════════════════════════════

def _reload_config():
    """Force-reload guardrail config module to pick up env changes.

    Evicts any cached ``config`` module that doesn't belong to guardrail/
    (e.g. mcp-server's config.py), then reloads with dotenv patched out.

    The dotenv patch covers BOTH the initial import and the reload because
    ``load_dotenv()`` runs at module level and would restore env vars from
    the ``.env`` file, undoing any ``monkeypatch.delenv`` calls.
    """
    # Evict wrong config if present (e.g. mcp-server's config)
    cached = sys.modules.get("config")
    if cached is not None:
        mod_file = getattr(cached, "__file__", "") or ""
        if "guardrail" not in mod_file.replace("\\", "/"):
            del sys.modules["config"]

    with patch("dotenv.load_dotenv", return_value=None):
        import config

        # Ensure we have the guardrail config
        mod_file = getattr(config, "__file__", "") or ""
        if "guardrail" not in mod_file.replace("\\", "/"):
            del sys.modules["config"]
            import config

        importlib.reload(config)
    return config


# ════════════════════════════════════════════════════════════
#  OPENAI_API_KEY
# ════════════════════════════════════════════════════════════

class TestOpenAIApiKey:
    """Tests for OPENAI_API_KEY config."""

    def test_default_value_is_empty(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        cfg = _reload_config()
        assert cfg.OPENAI_API_KEY == ""

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-789")
        cfg = _reload_config()
        assert cfg.OPENAI_API_KEY == "sk-test-key-789"

    def test_empty_string_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        cfg = _reload_config()
        assert cfg.OPENAI_API_KEY == ""


# ════════════════════════════════════════════════════════════
#  AGENT_API_URL
# ════════════════════════════════════════════════════════════

class TestAgentApiUrl:
    """Tests for AGENT_API_URL config."""

    def test_default_value(self, monkeypatch):
        monkeypatch.delenv("AGENT_API_URL", raising=False)
        cfg = _reload_config()
        assert cfg.AGENT_API_URL == "http://localhost:3000/chat"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("AGENT_API_URL", "http://custom:5000/api")
        cfg = _reload_config()
        assert cfg.AGENT_API_URL == "http://custom:5000/api"

    def test_custom_port_and_path(self, monkeypatch):
        monkeypatch.setenv("AGENT_API_URL", "http://10.0.0.1:9999/v2/chat")
        cfg = _reload_config()
        assert cfg.AGENT_API_URL == "http://10.0.0.1:9999/v2/chat"


# ════════════════════════════════════════════════════════════
#  GUARDRAIL_PORT
# ════════════════════════════════════════════════════════════

class TestGuardrailPort:
    """Tests for GUARDRAIL_PORT config."""

    def test_default_value(self, monkeypatch):
        monkeypatch.delenv("GUARDRAIL_PORT", raising=False)
        cfg = _reload_config()
        assert cfg.GUARDRAIL_PORT == 8002

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("GUARDRAIL_PORT", "9090")
        cfg = _reload_config()
        assert cfg.GUARDRAIL_PORT == 9090

    def test_is_integer(self, monkeypatch):
        monkeypatch.setenv("GUARDRAIL_PORT", "7777")
        cfg = _reload_config()
        assert isinstance(cfg.GUARDRAIL_PORT, int)

    def test_invalid_port_raises(self, monkeypatch):
        monkeypatch.setenv("GUARDRAIL_PORT", "not-a-number")
        with pytest.raises(ValueError):
            _reload_config()


# ════════════════════════════════════════════════════════════
#  VECTOR_SIMILARITY_THRESHOLD
# ════════════════════════════════════════════════════════════

class TestVectorSimilarityThreshold:
    """Tests for VECTOR_SIMILARITY_THRESHOLD config."""

    def test_default_value(self, monkeypatch):
        monkeypatch.delenv("VECTOR_SIMILARITY_THRESHOLD", raising=False)
        cfg = _reload_config()
        assert cfg.VECTOR_SIMILARITY_THRESHOLD == 0.45

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("VECTOR_SIMILARITY_THRESHOLD", "0.60")
        cfg = _reload_config()
        assert cfg.VECTOR_SIMILARITY_THRESHOLD == pytest.approx(0.60)

    def test_is_float(self, monkeypatch):
        monkeypatch.setenv("VECTOR_SIMILARITY_THRESHOLD", "0.50")
        cfg = _reload_config()
        assert isinstance(cfg.VECTOR_SIMILARITY_THRESHOLD, float)

    def test_zero_threshold(self, monkeypatch):
        monkeypatch.setenv("VECTOR_SIMILARITY_THRESHOLD", "0.0")
        cfg = _reload_config()
        assert cfg.VECTOR_SIMILARITY_THRESHOLD == 0.0

    def test_one_threshold(self, monkeypatch):
        monkeypatch.setenv("VECTOR_SIMILARITY_THRESHOLD", "1.0")
        cfg = _reload_config()
        assert cfg.VECTOR_SIMILARITY_THRESHOLD == 1.0

    def test_invalid_threshold_raises(self, monkeypatch):
        monkeypatch.setenv("VECTOR_SIMILARITY_THRESHOLD", "abc")
        with pytest.raises(ValueError):
            _reload_config()


# ════════════════════════════════════════════════════════════
#  POLICY_MODEL
# ════════════════════════════════════════════════════════════

class TestPolicyModel:
    """Tests for POLICY_MODEL config (hardcoded constant)."""

    def test_default_value(self):
        cfg = _reload_config()
        assert cfg.POLICY_MODEL == "gpt-4o-mini"

    def test_is_string(self):
        cfg = _reload_config()
        assert isinstance(cfg.POLICY_MODEL, str)

    def test_not_empty(self):
        cfg = _reload_config()
        assert len(cfg.POLICY_MODEL) > 0
