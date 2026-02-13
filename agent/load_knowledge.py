"""One-shot script to load knowledge base into vector store.

Usage:
    python agent/load_knowledge.py

This will:
1. Delete the old vector_store.db (phone product data)
2. Create a fresh DB with the new knowledge base schema
3. Load storage/ผงเครื่องเทศหอมรักกัน.txt (13 JSONL product knowledge records)
4. Load storage/image_mapping.txt (16 image descriptions as searchable documents)
"""

import sys
from pathlib import Path

# Add project root to path so imports work when run from any directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "agent"))

from vector_search import (
    setup,
    init_db,
    cmd_load,
    get_document_count,
    DB_PATH,
)


def main() -> None:
    client = setup()

    # Delete old DB for clean start
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"Deleted old database: {DB_PATH}")

    conn = init_db()
    print(f"Created new database: {DB_PATH}\n")

    # Load all .txt files from storage/
    storage_dir = PROJECT_ROOT / "storage"
    txt_files = sorted(storage_dir.glob("*.txt"))

    if not txt_files:
        print(f"No .txt files found in {storage_dir}")
        return

    for txt_file in txt_files:
        print(f"{'─' * 50}")
        print(f"Loading: {txt_file.name}")
        cmd_load(client, conn, str(txt_file))
        print()

    print(f"{'═' * 50}")
    print(f"Total documents in store: {get_document_count(conn)}")
    conn.close()
    print("Done!")


if __name__ == "__main__":
    main()
