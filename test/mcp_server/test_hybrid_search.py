"""Tests for mcp-server/tools/hybrid_search.py — knowledge_search tool.

NOTE: The hybrid_search module is pre-imported by conftest.py as
``_mod_hybrid_search``.  Tests that need to reference helper functions
(``_format_candidate``, ``_clean_candidates``) use conftest's reference
to avoid bare ``from tools.hybrid_search import ...`` which would trigger
a re-import of the mcp-server config module.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# We access the hybrid_search module through conftest's pre-imported reference.
# Import it here so helper-function tests can use it directly.
# ---------------------------------------------------------------------------
# conftest stores it as _mod_hybrid_search; we grab it the same way.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MCP_SERVER_DIR = str(PROJECT_ROOT / "mcp-server")


# ---------------------------------------------------------------------------
# Fixtures specific to hybrid_search
# ---------------------------------------------------------------------------

@pytest.fixture
def _patch_vector_search():
    """Patch the external dependencies used by hybrid_search tool.

    We import the module object that was already loaded by conftest and
    patch attributes on it.
    """
    # Get the already-imported module from sys.modules
    hs_mod = sys.modules.get("tools.hybrid_search")
    if hs_mod is None:
        pytest.skip("tools.hybrid_search not pre-imported by conftest")

    with patch.object(hs_mod, "get_connection") as mock_conn, \
         patch.object(hs_mod, "_hybrid_search") as mock_hs, \
         patch.object(hs_mod, "openai_client") as mock_oai:
        conn_obj = MagicMock()
        mock_conn.return_value = conn_obj

        mock_hs.return_value = []

        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = "[]"
        mock_oai.chat.completions.create.return_value = resp

        yield {
            "get_connection": mock_conn,
            "hybrid_search": mock_hs,
            "openai_client": mock_oai,
            "conn": conn_obj,
        }


@pytest.fixture
def hs_tools(_patch_vector_search, tool_collector):
    """Register hybrid_search tools and return {name: fn} + mocks."""
    hs_mod = sys.modules["tools.hybrid_search"]
    hs_mod.register(tool_collector)
    return tool_collector.tools, _patch_vector_search


# ---------------------------------------------------------------------------
# Helper: get the module for direct function tests
# ---------------------------------------------------------------------------

def _get_hs_module():
    """Return the pre-imported hybrid_search module."""
    mod = sys.modules.get("tools.hybrid_search")
    if mod is None:
        pytest.skip("tools.hybrid_search not loaded")
    return mod


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestHybridSearchRegistration:

    def test_knowledge_search_is_registered(self, hs_tools):
        tools, _ = hs_tools
        assert "knowledge_search" in tools
        assert len(tools) == 1


# ---------------------------------------------------------------------------
# knowledge_search — connection errors
# ---------------------------------------------------------------------------

class TestKnowledgeSearchConnectionErrors:

    def test_db_not_found_returns_error(self, tool_collector):
        hs_mod = _get_hs_module()
        with patch.object(hs_mod, "get_connection") as mock_conn, \
             patch.object(hs_mod, "_hybrid_search"), \
             patch.object(hs_mod, "openai_client"):
            mock_conn.side_effect = FileNotFoundError("DB not found")

            hs_mod.register(tool_collector)
            fn = tool_collector.tools["knowledge_search"]
            result = fn(query="test")

        assert result["success"] is False
        assert "not found" in result["error"].lower() or "DB not found" in result["error"]


# ---------------------------------------------------------------------------
# knowledge_search — empty results
# ---------------------------------------------------------------------------

class TestKnowledgeSearchEmpty:

    def test_empty_results(self, hs_tools):
        tools, mocks = hs_tools
        mocks["hybrid_search"].return_value = []

        result = tools["knowledge_search"](query="nonexistent thing")

        assert result["success"] is True
        assert result["total_candidates"] == 0
        assert result["refined_count"] == 0
        assert result["results"] == []
        assert result["query"] == "nonexistent thing"

    def test_empty_results_with_category_filter(self, hs_tools):
        tools, mocks = hs_tools
        mocks["hybrid_search"].return_value = []

        result = tools["knowledge_search"](query="test", category="recipe")

        assert result["success"] is True
        assert result["filters"] == {"category": "recipe"}

    def test_no_category_filter_returns_none_filters(self, hs_tools):
        tools, mocks = hs_tools
        mocks["hybrid_search"].return_value = []

        result = tools["knowledge_search"](query="test")

        assert result["filters"] is None


# ---------------------------------------------------------------------------
# knowledge_search — with results
# ---------------------------------------------------------------------------

class TestKnowledgeSearchWithResults:

    def _make_candidates(self, n=3):
        return [
            {
                "id": i,
                "doc_id": f"doc_{i:03d}",
                "category": "product_overview",
                "title": f"Product {i}",
                "text": f"This is product {i} description content.",
                "image_ids": [f"IMG_PROD_{i:03d}"],
                "score": 0.9 - (i * 0.1),
                "source": "vector",
            }
            for i in range(1, n + 1)
        ]

    def test_returns_refined_results(self, hs_tools):
        tools, mocks = hs_tools
        candidates = self._make_candidates(3)
        mocks["hybrid_search"].return_value = candidates

        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = "[1, 3]"
        mocks["openai_client"].chat.completions.create.return_value = resp

        result = tools["knowledge_search"](query="product info")

        assert result["success"] is True
        assert result["total_candidates"] == 3
        assert result["refined_count"] == 2
        result_ids = {r["id"] for r in result["results"]}
        assert result_ids == {1, 3}

    def test_fallback_returns_all_when_llm_fails(self, hs_tools):
        tools, mocks = hs_tools
        candidates = self._make_candidates(2)
        mocks["hybrid_search"].return_value = candidates

        mocks["openai_client"].chat.completions.create.side_effect = RuntimeError("API down")

        result = tools["knowledge_search"](query="test")

        assert result["success"] is True
        assert result["total_candidates"] == 2
        assert result["refined_count"] == 2

    def test_category_filter_passed_to_hybrid_search(self, hs_tools):
        tools, mocks = hs_tools
        mocks["hybrid_search"].return_value = []

        tools["knowledge_search"](query="recipe", category="recipe")

        mocks["hybrid_search"].assert_called_once()
        call_kwargs = mocks["hybrid_search"].call_args[1]
        assert call_kwargs.get("filters") == {"category": "recipe"} or \
               mocks["hybrid_search"].call_args.kwargs.get("filters") == {"category": "recipe"}

    def test_no_category_calls_two_phase_search(self, hs_tools):
        tools, mocks = hs_tools
        mocks["hybrid_search"].return_value = []

        tools["knowledge_search"](query="general query")

        assert mocks["hybrid_search"].call_count == 2

    def test_result_structure_has_expected_keys(self, hs_tools):
        tools, mocks = hs_tools
        candidates = self._make_candidates(1)
        mocks["hybrid_search"].return_value = candidates

        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = "[1]"
        mocks["openai_client"].chat.completions.create.return_value = resp

        result = tools["knowledge_search"](query="test")

        for key in ["success", "query", "filters", "total_candidates",
                     "refined_count", "results"]:
            assert key in result

    def test_custom_top_k(self, hs_tools):
        tools, mocks = hs_tools
        mocks["hybrid_search"].return_value = []

        tools["knowledge_search"](query="test", top_k=10, category="pricing")

        call_kwargs = mocks["hybrid_search"].call_args[1]
        assert call_kwargs.get("top_k") == 10

    def test_default_top_k_is_5(self, hs_tools):
        tools, mocks = hs_tools
        mocks["hybrid_search"].return_value = []

        tools["knowledge_search"](query="test", category="pricing")

        call_kwargs = mocks["hybrid_search"].call_args[1]
        assert call_kwargs.get("top_k") == 5


# ---------------------------------------------------------------------------
# knowledge_search — exceptions
# ---------------------------------------------------------------------------

class TestKnowledgeSearchException:

    def test_search_failure_returns_error(self, hs_tools):
        tools, mocks = hs_tools
        mocks["hybrid_search"].side_effect = Exception("FAISS error")

        result = tools["knowledge_search"](query="test")

        assert result["success"] is False
        assert "Search failed" in result["error"]

    def test_connection_closed_after_search(self, hs_tools):
        tools, mocks = hs_tools
        mocks["hybrid_search"].return_value = []

        tools["knowledge_search"](query="test")

        mocks["conn"].close.assert_called_once()

    def test_connection_closed_even_on_error(self, hs_tools):
        tools, mocks = hs_tools
        mocks["hybrid_search"].side_effect = Exception("error")

        tools["knowledge_search"](query="test")

        mocks["conn"].close.assert_called_once()


# ---------------------------------------------------------------------------
# Module-level helpers — _format_candidate, _clean_candidates
# ---------------------------------------------------------------------------

class TestFormatCandidate:

    def test_format_candidate_basic(self):
        mod = _get_hs_module()
        doc = {
            "id": 1, "doc_id": "doc_001", "category": "recipe",
            "title": "Soup Recipe",
            "text": "This is a recipe for soup",
            "image_ids": ["IMG_REC_001"], "source": "vector",
        }
        result = mod._format_candidate(doc)
        assert "ID: 1" in result
        assert "doc_001" in result
        assert "recipe" in result
        assert "Soup Recipe" in result
        assert "IMG_REC_001" in result

    def test_format_candidate_no_images(self):
        mod = _get_hs_module()
        doc = {
            "id": 2, "doc_id": "doc_002", "category": "pricing",
            "title": "Price List", "text": "Prices here",
            "image_ids": [], "source": "substring",
        }
        result = mod._format_candidate(doc)
        assert "images: none" in result


class TestCleanCandidates:

    def test_clean_basic(self):
        mod = _get_hs_module()
        candidates = [{
            "id": 1, "doc_id": "doc_001", "category": "recipe",
            "title": "Soup", "text": "Recipe content",
            "image_ids": ["IMG_001"], "score": 0.9, "source": "vector",
        }]

        cleaned = mod._clean_candidates(candidates)

        assert len(cleaned) == 1
        c = cleaned[0]
        assert c["id"] == 1
        assert c["content"] == "Recipe content"
        assert c["image_ids"] == ["IMG_001"]

    def test_clean_string_image_ids(self):
        mod = _get_hs_module()
        candidates = [{
            "id": 2, "doc_id": "d2", "category": "product",
            "title": "P", "text": "content",
            "image_ids": '["IMG_001", "IMG_002"]',
            "score": None, "source": "substring",
        }]

        cleaned = mod._clean_candidates(candidates)
        assert cleaned[0]["image_ids"] == ["IMG_001", "IMG_002"]

    def test_clean_invalid_string_image_ids(self):
        mod = _get_hs_module()
        candidates = [{
            "id": 3, "doc_id": "d3", "category": "product",
            "title": "P", "text": "content",
            "image_ids": "not-json",
            "score": None, "source": "substring",
        }]

        cleaned = mod._clean_candidates(candidates)
        assert cleaned[0]["image_ids"] == []

    def test_clean_empty_image_ids(self):
        mod = _get_hs_module()
        candidates = [{
            "id": 4, "doc_id": "d4", "category": "product",
            "title": "P", "text": "content",
            "image_ids": [], "score": 0.5, "source": "vector",
        }]

        cleaned = mod._clean_candidates(candidates)
        assert cleaned[0]["image_ids"] == []
        assert cleaned[0]["image_details"] == {}

    def test_clean_multiple_candidates(self):
        mod = _get_hs_module()
        candidates = [
            {"id": i, "doc_id": f"d{i}", "category": "c", "title": "t",
             "text": f"text {i}", "image_ids": [], "score": None, "source": "s"}
            for i in range(5)
        ]

        cleaned = mod._clean_candidates(candidates)
        assert len(cleaned) == 5
        for i, c in enumerate(cleaned):
            assert c["id"] == i
            assert c["content"] == f"text {i}"
