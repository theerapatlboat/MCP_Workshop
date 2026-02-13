"""Tests for shared/constants.py — error message constants."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from shared.constants import (
    ERROR_NO_OUTPUT,
    ERROR_PROCESSING,
    ERROR_SYSTEM_UNAVAILABLE,
    ERROR_SYSTEM_UNAVAILABLE_SHORT,
)


def test_error_system_unavailable_is_nonempty_string():
    assert isinstance(ERROR_SYSTEM_UNAVAILABLE, str)
    assert len(ERROR_SYSTEM_UNAVAILABLE) > 0


def test_error_system_unavailable_short_is_nonempty_string():
    assert isinstance(ERROR_SYSTEM_UNAVAILABLE_SHORT, str)
    assert len(ERROR_SYSTEM_UNAVAILABLE_SHORT) > 0


def test_error_no_output_is_nonempty_string():
    assert isinstance(ERROR_NO_OUTPUT, str)
    assert len(ERROR_NO_OUTPUT) > 0


def test_error_processing_is_nonempty_string():
    assert isinstance(ERROR_PROCESSING, str)
    assert len(ERROR_PROCESSING) > 0


def test_all_errors_contain_thai_text():
    """All error messages should contain Thai characters."""
    for msg in [ERROR_SYSTEM_UNAVAILABLE, ERROR_SYSTEM_UNAVAILABLE_SHORT,
                ERROR_NO_OUTPUT, ERROR_PROCESSING]:
        assert any("\u0e00" <= c <= "\u0e7f" for c in msg), (
            f"Expected Thai characters in: {msg}"
        )
