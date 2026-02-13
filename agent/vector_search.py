"""Semantic search REPL using OpenAI embeddings + FAISS + SQLite.

Store and retrieve knowledge base documents by semantic similarity.
Supports JSONL knowledge files with category and image_ids metadata.

Usage:
    python agent/vector_search.py
"""

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import faiss
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML


# ════════════════════════════════════════════════════════════
#  CONSTANTS
# ════════════════════════════════════════════════════════════

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
DB_PATH = Path(__file__).parent / "vector_store.db"


# ════════════════════════════════════════════════════════════
#  SQLITE LAYER
# ════════════════════════════════════════════════════════════

def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Open (or create) the database and ensure the schema exists."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            text        TEXT NOT NULL,
            embedding   BLOB NOT NULL,
            created_at  TEXT NOT NULL,
            doc_id      TEXT,
            category    TEXT,
            title       TEXT,
            image_ids   TEXT
        )
    """)
    conn.commit()

    # Migrate: add metadata columns if they don't exist (for old DBs)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(documents)").fetchall()}
    migrations = [
        ("doc_id", "TEXT"),
        ("category", "TEXT"),
        ("title", "TEXT"),
        ("image_ids", "TEXT"),
    ]
    for col, typ in migrations:
        if col not in existing:
            conn.execute(f"ALTER TABLE documents ADD COLUMN {col} {typ}")
    conn.commit()
    return conn


def store_document(
    conn: sqlite3.Connection,
    text: str,
    embedding: np.ndarray,
    metadata: dict | None = None,
) -> int:
    """Insert a document + embedding + optional metadata. Returns the new row ID."""
    meta = metadata or {}
    image_ids_val = meta.get("image_ids")
    if isinstance(image_ids_val, list):
        image_ids_str = json.dumps(image_ids_val, ensure_ascii=False)
    else:
        image_ids_str = image_ids_val
    cur = conn.execute(
        """INSERT INTO documents (text, embedding, created_at, doc_id, category, title, image_ids)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            text,
            embedding.tobytes(),
            datetime.now(timezone.utc).isoformat(),
            meta.get("doc_id"),
            meta.get("category"),
            meta.get("title"),
            image_ids_str,
        ),
    )
    conn.commit()
    return cur.lastrowid


def load_all_embeddings(conn: sqlite3.Connection) -> tuple[list[int], np.ndarray | None]:
    """Load all (id, embedding) pairs. Returns ([], None) if empty."""
    rows = conn.execute("SELECT id, embedding FROM documents ORDER BY id").fetchall()
    if not rows:
        return [], None
    ids = [r[0] for r in rows]
    vectors = np.array(
        [np.frombuffer(r[1], dtype=np.float32) for r in rows],
        dtype=np.float32,
    )
    return ids, vectors


def load_filtered_embeddings(
    conn: sqlite3.Connection, filters: dict
) -> tuple[list[int], np.ndarray | None]:
    """Load embeddings matching metadata filters. Returns ([], None) if empty."""
    where_clauses, params = _build_filter_clauses(filters)
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    rows = conn.execute(
        f"SELECT id, embedding FROM documents WHERE {where_sql} ORDER BY id",
        params,
    ).fetchall()
    if not rows:
        return [], None
    ids = [r[0] for r in rows]
    vectors = np.array(
        [np.frombuffer(r[1], dtype=np.float32) for r in rows],
        dtype=np.float32,
    )
    return ids, vectors


def _build_filter_clauses(filters: dict) -> tuple[list[str], list]:
    """Build SQL WHERE clauses from a filters dict."""
    where_clauses = []
    params = []
    for key, value in filters.items():
        if key == "category":
            where_clauses.append("category = ?")
            params.append(value)
        elif key == "exclude_category":
            where_clauses.append("category <> ?")
            params.append(value)
        elif key in ("doc_id", "title"):
            where_clauses.append(f"{key} LIKE ?")
            params.append(f"%{value}%")
    return where_clauses, params


def _parse_image_ids(raw: str | None) -> list[str]:
    """Parse image_ids from JSON string or return empty list."""
    if not raw:
        return []
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _row_to_dict(r: tuple) -> dict:
    """Convert a SELECT row (id, text, created_at, doc_id, category, title, image_ids) to dict."""
    return {
        "id": r[0],
        "text": r[1],
        "created_at": r[2],
        "doc_id": r[3],
        "category": r[4],
        "title": r[5],
        "image_ids": _parse_image_ids(r[6]),
    }


_SELECT_COLS = "id, text, created_at, doc_id, category, title, image_ids"


def substring_search(
    conn: sqlite3.Connection,
    query: str,
    filters: dict | None = None,
    limit: int = 5,
) -> list[dict]:
    """Search documents by substring match across text, title, category, doc_id."""
    like_param = f"%{query}%"
    text_match = "(text LIKE ? OR title LIKE ? OR category LIKE ? OR doc_id LIKE ?)"
    params: list = [like_param] * 4

    if filters:
        filter_clauses, filter_params = _build_filter_clauses(filters)
        if filter_clauses:
            where_sql = f"{text_match} AND " + " AND ".join(filter_clauses)
            params.extend(filter_params)
        else:
            where_sql = text_match
    else:
        where_sql = text_match

    rows = conn.execute(
        f"SELECT {_SELECT_COLS} FROM documents WHERE {where_sql} ORDER BY id LIMIT ?",
        params + [limit],
    ).fetchall()

    return [_row_to_dict(r) for r in rows]


def get_documents_by_ids(conn: sqlite3.Connection, doc_ids: list[int]) -> list[dict]:
    """Fetch documents by ID, returned in the order of doc_ids."""
    if not doc_ids:
        return []
    placeholders = ",".join("?" for _ in doc_ids)
    rows = conn.execute(
        f"SELECT {_SELECT_COLS} FROM documents WHERE id IN ({placeholders})",
        doc_ids,
    ).fetchall()
    by_id = {r[0]: _row_to_dict(r) for r in rows}
    return [by_id[did] for did in doc_ids if did in by_id]


def get_document_count(conn: sqlite3.Connection) -> int:
    """Return the total number of documents in the store."""
    return conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]


def get_all_documents(conn: sqlite3.Connection) -> list[dict]:
    """Fetch all documents ordered by ID."""
    rows = conn.execute(
        f"SELECT {_SELECT_COLS} FROM documents ORDER BY id"
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def clear_all(conn: sqlite3.Connection) -> None:
    """Delete all documents from the store."""
    conn.execute("DELETE FROM documents")
    conn.commit()


# ════════════════════════════════════════════════════════════
#  NATURAL LANGUAGE CONVERSION
# ════════════════════════════════════════════════════════════

def row_to_natural_language(meta: dict) -> str:
    """Convert a knowledge base record to natural language for embedding.

    Combines title + content + category into a single text for embedding.
    """
    parts = []
    if meta.get("title"):
        parts.append(meta["title"])
    if meta.get("content"):
        parts.append(meta["content"])
    if meta.get("category"):
        parts.append(f"(หมวด: {meta['category']})")
    return " ".join(parts)


# ════════════════════════════════════════════════════════════
#  EMBEDDING LAYER
# ════════════════════════════════════════════════════════════

def get_embedding(client: OpenAI, text: str) -> np.ndarray:
    """Embed a single text using OpenAI. Returns float32 array (1536,)."""
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return np.array(response.data[0].embedding, dtype=np.float32)


def get_embeddings_batch(client: OpenAI, texts: list[str]) -> list[np.ndarray]:
    """Embed multiple texts in one API call. Returns list of float32 arrays."""
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [
        np.array(item.embedding, dtype=np.float32)
        for item in sorted(response.data, key=lambda x: x.index)
    ]


# ════════════════════════════════════════════════════════════
#  FAISS LAYER
# ════════════════════════════════════════════════════════════

def build_faiss_index(embeddings: np.ndarray) -> faiss.IndexFlatIP:
    """Build a flat inner-product FAISS index from an (n, 1536) matrix."""
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(EMBEDDING_DIM)
    index.add(embeddings)
    return index


# ════════════════════════════════════════════════════════════
#  PROGRAMMATIC API  (used by MCP tool and other callers)
# ════════════════════════════════════════════════════════════

def get_connection() -> sqlite3.Connection:
    """Open a read-only connection to the vector store database.

    For external callers (e.g. MCP tools) that don't need schema migration.
    Raises FileNotFoundError if the DB doesn't exist yet.
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Vector store DB not found at {DB_PATH}. "
            "Run 'python agent/load_knowledge.py' to load data first."
        )
    return sqlite3.connect(str(DB_PATH))


def hybrid_search(
    client: OpenAI,
    conn: sqlite3.Connection,
    query: str,
    top_k: int = 5,
    filters: dict | None = None,
) -> list[dict]:
    """Run both vector and substring search, merge and deduplicate results.

    Each result dict includes:
      - 'score': float for vector hits, None for substring-only
      - 'source': 'vector', 'substring', or 'both'
      - 'image_ids': list of related image IDs
    """
    merged: dict[int, dict] = {}

    # ── Vector search ────────────────────────────────────
    if filters:
        ids, embeddings = load_filtered_embeddings(conn, filters)
    else:
        ids, embeddings = load_all_embeddings(conn)

    if embeddings is not None and len(ids) > 0:
        index = build_faiss_index(embeddings)
        query_vec = get_embedding(client, query).reshape(1, -1)
        faiss.normalize_L2(query_vec)

        k = min(top_k, len(ids))
        scores, indices = index.search(query_vec, k)

        matched_ids = [ids[i] for i in indices[0] if i >= 0]
        matched_scores = [float(scores[0][j]) for j, i in enumerate(indices[0]) if i >= 0]
        vector_docs = get_documents_by_ids(conn, matched_ids)

        for doc, score in zip(vector_docs, matched_scores):
            doc["score"] = score
            doc["source"] = "vector"
            merged[doc["id"]] = doc

    # ── Substring search ─────────────────────────────────
    substr_docs = substring_search(conn, query, filters=filters, limit=top_k)
    for doc in substr_docs:
        if doc["id"] in merged:
            merged[doc["id"]]["source"] = "both"
        else:
            doc["score"] = None
            doc["source"] = "substring"
            merged[doc["id"]] = doc

    # Sort: vector hits first (by score desc), then substring-only
    return sorted(
        merged.values(),
        key=lambda d: (d["score"] is not None, d["score"] or 0),
        reverse=True,
    )


# ════════════════════════════════════════════════════════════
#  SETUP
# ════════════════════════════════════════════════════════════

def setup() -> OpenAI:
    """Load env, validate API key, return OpenAI client."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set. Add it to .env or environment.", file=sys.stderr)
        sys.exit(1)
    return OpenAI(api_key=api_key)


# ════════════════════════════════════════════════════════════
#  KNOWLEDGE FILE PARSER
# ════════════════════════════════════════════════════════════

def parse_knowledge_file(filepath: Path) -> list[dict] | None:
    """Parse a JSONL knowledge file. Returns list of record dicts, or None if not JSONL.

    Each line should be a JSON object with at least 'id' and 'content' fields.
    Also handles a single JSON object (e.g. image_mapping.txt).
    """
    content = filepath.read_text(encoding="utf-8")
    stripped = content.strip()

    # Try as single JSON object first (e.g. image_mapping.txt)
    if stripped.startswith("{") and not stripped.startswith('{"id"'):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and not data.get("id"):
                # It's a mapping dict (like image_mapping) — convert entries to records
                records = []
                for key, value in data.items():
                    if isinstance(value, dict) and value.get("description"):
                        records.append({
                            "id": key,
                            "category": "image_description",
                            "title": key,
                            "content": value["description"],
                            "image_ids": [key],
                        })
                return records if records else None
        except json.JSONDecodeError:
            pass

    # Try as JSONL (one JSON object per line)
    records = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            if isinstance(record, dict) and "id" in record and "content" in record:
                records.append(record)
        except json.JSONDecodeError:
            continue

    return records if records else None


# ════════════════════════════════════════════════════════════
#  COMMAND HANDLERS
# ════════════════════════════════════════════════════════════

def cmd_add(client: OpenAI, conn: sqlite3.Connection, text: str) -> None:
    """Embed text and store it in SQLite."""
    if not text:
        print("  Usage: add <text>")
        return

    try:
        embedding = get_embedding(client, text)
    except Exception as e:
        print(f"  Error: Failed to generate embedding: {e}")
        return

    doc_id = store_document(conn, text, embedding)
    print(f"  Stored document {doc_id} ({len(text)} chars)")


def cmd_clear(conn: sqlite3.Connection) -> None:
    """Delete all documents from the vector store."""
    clear_all(conn)
    print("  Cleared all documents from the store.")


def parse_filters(rest: str) -> tuple[str, dict]:
    """Extract filter flags from the query string.

    Supported filters:
      --category recipe
    """
    filters = {}
    filter_pattern = re.compile(
        r"--(category)\s+(\S+)"
    )

    query = rest
    for match in filter_pattern.finditer(rest):
        key = match.group(1)
        filters[key] = match.group(2)
        query = query.replace(match.group(0), "")

    return query.strip(), filters


def _print_doc(doc: dict, rank: int, score: float | None = None, overlap: bool = False) -> None:
    """Print a single search result document."""
    overlap_mark = " ★" if overlap else ""
    if score is not None:
        print(f"\n  [{rank}] (score: {score:.4f})  ID: {doc['id']}{overlap_mark}")
    else:
        print(f"\n  [{rank}] ID: {doc['id']}{overlap_mark}")

    if doc.get("doc_id"):
        print(f"      doc_id:   {doc['doc_id']}")
        print(f"      Category: {doc.get('category', '-')}")
        print(f"      Title:    {doc.get('title', '-')}")
        image_ids = doc.get("image_ids", [])
        if image_ids:
            print(f"      Images:   {', '.join(image_ids)}")
        text_preview = doc["text"][:200]
        if len(doc["text"]) > 200:
            text_preview += "..."
        print(f"      Content:  {text_preview}")
    else:
        text_preview = doc["text"][:200]
        if len(doc["text"]) > 200:
            text_preview += "..."
        print(f"      Added: {doc['created_at']}")
        print(f"      {text_preview}")


def cmd_search(client: OpenAI, conn: sqlite3.Connection, query: str, top_k: int = 5) -> None:
    """Hybrid search: run both vector (semantic) and substring (text-match) search, display both."""
    if not query:
        print("  Usage: search <query>  or  search <query> /N")
        print("  Filters: --category <category>")
        return

    # Parse filters from query
    clean_query, filters = parse_filters(query)
    if not clean_query:
        print("  Error: Query text is empty after parsing filters.")
        return

    print(f'\n  Hybrid search: "{clean_query}"')
    if filters:
        print(f"  Filters: {filters}")

    # ── Vector (Semantic) Search ──────────────────────────
    vector_ids: list[int] = []
    if filters:
        ids, embeddings = load_filtered_embeddings(conn, filters)
    else:
        ids, embeddings = load_all_embeddings(conn)

    if embeddings is not None:
        index = build_faiss_index(embeddings)
        try:
            query_vec = get_embedding(client, clean_query)
        except Exception as e:
            print(f"  Error: Failed to generate embedding: {e}")
            return

        query_vec = query_vec.reshape(1, -1)
        faiss.normalize_L2(query_vec)

        k = min(top_k, len(ids))
        scores, indices = index.search(query_vec, k)

        matched_ids = [ids[i] for i in indices[0] if i >= 0]
        matched_scores = [float(scores[0][j]) for j, i in enumerate(indices[0]) if i >= 0]
        vector_docs = get_documents_by_ids(conn, matched_ids)
        vector_ids = [d["id"] for d in vector_docs]

        print(f"\n  {'═' * 20} Semantic Search (ความหมายใกล้เคียง) {'═' * 20}")
        if vector_docs:
            for rank, (doc, score) in enumerate(zip(vector_docs, matched_scores), 1):
                _print_doc(doc, rank, score=score)
        else:
            print("\n  No semantic results found.")
    else:
        print(f"\n  {'═' * 20} Semantic Search (ความหมายใกล้เคียง) {'═' * 20}")
        print("\n  No documents in the store yet.")

    # ── Substring (Text-Match) Search ─────────────────────
    vector_id_set = set(vector_ids)
    substr_docs = substring_search(conn, clean_query, filters=filters, limit=top_k)

    print(f"\n  {'═' * 20} Substring Search (ตรงตัวอักษร) {'═' * 20}")
    if substr_docs:
        for rank, doc in enumerate(substr_docs, 1):
            overlap = doc["id"] in vector_id_set
            _print_doc(doc, rank, overlap=overlap)
        if any(d["id"] in vector_id_set for d in substr_docs):
            print("\n  ★ = also appeared in semantic results")
    else:
        print("\n  No substring matches found.")
    print()


def cmd_list(conn: sqlite3.Connection) -> None:
    """List all stored documents."""
    docs = get_all_documents(conn)
    if not docs:
        print("  No documents in the store yet.")
        return

    print(f"\n  Documents ({len(docs)} total):")
    for doc in docs:
        if doc.get("doc_id"):
            images = ", ".join(doc.get("image_ids", [])) if doc.get("image_ids") else "-"
            print(f"    [{doc['id']}] {doc['doc_id']} | {doc.get('category', '-')} | {doc.get('title', '-')[:40]} | img: {images}")
        else:
            date = doc["created_at"][:10]
            text_preview = doc["text"][:80]
            if len(doc["text"]) > 80:
                text_preview += "..."
            print(f"    [{doc['id']}] {text_preview} ({date})")
    print()


def cmd_load(client: OpenAI, conn: sqlite3.Connection, filepath: str) -> None:
    """Load a file into the vector store.

    For JSONL knowledge files:
      - Parses category, title, content, image_ids
      - Embeds title + content for semantic search

    For JSON mapping files (e.g. image_mapping.txt):
      - Converts entries to searchable documents

    For plain text files:
      - One line = one document
    """
    if not filepath:
        print("  Usage: load <filepath>")
        return

    path = Path(filepath)
    if not path.is_file():
        print(f"  Error: File not found: {filepath}")
        return

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  Error: Cannot read file: {e}")
        return

    # Try parsing as knowledge file (JSONL or JSON mapping)
    records = parse_knowledge_file(path)
    if records:
        _load_knowledge(client, conn, records, path.name)
    else:
        _load_plain_text(client, conn, content, path.name)


def _load_knowledge(
    client: OpenAI, conn: sqlite3.Connection, records: list[dict], filename: str
) -> None:
    """Load knowledge base records: convert to NL, embed, store with metadata."""
    print(f"  Detected knowledge file: {filename}")
    print(f"  Found {len(records)} records to import")

    nl_texts = [row_to_natural_language(r) for r in records]

    # Show a sample
    print(f"\n  Sample (record 1):")
    print(f"    \"{nl_texts[0][:150]}...\"\n")

    # Batch embed
    BATCH_SIZE = 100
    stored = 0
    for i in range(0, len(nl_texts), BATCH_SIZE):
        batch_texts = nl_texts[i:i + BATCH_SIZE]
        batch_records = records[i:i + BATCH_SIZE]
        try:
            embeddings = get_embeddings_batch(client, batch_texts)
        except Exception as e:
            print(f"  Error at batch {i // BATCH_SIZE + 1}: {e}")
            break

        for text, emb, record in zip(batch_texts, embeddings, batch_records):
            store_document(conn, text, emb, metadata={
                "doc_id": record.get("id"),
                "category": record.get("category"),
                "title": record.get("title"),
                "image_ids": record.get("image_ids", []),
            })
            stored += 1

        print(f"  Imported {stored}/{len(records)}...")

    print(f"  Done! {stored} records imported from {filename}")
    print(f"  Metadata: doc_id, category, title, image_ids")
    print(f"  Use '--category <name>' flag with search to filter")


def _load_plain_text(
    client: OpenAI, conn: sqlite3.Connection, content: str, filename: str
) -> None:
    """Load a plain text file (one line = one document)."""
    lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if all(c in "=-+|# \t─━═╔╗╚╝║╠╣╦╩" for c in stripped):
            continue
        lines.append(stripped)

    if not lines:
        print("  No content lines found in file.")
        return

    print(f"  Found {len(lines)} lines to import from {filename}")

    BATCH_SIZE = 100
    stored = 0
    for i in range(0, len(lines), BATCH_SIZE):
        batch = lines[i:i + BATCH_SIZE]
        try:
            embeddings = get_embeddings_batch(client, batch)
        except Exception as e:
            print(f"  Error at batch {i // BATCH_SIZE + 1}: {e}")
            break

        for text, emb in zip(batch, embeddings):
            store_document(conn, text, emb)
            stored += 1

        print(f"  Imported {stored}/{len(lines)}...")

    print(f"  Done! {stored} documents imported from {filename}")


def cmd_count(conn: sqlite3.Connection) -> None:
    """Show document count."""
    count = get_document_count(conn)
    print(f"  {count} document{'s' if count != 1 else ''} in store")


def show_help() -> None:
    """Print available commands."""
    print("""
  Commands:
    add <text>         Add a document to the store
    load <filepath>    Import a file (auto-detects JSONL knowledge vs plain text)
    search <query>     Hybrid search: semantic + substring (top 5)
    search <query> /N  Search with custom top-k (e.g. /3)
    list               List all stored documents
    count              Show document count
    clear              Delete all documents
    help               Show this help message
    quit               Exit

  Hybrid Search:
    Every search runs BOTH methods and shows two result sections:
      1. Semantic Search  — finds documents with similar meaning (via embeddings)
      2. Substring Search — finds documents containing the exact query text
    Results appearing in both sections are marked with ★

  Search Filters (append to search query):
    --category recipe  Filter by category

  Example:
    search ราคาผงเครื่องเทศ
    search สูตรน้ำซุป --category recipe /3
    search IMG_PROD_001
""")


# ════════════════════════════════════════════════════════════
#  BANNER
# ════════════════════════════════════════════════════════════

def show_banner(doc_count: int) -> None:
    """Print the startup banner."""
    db_display = DB_PATH.name
    print()
    print("  +==================================================+")
    print("  |  Knowledge Search -- Semantic Search with FAISS   |")
    print(f"  |  Model: {EMBEDDING_MODEL:<41s}|")
    print(f"  |  DB: {db_display:<44s}|")
    print(f"  |  Documents: {doc_count:<37d}|")
    print("  +==================================================+")
    print()
    print("  Type 'help' for commands, 'quit' to exit.")
    print()


# ════════════════════════════════════════════════════════════
#  REPL
# ════════════════════════════════════════════════════════════

def repl(client: OpenAI, conn: sqlite3.Connection) -> None:
    """Interactive REPL loop with autocomplete and history."""
    completer = WordCompleter(
        ["add", "load", "search", "list", "count", "clear", "help", "quit", "exit"],
        ignore_case=True,
    )
    session: PromptSession = PromptSession(
        completer=completer,
        complete_while_typing=False,
    )

    while True:
        try:
            user_input = session.prompt(
                HTML("<ansicyan><b>vector</b></ansicyan><ansiwhite>&gt; </ansiwhite>")
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye!")
            return

        if not user_input:
            continue

        # Parse command and arguments
        parts = user_input.split(maxsplit=1)
        command = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""

        if command in ("quit", "exit", "q"):
            print("  Goodbye!")
            return
        elif command == "help":
            show_help()
        elif command == "count":
            cmd_count(conn)
        elif command == "list":
            cmd_list(conn)
        elif command == "clear":
            cmd_clear(conn)
        elif command == "add":
            cmd_add(client, conn, rest.strip())
        elif command == "load":
            cmd_load(client, conn, rest.strip())
        elif command == "search":
            # Parse optional /N at the end for top-k
            top_k = 5
            match = re.search(r"\s+/(\d+)\s*$", rest)
            if match:
                top_k = int(match.group(1))
                rest = rest[:match.start()]
            cmd_search(client, conn, rest.strip(), top_k)
        else:
            print(f"  Unknown command: {command}")
            print("  Type 'help' for available commands.")


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════

def main() -> None:
    client = setup()
    conn = init_db()

    doc_count = get_document_count(conn)
    show_banner(doc_count)

    repl(client, conn)


if __name__ == "__main__":
    main()
