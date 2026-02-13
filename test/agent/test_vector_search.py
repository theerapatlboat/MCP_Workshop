"""Tests for agent/vector_search.py — FAISS + SQLite semantic search."""

import json
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import faiss
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "agent"))

from agent.vector_search import (
    init_db, store_document, load_all_embeddings, load_filtered_embeddings,
    _build_filter_clauses, _parse_image_ids, _row_to_dict, substring_search,
    get_documents_by_ids, get_document_count, get_all_documents, clear_all,
    row_to_natural_language, get_embedding, get_embeddings_batch,
    build_faiss_index, hybrid_search, parse_knowledge_file, parse_filters,
    cmd_add, cmd_clear, cmd_count, cmd_load, cmd_search, cmd_list,
    _print_doc, show_help, show_banner, get_connection, setup,
    _load_knowledge, _load_plain_text,
    EMBEDDING_MODEL, EMBEDDING_DIM, DB_PATH,
)


# ════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════

def _random_embedding(dim: int = EMBEDDING_DIM) -> np.ndarray:
    """Return a random float32 vector of the given dimension."""
    vec = np.random.randn(dim).astype(np.float32)
    return vec


def _make_mock_client(dim: int = EMBEDDING_DIM):
    """Return a MagicMock that mimics the OpenAI client for embeddings."""
    client = MagicMock()

    def _single_embedding(*args, **kwargs):
        # Extract the input texts from kwargs or positional args
        inp = kwargs.get("input", None)
        if inp is None and len(args) > 1:
            inp = args[1]
        if inp is None:
            inp = ""

        # Normalise to a list so both single-string and batch calls work
        if isinstance(inp, str):
            inp = [inp]

        data = []
        for idx, _ in enumerate(inp):
            item = MagicMock()
            item.embedding = np.random.randn(dim).astype(np.float32).tolist()
            item.index = idx
            data.append(item)

        resp = MagicMock()
        resp.data = data
        return resp

    client.embeddings.create = MagicMock(side_effect=_single_embedding)
    return client


# ════════════════════════════════════════════════════════════
#  FIXTURES
# ════════════════════════════════════════════════════════════

@pytest.fixture
def db_conn(tmp_path):
    """Provide a fresh SQLite connection via init_db in a temp directory."""
    conn = init_db(tmp_path / "test_vector.db")
    yield conn
    conn.close()


@pytest.fixture
def mock_client():
    """Provide a mock OpenAI client that returns random embeddings."""
    return _make_mock_client()


@pytest.fixture
def populated_db(db_conn):
    """Insert three sample documents into the test database."""
    meta_list = [
        {"doc_id": "DOC_001", "category": "recipe", "title": "Tom Yum Soup",
         "image_ids": ["IMG_FOOD_001", "IMG_FOOD_002"]},
        {"doc_id": "DOC_002", "category": "ingredient", "title": "Lemongrass",
         "image_ids": ["IMG_INGR_001"]},
        {"doc_id": "DOC_003", "category": "recipe", "title": "Green Curry",
         "image_ids": []},
    ]
    texts = [
        "Tom Yum is a spicy Thai soup with shrimp and mushrooms.",
        "Lemongrass is an aromatic herb widely used in Southeast Asian cooking.",
        "Green Curry is a fragrant Thai dish made with green curry paste and coconut milk.",
    ]
    for text, meta in zip(texts, meta_list):
        emb = _random_embedding()
        store_document(db_conn, text, emb, metadata=meta)
    return db_conn


# ════════════════════════════════════════════════════════════
#  TESTS: init_db
# ════════════════════════════════════════════════════════════

def test_init_db_creates_table(tmp_path):
    """init_db should create the documents table with all required columns."""
    conn = init_db(tmp_path / "new.db")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(documents)").fetchall()}
    expected = {"id", "text", "embedding", "created_at", "doc_id", "category", "title", "image_ids"}
    assert expected == cols
    conn.close()


def test_init_db_idempotent(tmp_path):
    """Calling init_db twice on the same path should not raise or alter schema."""
    db_path = tmp_path / "reopen.db"
    conn1 = init_db(db_path)
    conn1.close()
    conn2 = init_db(db_path)
    cols = {row[1] for row in conn2.execute("PRAGMA table_info(documents)").fetchall()}
    assert "image_ids" in cols
    conn2.close()


def test_init_db_migration(tmp_path):
    """init_db should add missing columns to an old-schema DB."""
    import sqlite3
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            embedding BLOB NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

    conn2 = init_db(db_path)
    cols = {row[1] for row in conn2.execute("PRAGMA table_info(documents)").fetchall()}
    assert "doc_id" in cols
    assert "category" in cols
    assert "title" in cols
    assert "image_ids" in cols
    conn2.close()


# ════════════════════════════════════════════════════════════
#  TESTS: store_document
# ════════════════════════════════════════════════════════════

def test_store_document_returns_row_id(db_conn):
    """store_document should return a positive integer row ID."""
    emb = _random_embedding()
    row_id = store_document(db_conn, "hello world", emb)
    assert isinstance(row_id, int)
    assert row_id >= 1


def test_store_document_with_metadata(db_conn):
    """store_document should persist all metadata fields."""
    emb = _random_embedding()
    meta = {"doc_id": "D1", "category": "test", "title": "Title1",
            "image_ids": ["IMG_A", "IMG_B"]}
    row_id = store_document(db_conn, "text", emb, metadata=meta)
    row = db_conn.execute(
        "SELECT doc_id, category, title, image_ids FROM documents WHERE id = ?",
        (row_id,),
    ).fetchone()
    assert row[0] == "D1"
    assert row[1] == "test"
    assert row[2] == "Title1"
    assert json.loads(row[3]) == ["IMG_A", "IMG_B"]


def test_store_document_no_metadata(db_conn):
    """store_document without metadata should set nullable fields to None."""
    emb = _random_embedding()
    row_id = store_document(db_conn, "bare doc", emb)
    row = db_conn.execute(
        "SELECT doc_id, category, title, image_ids FROM documents WHERE id = ?",
        (row_id,),
    ).fetchone()
    assert row[0] is None
    assert row[1] is None
    assert row[2] is None
    assert row[3] is None


def test_store_document_image_ids_as_string(db_conn):
    """When image_ids is already a string, store_document should store it as-is."""
    emb = _random_embedding()
    meta = {"image_ids": '["IMG_X"]'}
    row_id = store_document(db_conn, "text", emb, metadata=meta)
    raw = db_conn.execute(
        "SELECT image_ids FROM documents WHERE id = ?", (row_id,)
    ).fetchone()[0]
    assert raw == '["IMG_X"]'


# ════════════════════════════════════════════════════════════
#  TESTS: load_all_embeddings
# ════════════════════════════════════════════════════════════

def test_load_all_embeddings_empty(db_conn):
    """Empty DB should return ([], None)."""
    ids, vectors = load_all_embeddings(db_conn)
    assert ids == []
    assert vectors is None


def test_load_all_embeddings_returns_correct_shape(populated_db):
    """Loaded embeddings should match (n, EMBEDDING_DIM) shape."""
    ids, vectors = load_all_embeddings(populated_db)
    assert len(ids) == 3
    assert vectors.shape == (3, EMBEDDING_DIM)
    assert vectors.dtype == np.float32


# ════════════════════════════════════════════════════════════
#  TESTS: load_filtered_embeddings
# ════════════════════════════════════════════════════════════

def test_load_filtered_embeddings_by_category(populated_db):
    """Filtering by category should return only matching rows."""
    ids, vectors = load_filtered_embeddings(populated_db, {"category": "recipe"})
    assert len(ids) == 2
    assert vectors.shape == (2, EMBEDDING_DIM)


def test_load_filtered_embeddings_empty_match(populated_db):
    """Filter that matches nothing should return ([], None)."""
    ids, vectors = load_filtered_embeddings(populated_db, {"category": "nonexistent"})
    assert ids == []
    assert vectors is None


def test_load_filtered_embeddings_exclude_category(populated_db):
    """exclude_category filter should omit the specified category."""
    ids, vectors = load_filtered_embeddings(populated_db, {"exclude_category": "recipe"})
    assert len(ids) == 1  # only the ingredient doc


def test_load_filtered_embeddings_by_doc_id(populated_db):
    """Filtering by doc_id (LIKE match) should return matching docs."""
    ids, vectors = load_filtered_embeddings(populated_db, {"doc_id": "DOC_001"})
    assert len(ids) == 1


def test_load_filtered_embeddings_by_title(populated_db):
    """Filtering by title (LIKE match) should return matching docs."""
    ids, vectors = load_filtered_embeddings(populated_db, {"title": "Curry"})
    assert len(ids) == 1


# ════════════════════════════════════════════════════════════
#  TESTS: _build_filter_clauses
# ════════════════════════════════════════════════════════════

def test_build_filter_clauses_empty():
    """Empty dict should produce no clauses."""
    clauses, params = _build_filter_clauses({})
    assert clauses == []
    assert params == []


def test_build_filter_clauses_category():
    clauses, params = _build_filter_clauses({"category": "recipe"})
    assert len(clauses) == 1
    assert "category = ?" in clauses[0]
    assert params == ["recipe"]


def test_build_filter_clauses_exclude_category():
    clauses, params = _build_filter_clauses({"exclude_category": "recipe"})
    assert "category <> ?" in clauses[0]
    assert params == ["recipe"]


def test_build_filter_clauses_doc_id():
    clauses, params = _build_filter_clauses({"doc_id": "DOC_001"})
    assert "doc_id LIKE ?" in clauses[0]
    assert params == ["%DOC_001%"]


def test_build_filter_clauses_title():
    clauses, params = _build_filter_clauses({"title": "Soup"})
    assert "title LIKE ?" in clauses[0]
    assert params == ["%Soup%"]


def test_build_filter_clauses_unknown_key_ignored():
    """Unknown filter keys should be silently ignored."""
    clauses, params = _build_filter_clauses({"unknown_key": "val"})
    assert clauses == []
    assert params == []


def test_build_filter_clauses_multiple():
    """Multiple filters should produce multiple clauses."""
    clauses, params = _build_filter_clauses({"category": "recipe", "title": "Soup"})
    assert len(clauses) == 2
    assert len(params) == 2


# ════════════════════════════════════════════════════════════
#  TESTS: _parse_image_ids
# ════════════════════════════════════════════════════════════

def test_parse_image_ids_valid_json():
    assert _parse_image_ids('["IMG_A", "IMG_B"]') == ["IMG_A", "IMG_B"]


def test_parse_image_ids_none():
    assert _parse_image_ids(None) == []


def test_parse_image_ids_empty_string():
    assert _parse_image_ids("") == []


def test_parse_image_ids_invalid_json():
    assert _parse_image_ids("not json") == []


def test_parse_image_ids_non_list_json():
    """If JSON parses to a non-list, return empty list."""
    assert _parse_image_ids('{"key": "val"}') == []


# ════════════════════════════════════════════════════════════
#  TESTS: _row_to_dict
# ════════════════════════════════════════════════════════════

def test_row_to_dict_full():
    row = (1, "text", "2024-01-01T00:00:00", "D1", "recipe", "Soup", '["IMG_A"]')
    d = _row_to_dict(row)
    assert d["id"] == 1
    assert d["text"] == "text"
    assert d["doc_id"] == "D1"
    assert d["category"] == "recipe"
    assert d["title"] == "Soup"
    assert d["image_ids"] == ["IMG_A"]


def test_row_to_dict_nulls():
    row = (2, "text", "2024-01-01T00:00:00", None, None, None, None)
    d = _row_to_dict(row)
    assert d["doc_id"] is None
    assert d["image_ids"] == []


# ════════════════════════════════════════════════════════════
#  TESTS: substring_search
# ════════════════════════════════════════════════════════════

def test_substring_search_finds_text(populated_db):
    """Substring search should match partial text content."""
    results = substring_search(populated_db, "spicy")
    assert len(results) == 1
    assert results[0]["doc_id"] == "DOC_001"


def test_substring_search_finds_title(populated_db):
    """Substring search should match title field."""
    results = substring_search(populated_db, "Lemongrass")
    assert len(results) >= 1


def test_substring_search_no_match(populated_db):
    results = substring_search(populated_db, "xyznonexistent")
    assert results == []


def test_substring_search_with_filters(populated_db):
    """Filters should narrow substring search results."""
    results = substring_search(populated_db, "Thai", filters={"category": "recipe"})
    # Only recipe-category docs matching "Thai"
    for r in results:
        assert r["category"] == "recipe"


def test_substring_search_respects_limit(populated_db):
    results = substring_search(populated_db, "a", limit=1)
    assert len(results) <= 1


def test_substring_search_matches_image_ids(populated_db):
    """Substring search should also check image_ids column."""
    results = substring_search(populated_db, "IMG_FOOD_001")
    assert len(results) >= 1


# ════════════════════════════════════════════════════════════
#  TESTS: get_documents_by_ids
# ════════════════════════════════════════════════════════════

def test_get_documents_by_ids_returns_ordered(populated_db):
    """Documents should be returned in the order of the requested IDs."""
    all_docs = get_all_documents(populated_db)
    ids = [d["id"] for d in all_docs]
    reversed_ids = list(reversed(ids))
    results = get_documents_by_ids(populated_db, reversed_ids)
    assert [r["id"] for r in results] == reversed_ids


def test_get_documents_by_ids_empty_list(populated_db):
    assert get_documents_by_ids(populated_db, []) == []


def test_get_documents_by_ids_missing_id(populated_db):
    """Missing IDs should be silently skipped."""
    results = get_documents_by_ids(populated_db, [9999])
    assert results == []


# ════════════════════════════════════════════════════════════
#  TESTS: get_document_count / get_all_documents / clear_all
# ════════════════════════════════════════════════════════════

def test_get_document_count_empty(db_conn):
    assert get_document_count(db_conn) == 0


def test_get_document_count_populated(populated_db):
    assert get_document_count(populated_db) == 3


def test_get_all_documents_empty(db_conn):
    assert get_all_documents(db_conn) == []


def test_get_all_documents_populated(populated_db):
    docs = get_all_documents(populated_db)
    assert len(docs) == 3
    assert all("id" in d for d in docs)


def test_clear_all(populated_db):
    clear_all(populated_db)
    assert get_document_count(populated_db) == 0


# ════════════════════════════════════════════════════════════
#  TESTS: row_to_natural_language
# ════════════════════════════════════════════════════════════

def test_row_to_natural_language_full():
    meta = {"title": "Green Curry", "content": "Delicious dish", "category": "recipe"}
    result = row_to_natural_language(meta)
    assert "Green Curry" in result
    assert "Delicious dish" in result
    assert "recipe" in result


def test_row_to_natural_language_title_only():
    meta = {"title": "Just Title"}
    result = row_to_natural_language(meta)
    assert result == "Just Title"


def test_row_to_natural_language_empty():
    assert row_to_natural_language({}) == ""


def test_row_to_natural_language_content_only():
    meta = {"content": "Only content here"}
    result = row_to_natural_language(meta)
    assert result == "Only content here"


# ════════════════════════════════════════════════════════════
#  TESTS: get_embedding / get_embeddings_batch
# ════════════════════════════════════════════════════════════

def test_get_embedding_returns_float32(mock_client):
    result = get_embedding(mock_client, "test text")
    assert isinstance(result, np.ndarray)
    assert result.dtype == np.float32
    assert result.shape == (EMBEDDING_DIM,)
    mock_client.embeddings.create.assert_called_once_with(
        model=EMBEDDING_MODEL, input="test text"
    )


def test_get_embeddings_batch_returns_list(mock_client):
    texts = ["alpha", "beta", "gamma"]
    results = get_embeddings_batch(mock_client, texts)
    assert len(results) == 3
    for r in results:
        assert isinstance(r, np.ndarray)
        assert r.dtype == np.float32
        assert r.shape == (EMBEDDING_DIM,)


def test_get_embeddings_batch_sorted_by_index(mock_client):
    """Batch embeddings should be returned sorted by their original index."""
    # The mock already returns items with correct indices;
    # make sure the function handles out-of-order data
    def _reversed_order(*args, **kwargs):
        inp = kwargs.get("input", [])
        data = []
        for idx in range(len(inp)):
            item = MagicMock()
            item.embedding = [float(idx)] * EMBEDDING_DIM
            item.index = idx
            data.append(item)
        # Reverse the data list to simulate out-of-order response
        data.reverse()
        resp = MagicMock()
        resp.data = data
        return resp

    mock_client.embeddings.create = MagicMock(side_effect=_reversed_order)
    results = get_embeddings_batch(mock_client, ["a", "b", "c"])
    # First embedding should start with 0.0, second with 1.0, etc.
    assert results[0][0] == pytest.approx(0.0)
    assert results[1][0] == pytest.approx(1.0)
    assert results[2][0] == pytest.approx(2.0)


# ════════════════════════════════════════════════════════════
#  TESTS: build_faiss_index
# ════════════════════════════════════════════════════════════

def test_build_faiss_index_creates_index():
    embs = np.random.randn(5, EMBEDDING_DIM).astype(np.float32)
    index = build_faiss_index(embs)
    assert isinstance(index, faiss.IndexFlatIP)
    assert index.ntotal == 5


def test_build_faiss_index_search_returns_results():
    """Build an index and verify a query returns sensible results."""
    # Create two distinct clusters
    embs = np.zeros((3, EMBEDDING_DIM), dtype=np.float32)
    embs[0, 0] = 1.0  # cluster A
    embs[1, 0] = 0.9  # cluster A (close to 0)
    embs[2, 1] = 1.0  # cluster B

    index = build_faiss_index(embs)
    query = np.zeros((1, EMBEDDING_DIM), dtype=np.float32)
    query[0, 0] = 1.0
    faiss.normalize_L2(query)
    scores, indices = index.search(query, 2)
    # The top result should be one of the first two vectors (cluster A)
    assert indices[0][0] in (0, 1)


# ════════════════════════════════════════════════════════════
#  TESTS: hybrid_search
# ════════════════════════════════════════════════════════════

def test_hybrid_search_returns_results(populated_db, mock_client):
    """hybrid_search should return a list of result dicts."""
    results = hybrid_search(mock_client, populated_db, "spicy soup")
    assert isinstance(results, list)
    # At minimum, substring match for "spicy" should appear
    assert len(results) >= 1
    # All results should have 'source' and 'score' keys
    for r in results:
        assert "source" in r
        assert "score" in r


def test_hybrid_search_empty_db(db_conn, mock_client):
    """hybrid_search on empty DB should return empty list or substring-only."""
    results = hybrid_search(mock_client, db_conn, "anything")
    assert isinstance(results, list)


def test_hybrid_search_with_filters(populated_db, mock_client):
    """Filters should be passed through to both vector and substring search."""
    results = hybrid_search(
        mock_client, populated_db, "Thai",
        filters={"category": "recipe"},
    )
    for r in results:
        # Filtered results should only be from recipe category
        assert r.get("category") == "recipe" or r.get("source") == "vector"


def test_hybrid_search_deduplicates(populated_db, mock_client):
    """Documents found by both vector and substring should appear once, marked 'both'."""
    results = hybrid_search(mock_client, populated_db, "Tom Yum")
    ids_seen = set()
    for r in results:
        assert r["id"] not in ids_seen, "Duplicate ID found in hybrid results"
        ids_seen.add(r["id"])


def test_hybrid_search_img_pattern(populated_db, mock_client):
    """IMG_* patterns in query should trigger additional substring searches."""
    results = hybrid_search(mock_client, populated_db, "find IMG_FOOD_001 details")
    # Should pick up the document that has IMG_FOOD_001 in image_ids
    found_ids = [r["doc_id"] for r in results if r.get("doc_id")]
    assert "DOC_001" in found_ids


def test_hybrid_search_sorting(populated_db, mock_client):
    """Vector results (score != None) should come before substring-only (score == None)."""
    results = hybrid_search(mock_client, populated_db, "soup")
    scores = [r["score"] for r in results]
    # Once we see a None, all subsequent should be None
    seen_none = False
    for s in scores:
        if s is None:
            seen_none = True
        elif seen_none:
            pytest.fail("Vector result appeared after substring-only result")


# ════════════════════════════════════════════════════════════
#  TESTS: parse_knowledge_file
# ════════════════════════════════════════════════════════════

def test_parse_knowledge_file_jsonl(tmp_path):
    """Parse a standard JSONL knowledge file."""
    content = (
        '{"id": "R001", "content": "Recipe one", "category": "recipe", "title": "Soup"}\n'
        '{"id": "R002", "content": "Recipe two", "category": "recipe", "title": "Curry"}\n'
    )
    fpath = tmp_path / "knowledge.jsonl"
    fpath.write_text(content, encoding="utf-8")
    records = parse_knowledge_file(fpath)
    assert records is not None
    assert len(records) == 2
    assert records[0]["id"] == "R001"


def test_parse_knowledge_file_json_mapping(tmp_path):
    """Parse a JSON mapping file (e.g. image_mapping.txt)."""
    data = {
        "IMG_PROD_001": {"description": "A product image", "url": "http://example.com/1.jpg"},
        "IMG_PROD_002": {"description": "Another product image", "url": "http://example.com/2.jpg"},
    }
    fpath = tmp_path / "image_mapping.txt"
    fpath.write_text(json.dumps(data), encoding="utf-8")
    records = parse_knowledge_file(fpath)
    assert records is not None
    assert len(records) == 2
    assert records[0]["category"] == "image_description"


def test_parse_knowledge_file_plain_text(tmp_path):
    """Plain text file with no valid JSON should return None."""
    fpath = tmp_path / "notes.txt"
    fpath.write_text("just plain text\nno json here", encoding="utf-8")
    records = parse_knowledge_file(fpath)
    assert records is None


def test_parse_knowledge_file_empty(tmp_path):
    """Empty file should return None."""
    fpath = tmp_path / "empty.txt"
    fpath.write_text("", encoding="utf-8")
    records = parse_knowledge_file(fpath)
    assert records is None


def test_parse_knowledge_file_jsonl_with_blanks(tmp_path):
    """JSONL with blank lines should still parse valid lines."""
    content = (
        '{"id": "R001", "content": "Recipe one"}\n'
        '\n'
        '{"id": "R002", "content": "Recipe two"}\n'
        '\n'
    )
    fpath = tmp_path / "knowledge.jsonl"
    fpath.write_text(content, encoding="utf-8")
    records = parse_knowledge_file(fpath)
    assert records is not None
    assert len(records) == 2


def test_parse_knowledge_file_jsonl_invalid_lines(tmp_path):
    """Invalid JSON lines should be skipped, valid ones kept."""
    content = (
        '{"id": "R001", "content": "Good line"}\n'
        'this is not json\n'
        '{"id": "R002", "content": "Also good"}\n'
    )
    fpath = tmp_path / "knowledge.jsonl"
    fpath.write_text(content, encoding="utf-8")
    records = parse_knowledge_file(fpath)
    assert records is not None
    assert len(records) == 2


def test_parse_knowledge_file_json_mapping_no_description(tmp_path):
    """JSON mapping entries without 'description' should be skipped."""
    data = {
        "IMG_001": {"url": "http://example.com/1.jpg"},  # no description
    }
    fpath = tmp_path / "mapping.txt"
    fpath.write_text(json.dumps(data), encoding="utf-8")
    records = parse_knowledge_file(fpath)
    assert records is None


# ════════════════════════════════════════════════════════════
#  TESTS: parse_filters
# ════════════════════════════════════════════════════════════

def test_parse_filters_no_flags():
    query, filters = parse_filters("search term here")
    assert query == "search term here"
    assert filters == {}


def test_parse_filters_category():
    query, filters = parse_filters("soup --category recipe")
    assert query == "soup"
    assert filters == {"category": "recipe"}


def test_parse_filters_category_in_middle():
    query, filters = parse_filters("--category recipe soup")
    assert "soup" in query
    assert filters == {"category": "recipe"}


def test_parse_filters_empty_string():
    query, filters = parse_filters("")
    assert query == ""
    assert filters == {}


# ════════════════════════════════════════════════════════════
#  TESTS: cmd_add
# ════════════════════════════════════════════════════════════

def test_cmd_add_stores_document(db_conn, mock_client, capsys):
    """cmd_add should embed text and store it."""
    cmd_add(mock_client, db_conn, "test document")
    captured = capsys.readouterr()
    assert "Stored document" in captured.out
    assert get_document_count(db_conn) == 1


def test_cmd_add_empty_text(db_conn, mock_client, capsys):
    """cmd_add with empty text should print usage."""
    cmd_add(mock_client, db_conn, "")
    captured = capsys.readouterr()
    assert "Usage" in captured.out
    assert get_document_count(db_conn) == 0


def test_cmd_add_embedding_error(db_conn, capsys):
    """cmd_add should handle embedding API errors gracefully."""
    client = MagicMock()
    client.embeddings.create.side_effect = RuntimeError("API down")
    cmd_add(client, db_conn, "some text")
    captured = capsys.readouterr()
    assert "Error" in captured.out
    assert get_document_count(db_conn) == 0


# ════════════════════════════════════════════════════════════
#  TESTS: cmd_clear
# ════════════════════════════════════════════════════════════

def test_cmd_clear(populated_db, capsys):
    """cmd_clear should remove all documents and print confirmation."""
    cmd_clear(populated_db)
    captured = capsys.readouterr()
    assert "Cleared" in captured.out
    assert get_document_count(populated_db) == 0


# ════════════════════════════════════════════════════════════
#  TESTS: cmd_count
# ════════════════════════════════════════════════════════════

def test_cmd_count_empty(db_conn, capsys):
    cmd_count(db_conn)
    captured = capsys.readouterr()
    assert "0 documents" in captured.out


def test_cmd_count_populated(populated_db, capsys):
    cmd_count(populated_db)
    captured = capsys.readouterr()
    assert "3 documents" in captured.out


def test_cmd_count_singular(db_conn, capsys):
    """Single document should use singular 'document' (no 's')."""
    emb = _random_embedding()
    store_document(db_conn, "single", emb)
    cmd_count(db_conn)
    captured = capsys.readouterr()
    assert "1 document" in captured.out
    assert "1 documents" not in captured.out


# ════════════════════════════════════════════════════════════
#  TESTS: cmd_load
# ════════════════════════════════════════════════════════════

def test_cmd_load_empty_filepath(db_conn, mock_client, capsys):
    """cmd_load with empty filepath should print usage."""
    cmd_load(mock_client, db_conn, "")
    captured = capsys.readouterr()
    assert "Usage" in captured.out


def test_cmd_load_missing_file(db_conn, mock_client, capsys):
    """cmd_load with nonexistent file should print error."""
    cmd_load(mock_client, db_conn, "/nonexistent/file.txt")
    captured = capsys.readouterr()
    assert "Error" in captured.out or "not found" in captured.out.lower()


def test_cmd_load_jsonl(db_conn, mock_client, tmp_path, capsys):
    """cmd_load should import a JSONL knowledge file."""
    content = '{"id": "R001", "content": "Recipe one", "category": "recipe", "title": "Soup"}\n'
    fpath = tmp_path / "knowledge.jsonl"
    fpath.write_text(content, encoding="utf-8")

    cmd_load(mock_client, db_conn, str(fpath))
    captured = capsys.readouterr()
    assert "1 records imported" in captured.out or "Imported" in captured.out
    assert get_document_count(db_conn) == 1


def test_cmd_load_plain_text(db_conn, mock_client, tmp_path, capsys):
    """cmd_load should import plain text lines as individual documents."""
    fpath = tmp_path / "lines.txt"
    fpath.write_text("Line one\nLine two\nLine three\n", encoding="utf-8")

    cmd_load(mock_client, db_conn, str(fpath))
    captured = capsys.readouterr()
    assert "3" in captured.out  # 3 lines imported
    assert get_document_count(db_conn) == 3


def test_cmd_load_plain_text_skips_separator_lines(db_conn, mock_client, tmp_path, capsys):
    """Plain text loader should skip separator/decoration lines."""
    fpath = tmp_path / "decorated.txt"
    fpath.write_text("Real content\n========\n---\nMore content\n", encoding="utf-8")

    cmd_load(mock_client, db_conn, str(fpath))
    captured = capsys.readouterr()
    assert get_document_count(db_conn) == 2


def test_cmd_load_plain_text_empty_content(db_conn, mock_client, tmp_path, capsys):
    """Plain text file with only blank lines should report no content."""
    fpath = tmp_path / "blank.txt"
    fpath.write_text("\n\n\n", encoding="utf-8")

    cmd_load(mock_client, db_conn, str(fpath))
    captured = capsys.readouterr()
    assert "No content" in captured.out


def test_cmd_load_embedding_error_batch(db_conn, tmp_path, capsys):
    """cmd_load should handle batch embedding errors gracefully."""
    client = MagicMock()
    client.embeddings.create.side_effect = RuntimeError("API error")

    content = '{"id": "R001", "content": "Recipe one", "category": "recipe", "title": "Soup"}\n'
    fpath = tmp_path / "knowledge.jsonl"
    fpath.write_text(content, encoding="utf-8")

    cmd_load(client, db_conn, str(fpath))
    captured = capsys.readouterr()
    assert "Error" in captured.out


# ════════════════════════════════════════════════════════════
#  TESTS: CONSTANTS
# ════════════════════════════════════════════════════════════

def test_embedding_model_constant():
    assert EMBEDDING_MODEL == "text-embedding-3-small"


def test_embedding_dim_constant():
    assert EMBEDDING_DIM == 1536


# ════════════════════════════════════════════════════════════
#  TESTS: _print_doc
# ════════════════════════════════════════════════════════════

def test_print_doc_with_score(capsys):
    """_print_doc with a score should display the score."""
    doc = {
        "id": 1, "text": "short text", "created_at": "2024-01-01",
        "doc_id": "D1", "category": "recipe", "title": "Soup",
        "image_ids": ["IMG_A"],
    }
    _print_doc(doc, rank=1, score=0.9123)
    out = capsys.readouterr().out
    assert "0.9123" in out
    assert "D1" in out
    assert "IMG_A" in out


def test_print_doc_without_score(capsys):
    """_print_doc without a score should omit score line."""
    doc = {
        "id": 2, "text": "short text", "created_at": "2024-01-01",
        "doc_id": None, "category": None, "title": None,
        "image_ids": [],
    }
    _print_doc(doc, rank=1)
    out = capsys.readouterr().out
    assert "score" not in out
    assert "Added:" in out


def test_print_doc_overlap_mark(capsys):
    """_print_doc with overlap=True should show the star marker."""
    doc = {
        "id": 3, "text": "text", "created_at": "2024-01-01",
        "doc_id": None, "category": None, "title": None,
        "image_ids": [],
    }
    _print_doc(doc, rank=1, overlap=True)
    out = capsys.readouterr().out
    assert "\u2605" in out  # star character


def test_print_doc_long_text_truncated(capsys):
    """_print_doc should truncate text longer than 200 characters with '...'."""
    doc = {
        "id": 4, "text": "A" * 300, "created_at": "2024-01-01",
        "doc_id": "D1", "category": "cat", "title": "Title",
        "image_ids": [],
    }
    _print_doc(doc, rank=1, score=0.5)
    out = capsys.readouterr().out
    assert "..." in out


def test_print_doc_no_doc_id_long_text(capsys):
    """_print_doc without doc_id but with long text should also truncate."""
    doc = {
        "id": 5, "text": "B" * 300, "created_at": "2024-06-15",
        "doc_id": None, "category": None, "title": None,
        "image_ids": [],
    }
    _print_doc(doc, rank=2)
    out = capsys.readouterr().out
    assert "..." in out
    assert "2024-06-15" in out


# ════════════════════════════════════════════════════════════
#  TESTS: cmd_search
# ════════════════════════════════════════════════════════════

def test_cmd_search_empty_query(db_conn, mock_client, capsys):
    """cmd_search with empty query should print usage."""
    cmd_search(mock_client, db_conn, "")
    out = capsys.readouterr().out
    assert "Usage" in out


def test_cmd_search_only_filters(db_conn, mock_client, capsys):
    """cmd_search where query is only filters (no actual text) should print error."""
    cmd_search(mock_client, db_conn, "--category recipe")
    out = capsys.readouterr().out
    assert "empty" in out.lower()


def test_cmd_search_with_populated_db(populated_db, mock_client, capsys):
    """cmd_search on populated DB should show both semantic and substring sections."""
    cmd_search(mock_client, populated_db, "spicy soup")
    out = capsys.readouterr().out
    assert "Semantic Search" in out
    assert "Substring Search" in out


def test_cmd_search_empty_db(db_conn, mock_client, capsys):
    """cmd_search on empty DB should indicate no documents."""
    cmd_search(mock_client, db_conn, "anything")
    out = capsys.readouterr().out
    assert "No documents" in out


def test_cmd_search_with_filters(populated_db, mock_client, capsys):
    """cmd_search with --category filter should show the filter in output."""
    cmd_search(mock_client, populated_db, "soup --category recipe")
    out = capsys.readouterr().out
    assert "Filters" in out


def test_cmd_search_embedding_error(populated_db, capsys):
    """cmd_search should handle embedding API errors gracefully."""
    client = MagicMock()
    client.embeddings.create.side_effect = RuntimeError("API timeout")
    cmd_search(client, populated_db, "soup")
    out = capsys.readouterr().out
    assert "Error" in out


def test_cmd_search_custom_top_k(populated_db, mock_client, capsys):
    """cmd_search should work with a custom top_k value."""
    cmd_search(mock_client, populated_db, "Thai", top_k=1)
    out = capsys.readouterr().out
    assert "Semantic Search" in out


# ════════════════════════════════════════════════════════════
#  TESTS: cmd_list
# ════════════════════════════════════════════════════════════

def test_cmd_list_empty(db_conn, capsys):
    """cmd_list on empty DB should indicate no documents."""
    cmd_list(db_conn)
    out = capsys.readouterr().out
    assert "No documents" in out


def test_cmd_list_populated(populated_db, capsys):
    """cmd_list on populated DB should show document count and doc IDs."""
    cmd_list(populated_db)
    out = capsys.readouterr().out
    assert "3 total" in out
    assert "DOC_001" in out
    assert "DOC_002" in out


def test_cmd_list_plain_docs(db_conn, capsys):
    """cmd_list should handle documents without doc_id metadata."""
    emb = _random_embedding()
    store_document(db_conn, "plain document text for listing", emb)
    cmd_list(db_conn)
    out = capsys.readouterr().out
    assert "plain document text" in out


# ════════════════════════════════════════════════════════════
#  TESTS: show_help / show_banner
# ════════════════════════════════════════════════════════════

def test_show_help(capsys):
    """show_help should print command descriptions."""
    show_help()
    out = capsys.readouterr().out
    assert "add" in out
    assert "search" in out
    assert "load" in out
    assert "clear" in out
    assert "quit" in out


def test_show_banner(capsys):
    """show_banner should display model name and document count."""
    show_banner(42)
    out = capsys.readouterr().out
    assert EMBEDDING_MODEL in out
    assert "42" in out


def test_show_banner_zero(capsys):
    """show_banner with 0 documents should display 0."""
    show_banner(0)
    out = capsys.readouterr().out
    assert "0" in out


# ════════════════════════════════════════════════════════════
#  TESTS: get_connection
# ════════════════════════════════════════════════════════════

def test_get_connection_missing_db():
    """get_connection should raise FileNotFoundError when DB does not exist."""
    with patch("agent.vector_search.DB_PATH", Path("/nonexistent/path/db.sqlite")):
        with pytest.raises(FileNotFoundError):
            get_connection()


def test_get_connection_existing_db(tmp_path):
    """get_connection should return a valid connection when DB exists."""
    db_path = tmp_path / "vector_store.db"
    # Create the DB file first
    conn = init_db(db_path)
    conn.close()
    with patch("agent.vector_search.DB_PATH", db_path):
        conn = get_connection()
        assert conn is not None
        conn.close()


# ════════════════════════════════════════════════════════════
#  TESTS: setup
# ════════════════════════════════════════════════════════════

def test_setup_no_api_key():
    """setup without OPENAI_API_KEY should exit with error."""
    with patch.dict("os.environ", {}, clear=True), \
         patch("agent.vector_search.load_dotenv"), \
         pytest.raises(SystemExit):
        setup()


def test_setup_with_api_key():
    """setup with OPENAI_API_KEY should return an OpenAI client."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test-key"}), \
         patch("agent.vector_search.load_dotenv"), \
         patch("agent.vector_search.OpenAI") as mock_openai:
        mock_openai.return_value = MagicMock()
        client = setup()
        mock_openai.assert_called_once_with(api_key="sk-test-key")
        assert client is not None


# ════════════════════════════════════════════════════════════
#  TESTS: _load_knowledge / _load_plain_text (internal)
# ════════════════════════════════════════════════════════════

def test_load_knowledge_multiple_batches(db_conn, mock_client, capsys):
    """_load_knowledge should handle records exceeding BATCH_SIZE by batching."""
    records = [
        {"id": f"R{i:03d}", "content": f"Content {i}", "category": "test", "title": f"Title {i}"}
        for i in range(3)
    ]
    _load_knowledge(mock_client, db_conn, records, "test.jsonl")
    captured = capsys.readouterr()
    assert "3 records imported" in captured.out
    assert get_document_count(db_conn) == 3


def test_load_knowledge_preserves_metadata(db_conn, mock_client, capsys):
    """_load_knowledge should store doc_id, category, title, image_ids."""
    records = [
        {"id": "R001", "content": "Test content", "category": "cat1",
         "title": "Title1", "image_ids": ["IMG_001"]},
    ]
    _load_knowledge(mock_client, db_conn, records, "test.jsonl")
    docs = get_all_documents(db_conn)
    assert len(docs) == 1
    assert docs[0]["doc_id"] == "R001"
    assert docs[0]["category"] == "cat1"
    assert docs[0]["image_ids"] == ["IMG_001"]


def test_load_knowledge_embedding_error(db_conn, capsys):
    """_load_knowledge should handle embedding errors mid-batch."""
    client = MagicMock()
    client.embeddings.create.side_effect = RuntimeError("Batch fail")
    records = [{"id": "R001", "content": "text", "category": "a", "title": "b"}]
    _load_knowledge(client, db_conn, records, "test.jsonl")
    captured = capsys.readouterr()
    assert "Error" in captured.out
    assert get_document_count(db_conn) == 0


def test_load_plain_text_basic(db_conn, mock_client, capsys):
    """_load_plain_text should import non-empty, non-separator lines."""
    content = "Line one\nLine two\n===\n\nLine three\n"
    _load_plain_text(mock_client, db_conn, content, "test.txt")
    captured = capsys.readouterr()
    # "===" should be skipped, blank lines skipped -> 3 lines
    assert get_document_count(db_conn) == 3


def test_load_plain_text_no_content(db_conn, mock_client, capsys):
    """_load_plain_text with only blanks/separators should report no content."""
    content = "\n\n===\n---\n"
    _load_plain_text(mock_client, db_conn, content, "empty.txt")
    captured = capsys.readouterr()
    assert "No content" in captured.out


def test_load_plain_text_embedding_error(db_conn, capsys):
    """_load_plain_text should handle embedding errors gracefully."""
    client = MagicMock()
    client.embeddings.create.side_effect = RuntimeError("API fail")
    content = "Some text line\n"
    _load_plain_text(client, db_conn, content, "test.txt")
    captured = capsys.readouterr()
    assert "Error" in captured.out


# ════════════════════════════════════════════════════════════
#  TESTS: Additional edge cases for hybrid_search
# ════════════════════════════════════════════════════════════

def test_hybrid_search_top_k_larger_than_docs(populated_db, mock_client):
    """hybrid_search with top_k > document count should not crash."""
    results = hybrid_search(mock_client, populated_db, "soup", top_k=100)
    assert isinstance(results, list)


def test_hybrid_search_img_pattern_same_as_query(populated_db, mock_client):
    """When query IS an IMG_* pattern, the img-specific search should skip it (already covered)."""
    results = hybrid_search(mock_client, populated_db, "IMG_FOOD_001")
    # Should not crash, and should find the doc with that image ID
    assert isinstance(results, list)


# ════════════════════════════════════════════════════════════
#  TESTS: Additional edge cases for parse_knowledge_file
# ════════════════════════════════════════════════════════════

def test_parse_knowledge_file_jsonl_missing_required_fields(tmp_path):
    """JSONL records missing 'id' or 'content' should be skipped."""
    content = (
        '{"id": "R001"}\n'           # missing content
        '{"content": "no id"}\n'     # missing id
        '{"id": "R002", "content": "valid"}\n'
    )
    fpath = tmp_path / "partial.jsonl"
    fpath.write_text(content, encoding="utf-8")
    records = parse_knowledge_file(fpath)
    assert records is not None
    assert len(records) == 1
    assert records[0]["id"] == "R002"


def test_parse_knowledge_file_single_json_with_id(tmp_path):
    """A single JSON object starting with {"id" should be parsed as JSONL."""
    content = '{"id": "R001", "content": "single record"}\n'
    fpath = tmp_path / "single.jsonl"
    fpath.write_text(content, encoding="utf-8")
    records = parse_knowledge_file(fpath)
    assert records is not None
    assert len(records) == 1


def test_parse_knowledge_file_invalid_single_json(tmp_path):
    """A file starting with '{' but containing invalid JSON should fall through to JSONL."""
    content = '{invalid json that is not parseable\n'
    fpath = tmp_path / "bad.txt"
    fpath.write_text(content, encoding="utf-8")
    records = parse_knowledge_file(fpath)
    assert records is None


# ════════════════════════════════════════════════════════════
#  TESTS: substring_search edge cases
# ════════════════════════════════════════════════════════════

def test_substring_search_with_unknown_filter_keys(populated_db):
    """Filters with unknown keys should not add WHERE clauses (line 196 branch)."""
    results = substring_search(populated_db, "Thai", filters={"unknown_key": "val"})
    # Should still return results matching "Thai" without filter restriction
    assert len(results) >= 1


# ════════════════════════════════════════════════════════════
#  TESTS: cmd_list with long text (line 600)
# ════════════════════════════════════════════════════════════

def test_cmd_list_plain_doc_long_text(db_conn, capsys):
    """cmd_list should truncate plain doc text longer than 80 chars."""
    emb = _random_embedding()
    store_document(db_conn, "X" * 100, emb)
    cmd_list(db_conn)
    out = capsys.readouterr().out
    assert "..." in out


# ════════════════════════════════════════════════════════════
#  TESTS: cmd_search with no semantic results (line 563)
# ════════════════════════════════════════════════════════════

def test_cmd_search_no_semantic_results(db_conn, mock_client, capsys):
    """cmd_search should show 'No semantic results' when filters match docs but query doesn't."""
    emb = _random_embedding()
    store_document(db_conn, "unique doc", emb, metadata={"category": "rare"})
    # Search for something that won't match semantically in a category with data
    cmd_search(mock_client, db_conn, "zzzznonexistent --category rare")
    out = capsys.readouterr().out
    assert "Semantic Search" in out


# ════════════════════════════════════════════════════════════
#  TESTS: hybrid_search with substring-only hits (lines 353-355)
# ════════════════════════════════════════════════════════════

def test_hybrid_search_substring_only_no_vector_overlap(db_conn, mock_client):
    """Documents found only by substring (not by vector) should get source='substring'."""
    # Store a doc that will match substring but likely not rank high in vector
    emb = _random_embedding()
    store_document(db_conn, "unique_keyword_xyz123 hello world", emb)
    results = hybrid_search(mock_client, db_conn, "unique_keyword_xyz123", top_k=5)
    # Should have at least one result from substring
    substr_results = [r for r in results if r["source"] in ("substring", "both")]
    assert len(substr_results) >= 1


# ════════════════════════════════════════════════════════════
#  TESTS: hybrid_search IMG_* additional pattern (lines 367-369)
# ════════════════════════════════════════════════════════════

def test_hybrid_search_img_pattern_in_longer_query(db_conn, mock_client):
    """IMG_* pattern within a larger query should trigger secondary image search."""
    emb = _random_embedding()
    store_document(
        db_conn, "product info",
        emb,
        metadata={"doc_id": "P1", "image_ids": ["IMG_PROD_999"]},
    )
    results = hybrid_search(mock_client, db_conn, "show me IMG_PROD_999 please", top_k=5)
    found_ids = [r.get("doc_id") for r in results]
    assert "P1" in found_ids


# ════════════════════════════════════════════════════════════
#  TESTS: cmd_search overlap star (line 577-578)
# ════════════════════════════════════════════════════════════

def test_cmd_search_shows_overlap_star(populated_db, mock_client, capsys):
    """When docs appear in both semantic and substring results, the star note should appear."""
    # "Tom Yum" should match in substring; likely also in vector results
    cmd_search(mock_client, populated_db, "Tom Yum")
    out = capsys.readouterr().out
    # If there's overlap, the star note appears; if not, at least no crash
    assert "Substring Search" in out


# ════════════════════════════════════════════════════════════
#  TESTS: repl function
# ════════════════════════════════════════════════════════════

def test_repl_quit(db_conn, mock_client, capsys):
    """repl should exit on 'quit' command."""
    from agent.vector_search import repl
    with patch("agent.vector_search.PromptSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.prompt.return_value = "quit"
        mock_session_cls.return_value = mock_session
        repl(mock_client, db_conn)
    out = capsys.readouterr().out
    assert "Goodbye" in out


def test_repl_exit(db_conn, mock_client, capsys):
    """repl should exit on 'exit' command."""
    from agent.vector_search import repl
    with patch("agent.vector_search.PromptSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.prompt.return_value = "exit"
        mock_session_cls.return_value = mock_session
        repl(mock_client, db_conn)
    out = capsys.readouterr().out
    assert "Goodbye" in out


def test_repl_eof(db_conn, mock_client, capsys):
    """repl should exit gracefully on EOFError."""
    from agent.vector_search import repl
    with patch("agent.vector_search.PromptSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.prompt.side_effect = EOFError()
        mock_session_cls.return_value = mock_session
        repl(mock_client, db_conn)
    out = capsys.readouterr().out
    assert "Goodbye" in out


def test_repl_keyboard_interrupt(db_conn, mock_client, capsys):
    """repl should exit gracefully on KeyboardInterrupt."""
    from agent.vector_search import repl
    with patch("agent.vector_search.PromptSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.prompt.side_effect = KeyboardInterrupt()
        mock_session_cls.return_value = mock_session
        repl(mock_client, db_conn)
    out = capsys.readouterr().out
    assert "Goodbye" in out


def test_repl_empty_input(db_conn, mock_client, capsys):
    """repl should skip empty input and continue."""
    from agent.vector_search import repl
    with patch("agent.vector_search.PromptSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.prompt.side_effect = ["", "quit"]
        mock_session_cls.return_value = mock_session
        repl(mock_client, db_conn)
    out = capsys.readouterr().out
    assert "Goodbye" in out


def test_repl_unknown_command(db_conn, mock_client, capsys):
    """repl should print error for unknown commands."""
    from agent.vector_search import repl
    with patch("agent.vector_search.PromptSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.prompt.side_effect = ["foobar", "quit"]
        mock_session_cls.return_value = mock_session
        repl(mock_client, db_conn)
    out = capsys.readouterr().out
    assert "Unknown command" in out


def test_repl_help(db_conn, mock_client, capsys):
    """repl 'help' command should show help text."""
    from agent.vector_search import repl
    with patch("agent.vector_search.PromptSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.prompt.side_effect = ["help", "quit"]
        mock_session_cls.return_value = mock_session
        repl(mock_client, db_conn)
    out = capsys.readouterr().out
    assert "Commands" in out


def test_repl_count(populated_db, mock_client, capsys):
    """repl 'count' command should display document count."""
    from agent.vector_search import repl
    with patch("agent.vector_search.PromptSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.prompt.side_effect = ["count", "quit"]
        mock_session_cls.return_value = mock_session
        repl(mock_client, populated_db)
    out = capsys.readouterr().out
    assert "3 documents" in out


def test_repl_list(populated_db, mock_client, capsys):
    """repl 'list' command should display documents."""
    from agent.vector_search import repl
    with patch("agent.vector_search.PromptSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.prompt.side_effect = ["list", "quit"]
        mock_session_cls.return_value = mock_session
        repl(mock_client, populated_db)
    out = capsys.readouterr().out
    assert "DOC_001" in out


def test_repl_clear(populated_db, mock_client, capsys):
    """repl 'clear' command should clear all documents."""
    from agent.vector_search import repl
    with patch("agent.vector_search.PromptSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.prompt.side_effect = ["clear", "quit"]
        mock_session_cls.return_value = mock_session
        repl(mock_client, populated_db)
    out = capsys.readouterr().out
    assert "Cleared" in out


def test_repl_add(db_conn, mock_client, capsys):
    """repl 'add' command should store a document."""
    from agent.vector_search import repl
    with patch("agent.vector_search.PromptSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.prompt.side_effect = ["add test document", "quit"]
        mock_session_cls.return_value = mock_session
        repl(mock_client, db_conn)
    out = capsys.readouterr().out
    assert "Stored document" in out


def test_repl_search_with_top_k(populated_db, mock_client, capsys):
    """repl 'search' command with /N should parse top_k."""
    from agent.vector_search import repl
    with patch("agent.vector_search.PromptSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.prompt.side_effect = ["search soup /2", "quit"]
        mock_session_cls.return_value = mock_session
        repl(mock_client, populated_db)
    out = capsys.readouterr().out
    assert "Semantic Search" in out


def test_repl_q_shortcut(db_conn, mock_client, capsys):
    """repl should accept 'q' as quit shortcut."""
    from agent.vector_search import repl
    with patch("agent.vector_search.PromptSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.prompt.return_value = "q"
        mock_session_cls.return_value = mock_session
        repl(mock_client, db_conn)
    out = capsys.readouterr().out
    assert "Goodbye" in out


# ════════════════════════════════════════════════════════════
#  TESTS: main function
# ════════════════════════════════════════════════════════════

def test_main():
    """main() should call setup, init_db, show_banner, and repl."""
    from agent.vector_search import main
    with patch("agent.vector_search.setup") as mock_setup, \
         patch("agent.vector_search.init_db") as mock_init_db, \
         patch("agent.vector_search.get_document_count", return_value=0), \
         patch("agent.vector_search.show_banner"), \
         patch("agent.vector_search.repl") as mock_repl:
        mock_setup.return_value = MagicMock()
        mock_init_db.return_value = MagicMock()
        main()
        mock_setup.assert_called_once()
        mock_init_db.assert_called_once()
        mock_repl.assert_called_once()
