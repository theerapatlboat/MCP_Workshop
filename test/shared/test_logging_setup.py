"""Tests for shared/logging_setup.py — logger creation with rotation."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from shared.logging_setup import setup_logger


def test_setup_logger_returns_logger(tmp_path):
    logger = setup_logger("test1", tmp_path, "test.log")
    assert isinstance(logger, logging.Logger)


def test_setup_logger_name(tmp_path):
    logger = setup_logger("myname", tmp_path, "test.log")
    assert logger.name == "myname"


def test_setup_logger_creates_directory(tmp_path):
    log_dir = tmp_path / "logs"
    assert not log_dir.exists()
    setup_logger("test2", log_dir, "test.log")
    assert log_dir.exists()


def test_setup_logger_creates_log_file(tmp_path):
    setup_logger("test3", tmp_path, "app.log")
    assert (tmp_path / "app.log").exists()


def test_setup_logger_has_console_handler(tmp_path):
    logger = setup_logger("test4", tmp_path, "test.log")
    stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)
                       and not isinstance(h, RotatingFileHandler)]
    assert len(stream_handlers) >= 1


def test_setup_logger_has_file_handler(tmp_path):
    logger = setup_logger("test5", tmp_path, "test.log")
    file_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
    assert len(file_handlers) == 1


def test_setup_logger_default_level(tmp_path):
    logger = setup_logger("test6", tmp_path, "test.log")
    assert logger.level == logging.INFO


def test_setup_logger_custom_level(tmp_path):
    logger = setup_logger("test7", tmp_path, "test.log", level=logging.DEBUG)
    assert logger.level == logging.DEBUG


def test_setup_logger_formatter_pattern(tmp_path):
    logger = setup_logger("test8", tmp_path, "test.log")
    for handler in logger.handlers:
        fmt = handler.formatter._fmt
        assert "%(asctime)s" in fmt
        assert "%(levelname)" in fmt
        assert "%(message)s" in fmt


def test_setup_logger_no_duplicate_handlers(tmp_path):
    logger1 = setup_logger("test_dup", tmp_path, "test.log")
    count1 = len(logger1.handlers)
    logger2 = setup_logger("test_dup", tmp_path, "test.log")
    count2 = len(logger2.handlers)
    assert count1 == count2, "Second call should not add duplicate handlers"
    assert logger1 is logger2


def test_setup_logger_rotating_max_bytes(tmp_path):
    logger = setup_logger("test9", tmp_path, "test.log", max_bytes=1_000_000)
    file_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
    assert file_handlers[0].maxBytes == 1_000_000


def test_setup_logger_rotating_backup_count(tmp_path):
    logger = setup_logger("test10", tmp_path, "test.log", backup_count=5)
    file_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
    assert file_handlers[0].backupCount == 5


def test_setup_logger_default_rotation_params(tmp_path):
    logger = setup_logger("test11", tmp_path, "test.log")
    file_handlers = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
    assert file_handlers[0].maxBytes == 5_000_000
    assert file_handlers[0].backupCount == 3
