"""Semantic search REPL using OpenAI embeddings + FAISS + SQLite.

Store and retrieve documents by semantic similarity.
Supports structured product files with metadata filtering.

Usage:
    python agent/vector_search.py
"""

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

# Expected header for structured product files
PRODUCT_COLUMNS = ["id", "name", "sku", "price", "stock", "color", "model", "screen_size"]


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
            name        TEXT,
            sku         TEXT,
            price       REAL,
            stock       INTEGER,
            color       TEXT,
            model       TEXT,
            screen_size REAL
        )
    """)
    conn.commit()

    # Migrate: add metadata columns if they don't exist (for old DBs)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(documents)").fetchall()}
    migrations = [
        ("name", "TEXT"),
        ("sku", "TEXT"),
        ("price", "REAL"),
        ("stock", "INTEGER"),
        ("color", "TEXT"),
        ("model", "TEXT"),
        ("screen_size", "REAL"),
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
    cur = conn.execute(
        """INSERT INTO documents (text, embedding, created_at, name, sku, price, stock, color, model, screen_size)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            text,
            embedding.tobytes(),
            datetime.now(timezone.utc).isoformat(),
            meta.get("name"),
            meta.get("sku"),
            meta.get("price"),
            meta.get("stock"),
            meta.get("color"),
            meta.get("model"),
            meta.get("screen_size"),
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
    where_clauses = []
    params = []

    for key, value in filters.items():
        if key == "min_price":
            where_clauses.append("price >= ?")
            params.append(float(value))
        elif key == "max_price":
            where_clauses.append("price <= ?")
            params.append(float(value))
        elif key == "min_screen":
            where_clauses.append("screen_size >= ?")
            params.append(float(value))
        elif key == "max_screen":
            where_clauses.append("screen_size >= ?")
            params.append(float(value))
        elif key in ("name", "color", "model", "sku"):
            where_clauses.append(f"{key} LIKE ?")
            params.append(f"%{value}%")
        elif key == "min_stock":
            where_clauses.append("stock >= ?")
            params.append(int(value))

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


def get_documents_by_ids(conn: sqlite3.Connection, doc_ids: list[int]) -> list[dict]:
    """Fetch documents by ID, returned in the order of doc_ids."""
    if not doc_ids:
        return []
    placeholders = ",".join("?" for _ in doc_ids)
    rows = conn.execute(
        f"""SELECT id, text, created_at, name, sku, price, stock, color, model, screen_size
            FROM documents WHERE id IN ({placeholders})""",
        doc_ids,
    ).fetchall()
    by_id = {
        r[0]: {
            "id": r[0], "text": r[1], "created_at": r[2],
            "name": r[3], "sku": r[4], "price": r[5],
            "stock": r[6], "color": r[7], "model": r[8], "screen_size": r[9],
        }
        for r in rows
    }
    return [by_id[did] for did in doc_ids if did in by_id]


def get_document_count(conn: sqlite3.Connection) -> int:
    """Return the total number of documents in the store."""
    return conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]


def get_all_documents(conn: sqlite3.Connection) -> list[dict]:
    """Fetch all documents ordered by ID."""
    rows = conn.execute(
        "SELECT id, text, created_at, name, sku, price, stock, color, model, screen_size FROM documents ORDER BY id"
    ).fetchall()
    return [
        {
            "id": r[0], "text": r[1], "created_at": r[2],
            "name": r[3], "sku": r[4], "price": r[5],
            "stock": r[6], "color": r[7], "model": r[8], "screen_size": r[9],
        }
        for r in rows
    ]


# ════════════════════════════════════════════════════════════
#  NATURAL LANGUAGE CONVERSION
# ════════════════════════════════════════════════════════════

def row_to_natural_language(meta: dict) -> str:
    """Convert a product metadata row to a natural language sentence for embedding.

    Example output:
      "iPhone 16 Pro Max สีดำไทเทเนียม หน้าจอ 6.9 นิ้ว ราคา 52,900 บาท มีสินค้า 15 เครื่อง (SKU: IPH-16PM-BLK-256)"
    """
    price_str = f"{int(meta['price']):,}" if meta.get("price") else "N/A"
    stock_str = str(meta.get("stock", "N/A"))
    screen_str = str(meta.get("screen_size", "N/A"))

    return (
        f"{meta.get('name', '')} สี{meta.get('color', '')} "
        f"หน้าจอ {screen_str} นิ้ว "
        f"ราคา {price_str} บาท "
        f"มีสินค้า {stock_str} เครื่อง "
        f"(SKU: {meta.get('sku', '')})"
    )


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
#  PRODUCT FILE PARSER
# ════════════════════════════════════════════════════════════

def parse_product_file(filepath: Path) -> list[dict] | None:
    """Parse a pipe-delimited product file. Returns list of metadata dicts, or None if not a product file."""
    content = filepath.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return None

    # Check if the first line is a matching header
    header = [col.strip() for col in lines[0].split("|")]
    if header != PRODUCT_COLUMNS:
        return None

    products = []
    for line in lines[1:]:
        cols = [col.strip() for col in line.split("|")]
        if len(cols) != len(PRODUCT_COLUMNS):
            continue
        try:
            products.append({
                "name": cols[1],
                "sku": cols[2],
                "price": float(cols[3]),
                "stock": int(cols[4]),
                "color": cols[5],
                "model": cols[6],
                "screen_size": float(cols[7]),
            })
        except (ValueError, IndexError):
            continue

    return products if products else None


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


def parse_filters(rest: str) -> tuple[str, dict]:
    """Extract filter flags from the query string.

    Supported filters:
      --min-price 10000  --max-price 30000
      --color สีดำ       --model Galaxy
      --min-screen 6.5   --max-screen 6.8
      --min-stock 10
    """
    filters = {}
    filter_pattern = re.compile(
        r"--(min-price|max-price|color|model|min-screen|max-screen|min-stock)\s+(\S+)"
    )

    query = rest
    for match in filter_pattern.finditer(rest):
        key = match.group(1).replace("-", "_")
        filters[key] = match.group(2)
        query = query.replace(match.group(0), "")

    return query.strip(), filters


def cmd_search(client: OpenAI, conn: sqlite3.Connection, query: str, top_k: int = 5) -> None:
    """Embed query, search FAISS, display ranked results with metadata."""
    if not query:
        print("  Usage: search <query>  or  search <query> /N")
        print("  Filters: --min-price N --max-price N --color X --model X --min-screen N --min-stock N")
        return

    # Parse filters from query
    clean_query, filters = parse_filters(query)
    if not clean_query:
        print("  Error: Query text is empty after parsing filters.")
        return

    # Load embeddings (filtered or all)
    if filters:
        ids, embeddings = load_filtered_embeddings(conn, filters)
        if embeddings is None:
            print("  No documents match the given filters.")
            return
        print(f"  Filtered to {len(ids)} documents")
    else:
        ids, embeddings = load_all_embeddings(conn)
        if embeddings is None:
            print("  No documents in the store yet. Use 'add <text>' or 'load <filepath>' first.")
            return

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
    docs = get_documents_by_ids(conn, matched_ids)

    print(f'\n  Results for: "{clean_query}"')
    if filters:
        print(f"  Filters: {filters}")
    print("  " + "=" * 58)
    for rank, (doc, score) in enumerate(zip(docs, matched_scores), 1):
        print(f"\n  [{rank}] (score: {score:.4f})  ID: {doc['id']}")

        # Show metadata if available
        if doc.get("name"):
            price_str = f"{int(doc['price']):,}" if doc.get("price") else "-"
            print(f"      Name:   {doc['name']}")
            print(f"      SKU:    {doc.get('sku', '-')}")
            print(f"      Price:  {price_str} บาท")
            print(f"      Stock:  {doc.get('stock', '-')} เครื่อง")
            print(f"      Color:  {doc.get('color', '-')}")
            print(f"      Model:  {doc.get('model', '-')}")
            print(f"      Screen: {doc.get('screen_size', '-')} นิ้ว")
        else:
            text_preview = doc["text"][:200]
            if len(doc["text"]) > 200:
                text_preview += "..."
            print(f"      Added: {doc['created_at']}")
            print(f"      {text_preview}")
    print()


def cmd_list(conn: sqlite3.Connection) -> None:
    """List all stored documents."""
    docs = get_all_documents(conn)
    if not docs:
        print("  No documents in the store yet.")
        return

    print(f"\n  Documents ({len(docs)} total):")
    for doc in docs:
        if doc.get("name"):
            price_str = f"{int(doc['price']):,}" if doc.get("price") else "-"
            print(f"    [{doc['id']}] {doc['name']} | {doc.get('color','-')} | {price_str}฿ | stock:{doc.get('stock','-')}")
        else:
            date = doc["created_at"][:10]
            text_preview = doc["text"][:80]
            if len(doc["text"]) > 80:
                text_preview += "..."
            print(f"    [{doc['id']}] {text_preview} ({date})")
    print()


def cmd_load(client: OpenAI, conn: sqlite3.Connection, filepath: str) -> None:
    """Load a file into the vector store.

    For structured product files (pipe-delimited with header):
      - Parses metadata columns for filtering
      - Converts each row to natural language before embedding

    For plain text files:
      - One line = one document (original behavior)
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

    # Try parsing as structured product file
    products = parse_product_file(path)
    if products:
        _load_products(client, conn, products, path.name)
    else:
        _load_plain_text(client, conn, content, path.name)


def _load_products(
    client: OpenAI, conn: sqlite3.Connection, products: list[dict], filename: str
) -> None:
    """Load structured product data: convert to natural language, embed, store with metadata."""
    print(f"  Detected structured product file: {filename}")
    print(f"  Found {len(products)} products to import")
    print(f"  Converting rows to natural language for embedding...")

    # Convert all products to natural language
    nl_texts = [row_to_natural_language(p) for p in products]

    # Show a sample
    print(f"\n  Sample (row 1):")
    print(f"    \"{nl_texts[0]}\"\n")

    # Batch embed
    BATCH_SIZE = 100
    stored = 0
    for i in range(0, len(nl_texts), BATCH_SIZE):
        batch_texts = nl_texts[i:i + BATCH_SIZE]
        batch_meta = products[i:i + BATCH_SIZE]
        try:
            embeddings = get_embeddings_batch(client, batch_texts)
        except Exception as e:
            print(f"  Error at batch {i // BATCH_SIZE + 1}: {e}")
            break

        for text, emb, meta in zip(batch_texts, embeddings, batch_meta):
            store_document(conn, text, emb, metadata=meta)
            stored += 1

        print(f"  Imported {stored}/{len(products)}...")

    print(f"  Done! {stored} products imported from {filename}")
    print(f"  Metadata columns stored: name, sku, price, stock, color, model, screen_size")
    print(f"  Use '--min-price', '--max-price', '--color', '--model' flags with search to filter")


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
    load <filepath>    Import a file (auto-detects structured product vs plain text)
    search <query>     Search for similar documents (top 5)
    search <query> /N  Search with custom top-k (e.g. /3)
    list               List all stored documents
    count              Show document count
    help               Show this help message
    quit               Exit

  Search Filters (append to search query):
    --min-price 10000  Minimum price
    --max-price 30000  Maximum price
    --color ดำ          Filter by color (partial match)
    --model Galaxy     Filter by model (partial match)
    --min-screen 6.5   Minimum screen size
    --max-screen 6.8   Maximum screen size
    --min-stock 10     Minimum stock

  Example:
    search มือถือจอใหญ่ --min-price 20000 --max-price 40000
    search iPhone สีดำ --min-stock 10 /3
""")


# ════════════════════════════════════════════════════════════
#  BANNER
# ════════════════════════════════════════════════════════════

def show_banner(doc_count: int) -> None:
    """Print the startup banner."""
    db_display = DB_PATH.name
    print()
    print("  +==================================================+")
    print("  |  Vector Search -- Semantic Search with FAISS      |")
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
        ["add", "load", "search", "list", "count", "help", "quit", "exit"],
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
