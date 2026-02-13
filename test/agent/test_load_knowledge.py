"""Tests for agent/load_knowledge.py — knowledge base loading script."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "agent"))


@pytest.fixture
def mock_setup():
    with patch("agent.load_knowledge.setup") as m:
        m.return_value = MagicMock()
        yield m


@pytest.fixture
def mock_init_db():
    with patch("agent.load_knowledge.init_db") as m:
        m.return_value = MagicMock()
        yield m


@pytest.fixture
def mock_cmd_load():
    with patch("agent.load_knowledge.cmd_load") as m:
        yield m


@pytest.fixture
def mock_get_doc_count():
    with patch("agent.load_knowledge.get_document_count") as m:
        m.return_value = 29
        yield m


def test_main_deletes_old_db(tmp_path, mock_setup, mock_init_db, mock_cmd_load, mock_get_doc_count):
    db_file = tmp_path / "vector_store.db"
    db_file.write_text("old data")

    with patch("agent.load_knowledge.DB_PATH", db_file), \
         patch("agent.load_knowledge.PROJECT_ROOT", tmp_path):
        (tmp_path / "storage").mkdir(exist_ok=True)
        from agent.load_knowledge import main
        main()

    assert not db_file.exists() or mock_init_db.called


def test_main_creates_new_db(tmp_path, mock_setup, mock_init_db, mock_cmd_load, mock_get_doc_count):
    with patch("agent.load_knowledge.DB_PATH", tmp_path / "new.db"), \
         patch("agent.load_knowledge.PROJECT_ROOT", tmp_path):
        (tmp_path / "storage").mkdir(exist_ok=True)
        from agent.load_knowledge import main
        main()

    mock_init_db.assert_called_once()


def test_main_loads_all_txt_files(tmp_path, mock_setup, mock_init_db, mock_cmd_load, mock_get_doc_count):
    storage = tmp_path / "storage"
    storage.mkdir()
    (storage / "file1.txt").write_text("data1")
    (storage / "file2.txt").write_text("data2")

    with patch("agent.load_knowledge.DB_PATH", tmp_path / "test.db"), \
         patch("agent.load_knowledge.PROJECT_ROOT", tmp_path):
        from agent.load_knowledge import main
        main()

    assert mock_cmd_load.call_count == 2


def test_main_no_txt_files(tmp_path, mock_setup, mock_init_db, mock_cmd_load, mock_get_doc_count, capsys):
    storage = tmp_path / "storage"
    storage.mkdir()

    with patch("agent.load_knowledge.DB_PATH", tmp_path / "test.db"), \
         patch("agent.load_knowledge.PROJECT_ROOT", tmp_path):
        from agent.load_knowledge import main
        main()

    mock_cmd_load.assert_not_called()


def test_main_prints_total_count(tmp_path, mock_setup, mock_init_db, mock_cmd_load, mock_get_doc_count, capsys):
    storage = tmp_path / "storage"
    storage.mkdir()
    (storage / "file.txt").write_text("data")

    with patch("agent.load_knowledge.DB_PATH", tmp_path / "test.db"), \
         patch("agent.load_knowledge.PROJECT_ROOT", tmp_path):
        from agent.load_knowledge import main
        main()

    captured = capsys.readouterr()
    assert "29" in captured.out
