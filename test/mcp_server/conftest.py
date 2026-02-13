"""Shared fixtures for mcp_server tests.

Provides mock FastMCP, API helpers, OpenAI client, and mem0 memory so that
tool modules can be imported and their inner functions captured without
touching any real external service.

Strategy:
  1. Temporarily put ``mcp-server/`` first in sys.path.
  2. Mock OpenAI and mem0 so ``config.py`` can be imported without side effects.
  3. Import all tool modules (they bind ``from config import api_get`` etc.).
  4. Restore sys.path to its original order (guardrail before mcp-server).
  5. Keep the mcp-server modules in sys.modules under their real names so
     fixture-based tests work.  The ``config`` and ``models`` entries are
     removed so that guardrail tests (which also have those names) can
     re-import from the correct directory.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Make mcp-server modules importable WITH highest priority — temporarily
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MCP_SERVER_DIR = str(PROJECT_ROOT / "mcp-server")

# Save original path so we can restore it
_original_sys_path = list(sys.path)

# Put mcp-server first so its config.py / models.py win during import
if MCP_SERVER_DIR in sys.path:
    sys.path.remove(MCP_SERVER_DIR)
sys.path.insert(0, MCP_SERVER_DIR)

_proj_root_str = str(PROJECT_ROOT)
if _proj_root_str not in sys.path:
    sys.path.insert(1, _proj_root_str)

# Evict any ``config`` / ``models`` from a different directory
for _mod_name in ["config", "models"]:
    cached = sys.modules.get(_mod_name)
    if cached is not None:
        mod_file = getattr(cached, "__file__", "") or ""
        if "mcp-server" not in mod_file.replace("\\", "/"):
            del sys.modules[_mod_name]

# ---------------------------------------------------------------------------
# Mock heavy dependencies BEFORE importing config.py
# ---------------------------------------------------------------------------
_mock_openai_cls = MagicMock()
_mock_openai_cls.return_value = MagicMock()

_mock_mem0_cls = MagicMock()
_mock_mem0_cls.from_config.return_value = MagicMock()

_orig_openai_mod = sys.modules.get("openai")
_orig_mem0_mod = sys.modules.get("mem0")

_fake_openai = MagicMock()
_fake_openai.OpenAI = _mock_openai_cls
sys.modules["openai"] = _fake_openai

_fake_mem0 = MagicMock()
_fake_mem0.Memory = _mock_mem0_cls
sys.modules["mem0"] = _fake_mem0

# Also mock dotenv so load_dotenv() doesn't leak real .env values
# into os.environ (which would break guardrail config tests).
_orig_dotenv_mod = sys.modules.get("dotenv")
_fake_dotenv = MagicMock()
_fake_dotenv.load_dotenv = MagicMock(return_value=None)
sys.modules["dotenv"] = _fake_dotenv

if "config" in sys.modules:
    del sys.modules["config"]

import config as _mcp_config  # noqa: E402

# Restore dotenv
if _orig_dotenv_mod is not None:
    sys.modules["dotenv"] = _orig_dotenv_mod
elif "dotenv" in sys.modules and sys.modules["dotenv"] is _fake_dotenv:
    del sys.modules["dotenv"]

# Restore openai / mem0
if _orig_openai_mod is not None:
    sys.modules["openai"] = _orig_openai_mod
elif "openai" in sys.modules and sys.modules["openai"] is _fake_openai:
    del sys.modules["openai"]

if _orig_mem0_mod is not None:
    sys.modules["mem0"] = _orig_mem0_mod
elif "mem0" in sys.modules and sys.modules["mem0"] is _fake_mem0:
    del sys.modules["mem0"]

# ---------------------------------------------------------------------------
# Import tool modules (they capture ``api_get`` etc. from config at import time)
# ---------------------------------------------------------------------------
from tools import order_draft as _mod_order_draft  # noqa: E402
from tools import product as _mod_product  # noqa: E402
from tools import shipment as _mod_shipment  # noqa: E402
from tools import report as _mod_report  # noqa: E402
from tools import order as _mod_order  # noqa: E402
from tools import utilities as _mod_utilities  # noqa: E402
from tools import memory as _mod_memory  # noqa: E402

# Also import hybrid_search for direct helper tests
from tools import hybrid_search as _mod_hybrid_search  # noqa: E402

# ---------------------------------------------------------------------------
# Restore sys.path to original order.
# The root conftest.py had guardrail before mcp-server, which is what
# guardrail tests need.  We keep mcp-server in sys.path (root conftest
# put it there) but not at position 0 anymore.
# ---------------------------------------------------------------------------
sys.path[:] = _original_sys_path

# Remove bare ``config`` and ``models`` from sys.modules so guardrail can
# import its own versions later.  Our tool modules already hold references.
for _mod_name in ["config", "models"]:
    cached = sys.modules.get(_mod_name)
    if cached is not None:
        mf = getattr(cached, "__file__", "") or ""
        if "mcp-server" in mf.replace("\\", "/"):
            del sys.modules[_mod_name]


# ── Helpers ───────────────────────────────────────────────────────────────


class _ToolCollector:
    """Minimal stand-in for FastMCP that captures tool functions."""

    def __init__(self):
        self.tools: dict[str, callable] = {}

    def tool(self, **kwargs):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


@pytest.fixture(autouse=True)
def _ensure_mcp_modules():
    """Per-test fixture ensuring mcp-server modules are accessible.

    Other test directories (guardrail) may evict 'config' from sys.modules.
    This fixture ensures the bare 'config' name is NOT pointing to a wrong
    module before any mcp_server test runs.  Our tool modules already hold
    direct references to the mcp-server config's functions, so we do NOT
    need to re-import config — we just need to prevent import errors if a
    test happens to do ``import config`` directly.
    """
    # Evict config/models if they were replaced by guardrail
    for mod_name in ["config", "models"]:
        cached = sys.modules.get(mod_name)
        if cached is not None:
            mod_file = getattr(cached, "__file__", "") or ""
            if "mcp-server" not in mod_file.replace("\\", "/"):
                del sys.modules[mod_name]
    yield


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def tool_collector():
    """Return a fresh _ToolCollector instance."""
    return _ToolCollector()


@pytest.fixture
def mock_api_get():
    """Patch ``api_get`` in all tool modules that use it."""
    m = MagicMock()
    targets = [_mod_order_draft, _mod_product, _mod_shipment,
               _mod_report, _mod_order]
    patches = [patch.object(mod, "api_get", m) for mod in targets]
    for p in patches:
        p.start()
    yield m
    for p in patches:
        p.stop()


@pytest.fixture
def mock_api_post():
    """Patch ``api_post`` in tool modules that use it."""
    m = MagicMock()
    patches = [patch.object(_mod_order_draft, "api_post", m)]
    for p in patches:
        p.start()
    yield m
    for p in patches:
        p.stop()


@pytest.fixture
def mock_api_delete():
    """Patch ``api_delete`` in tool modules that use it."""
    m = MagicMock()
    patches = [patch.object(_mod_order_draft, "api_delete", m)]
    for p in patches:
        p.start()
    yield m
    for p in patches:
        p.stop()


@pytest.fixture
def mock_openai():
    """Patch ``openai_client`` in tool modules that use it."""
    client = MagicMock()
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = '{"answer": "ok"}'
    client.chat.completions.create.return_value = resp

    patches = [patch.object(_mod_utilities, "openai_client", client)]
    for p in patches:
        p.start()
    yield client
    for p in patches:
        p.stop()


@pytest.fixture
def mock_mem0():
    """Patch ``mem0_memory`` in the memory tool module."""
    m = MagicMock()
    p = patch.object(_mod_memory, "mem0_memory", m)
    p.start()
    yield m
    p.stop()


# ── Expose imported modules so test files can use them ────────────────────

@pytest.fixture
def mcp_config():
    """Return the mcp-server config module (already imported with mocks)."""
    return _mcp_config


# ── Pre-registered tool sets ─────────────────────────────────────────────


@pytest.fixture
def order_draft_tools(tool_collector, mock_api_get, mock_api_post, mock_api_delete):
    _mod_order_draft.register(tool_collector)
    return tool_collector.tools


@pytest.fixture
def product_tools(tool_collector, mock_api_get):
    _mod_product.register(tool_collector)
    return tool_collector.tools


@pytest.fixture
def shipment_tools(tool_collector, mock_api_get):
    _mod_shipment.register(tool_collector)
    return tool_collector.tools


@pytest.fixture
def report_tools(tool_collector, mock_api_get):
    _mod_report.register(tool_collector)
    return tool_collector.tools


@pytest.fixture
def order_tools(tool_collector, mock_api_get):
    _mod_order.register(tool_collector)
    return tool_collector.tools


@pytest.fixture
def utility_tools(tool_collector, mock_openai):
    _mod_utilities.register(tool_collector)
    return tool_collector.tools


@pytest.fixture
def memory_tools(tool_collector, mock_mem0):
    _mod_memory.register(tool_collector)
    return tool_collector.tools
