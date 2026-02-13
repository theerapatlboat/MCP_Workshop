"""Tests for mcp-server/server.py — FastMCP tool registration."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add paths
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "mcp-server"))


# ════════════════════════════════════════════════════════════
#  Tool module registration
# ════════════════════════════════════════════════════════════

def test_order_draft_has_register():
    from tools import order_draft
    assert hasattr(order_draft, "register")
    assert callable(order_draft.register)


def test_product_has_register():
    from tools import product
    assert hasattr(product, "register")
    assert callable(product.register)


def test_shipment_has_register():
    from tools import shipment
    assert hasattr(shipment, "register")
    assert callable(shipment.register)


def test_report_has_register():
    from tools import report
    assert hasattr(report, "register")
    assert callable(report.register)


def test_order_has_register():
    from tools import order
    assert hasattr(order, "register")
    assert callable(order.register)


def test_utilities_has_register():
    from tools import utilities
    assert hasattr(utilities, "register")
    assert callable(utilities.register)


def test_hybrid_search_has_register():
    from tools import hybrid_search
    assert hasattr(hybrid_search, "register")
    assert callable(hybrid_search.register)


def test_memory_has_register():
    from tools import memory
    assert hasattr(memory, "register")
    assert callable(memory.register)


def test_all_eight_modules_importable():
    """All 8 tool modules should be importable."""
    from tools import (
        order_draft,
        product,
        shipment,
        report,
        order,
        utilities,
        hybrid_search,
        memory,
    )
    modules = [order_draft, product, shipment, report, order, utilities, hybrid_search, memory]
    assert len(modules) == 8


def test_register_functions_accept_mcp():
    """Each register function should accept a FastMCP instance without error."""
    mock_mcp = MagicMock()
    mock_mcp.tool = MagicMock(return_value=lambda fn: fn)

    from tools import (
        order_draft,
        product,
        shipment,
        report,
        order,
        utilities,
        hybrid_search,
        memory,
    )

    for module in [order_draft, product, shipment, report, order, utilities, hybrid_search, memory]:
        module.register(mock_mcp)
