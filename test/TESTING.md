# Testing Guide — AI-Workshop (GoSaaS Order Management Agent)

## Overview

This test suite provides comprehensive coverage for the AI-Workshop project — a production Facebook Messenger AI chatbot for Thai spice product sales. All external APIs are mocked so tests run completely offline without API keys.

## Prerequisites

```bash
# Install test dependencies
pip install -r test/requirements.txt
```

### Required packages:
- `pytest>=8.0` — Test framework
- `pytest-asyncio>=0.23` — Async test support
- `pytest-cov>=5.0` — Coverage reporting
- `pytest-mock>=3.12` — Mock fixtures
- `httpx>=0.27.0` — Async HTTP testing
- `respx>=0.21.0` — httpx mock server
- `textual[dev]>=0.80.0` — TUI app testing
- `numpy` — Needed by FAISS vector search

## Quick Start

```bash
# Run all tests
python -m pytest test/ -v

# Run with coverage report
python -m pytest test/ -v --cov=agent --cov=shared --cov-report=term-missing

# Run fast (skip slow tests)
python -m pytest test/ -v -m "not slow"
```

> **Note:** If `pytest` is not on your PATH, use `python -m pytest` instead.

## Test Structure

```
test/
├── conftest.py                     # Root shared fixtures
├── requirements.txt                # Test dependencies
├── TESTING.md                      # This file
│
├── shared/                         # Shared utilities
│   ├── test_constants.py           # Error message constants
│   ├── test_logging_setup.py       # Logger creation & rotation
│   └── test_http_client.py         # forward_to_agent HTTP helper
│
├── agent/                          # Agent API layer
│   ├── test_agent_api.py           # POST /chat endpoint, image parsing
│   ├── test_session_store.py       # SQLite session CRUD, TTL, truncation
│   ├── test_agent_config.py        # Environment config validation
│   ├── test_vector_search.py       # FAISS + SQLite hybrid search
│   ├── test_load_knowledge.py      # Knowledge base loading script
│   └── test_run_agents.py          # CLI runner, ConsoleTraceProcessor
│
├── tui/                            # Textual TUI
│   ├── test_tui_app.py             # TUI compose, events, sessions
│   └── test_trace_processor.py     # TuiTraceProcessor span handling
│
├── mcp_server/                     # MCP Server tools
│   ├── conftest.py                 # MCP-specific fixtures
│   ├── test_config.py              # api_get/post/delete helpers
│   ├── test_models.py              # AddressVerificationResult model
│   ├── test_server_registration.py # FastMCP tool registration
│   ├── test_order_draft.py         # 5 order draft tools
│   ├── test_product.py             # list_product, get_product
│   ├── test_shipment.py            # Shipping status & shipment
│   ├── test_report.py              # Sales summary & filter reports
│   ├── test_order.py               # get_order_meta
│   ├── test_utilities.py           # verify_address, faq, intent_classify
│   ├── test_hybrid_search.py       # knowledge_search + LLM refinement
│   └── test_memory.py              # Memory CRUD (add/search/get_all/delete)
│
├── webhook/                        # Facebook Webhook
│   ├── conftest.py                 # Webhook fixtures (signatures, events)
│   ├── test_main.py                # Routes, debounce, dedup, FB signature
│   └── test_upload_images.py       # Image upload utility
│
└── guardrail/                      # Guardrail Proxy
    ├── conftest.py                 # Guardrail fixtures
    ├── test_models.py              # GuardRequest/Response models
    ├── test_config.py              # Env-based config loading
    ├── test_vector_guard.py        # Vector similarity checks
    ├── test_llm_guard.py           # LLM policy checks
    └── test_main.py                # POST /guard, /health endpoints
```

## Running Tests by Module

```bash
# Shared utilities
pytest test/shared/ -v

# Agent API layer
pytest test/agent/ -v

# TUI (Textual terminal UI)
pytest test/tui/ -v

# MCP Server tools
pytest test/mcp_server/ -v

# Facebook webhook
pytest test/webhook/ -v

# Guardrail proxy
pytest test/guardrail/ -v
```

## Running Specific Test Files

```bash
# Single file
pytest test/agent/test_session_store.py -v

# Single test function
pytest test/agent/test_session_store.py::test_save_and_get_messages -v

# Tests matching a keyword
pytest test/ -v -k "memory"
```

## Coverage Report

```bash
# Full coverage with terminal report
pytest test/ -v \
  --cov=agent \
  --cov=shared \
  --cov-report=term-missing

# HTML coverage report
pytest test/ -v \
  --cov=agent \
  --cov=shared \
  --cov-report=html

# Coverage with branch analysis
pytest test/ -v \
  --cov=agent \
  --cov=shared \
  --cov-report=term-missing \
  --cov-branch
```

## Mocking Strategy

All external dependencies are mocked — no API keys or network access needed:

| Dependency | Mock Approach |
|---|---|
| **OpenAI API** (embeddings, chat) | `unittest.mock.MagicMock` / `AsyncMock` on client objects |
| **GoSaaS UAT API** | Patch `config.api_get/post/delete` at module level |
| **Facebook Graph API** | `respx` or mock `httpx.AsyncClient.post` |
| **mem0 + Qdrant** | Patch `config.mem0_memory` (`.add`, `.search`, `.get_all`, `.delete`) |
| **MCP Server** | `AsyncMock(spec=MCPServerStreamableHttp)` |
| **OpenAI Agents Runner** | Patch `Runner.run` / `Runner.run_streamed` |
| **SQLite** | Real SQLite via `tmp_path` fixtures (fast, in-memory) |
| **FAISS** | Real FAISS-CPU on small test data (fast) |

## Key Fixtures (from `test/conftest.py`)

| Fixture | Description |
|---|---|
| `tmp_sqlite_db` | Temp SQLite database path |
| `mock_openai_client` | Mocked sync OpenAI client |
| `mock_async_openai_client` | Mocked async OpenAI client |
| `mock_embedding_response` | Fake embedding (1536-dim zeros) |
| `mock_chat_response` | Fake ChatCompletion response |
| `sample_product_data` | Thai spice product JSON data |
| `sample_order_draft_body` | Order draft request body |
| `mock_env_vars` | All required environment variables |

## pytest Configuration

The project uses `pytest.ini` at the project root:

```ini
[pytest]
asyncio_mode = auto
testpaths = test
python_files = test_*.py
python_functions = test_*
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
```

## Troubleshooting

### Import Errors
The `test/conftest.py` adds all project subdirectories to `sys.path`. If you get import errors, ensure you're running pytest from the project root:

```bash
cd AI-Workshop
pytest test/ -v
```

### Textual TUI Tests
TUI tests use `app.run_test()` from textual. If they hang, ensure `textual[dev]` is installed:

```bash
pip install "textual[dev]>=0.80.0"
```

### Async Test Warnings
If you see `RuntimeWarning: coroutine was never awaited`, ensure `pytest-asyncio` is installed and `asyncio_mode = auto` is set in `pytest.ini`.

### Windows-specific
On Windows, if FAISS tests fail, install `faiss-cpu`:

```bash
pip install faiss-cpu
```
