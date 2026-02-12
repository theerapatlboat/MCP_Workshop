"""Hybrid search tool — semantic + substring search with LLM refinement."""

import json
import sys
from pathlib import Path

# Add project root to sys.path so we can import from agent/
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp.server.fastmcp import FastMCP
from config import openai_client
from agent.vector_search import get_connection, hybrid_search as _hybrid_search


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def hybrid_search(
        query: str,
        top_k: int = 5,
        min_price: float | None = None,
        max_price: float | None = None,
        color: str | None = None,
        model: str | None = None,
        min_screen: float | None = None,
        max_screen: float | None = None,
        min_stock: int | None = None,
    ) -> dict:
        """
        ค้นหาสินค้าแบบ hybrid (semantic + substring) พร้อม LLM refinement.

        ระบบจะค้นหา 2 แบบพร้อมกัน:
        1. Semantic Search — ค้นหาตามความหมาย (เช่น "มือถือจอใหญ่ราคาถูก")
        2. Substring Search — ค้นหาตรงตัวอักษร (เช่น SKU "IPH-16PM", ชื่อ "iPhone")

        จากนั้นใช้ LLM กรองผลลัพธ์ที่ไม่เกี่ยวข้องออก (refinement) เพื่อความแม่นยำ

        Args:
            query: คำค้นหา (ภาษาไทยหรืออังกฤษ)
            top_k: จำนวนผลลัพธ์สูงสุดต่อแบบค้นหา (default: 5)
            min_price: ราคาขั้นต่ำ (บาท)
            max_price: ราคาสูงสุด (บาท)
            color: สีสินค้า (partial match)
            model: รุ่นสินค้า (partial match)
            min_screen: ขนาดหน้าจอขั้นต่ำ (นิ้ว)
            max_screen: ขนาดหน้าจอสูงสุด (นิ้ว)
            min_stock: จำนวนคงเหลือขั้นต่ำ

        Returns:
            Refined search results with product details
        """
        # Build filters dict from optional params
        filters: dict = {}
        if min_price is not None:
            filters["min_price"] = min_price
        if max_price is not None:
            filters["max_price"] = max_price
        if color is not None:
            filters["color"] = color
        if model is not None:
            filters["model"] = model
        if min_screen is not None:
            filters["min_screen"] = min_screen
        if max_screen is not None:
            filters["max_screen"] = max_screen
        if min_stock is not None:
            filters["min_stock"] = min_stock

        # ── Run hybrid search ────────────────────────────
        try:
            conn = get_connection()
        except FileNotFoundError as e:
            return {"success": False, "error": str(e)}

        try:
            candidates = _hybrid_search(
                client=openai_client,
                conn=conn,
                query=query,
                top_k=top_k,
                filters=filters or None,
            )
        except Exception as e:
            return {"success": False, "error": f"Search failed: {e}"}
        finally:
            conn.close()

        if not candidates:
            return {
                "success": True,
                "query": query,
                "filters": filters or None,
                "total_candidates": 0,
                "refined_count": 0,
                "results": [],
            }

        # ── LLM Refinement — remove noise ────────────────
        refined = _llm_refine(query, candidates)

        return {
            "success": True,
            "query": query,
            "filters": filters or None,
            "total_candidates": len(candidates),
            "refined_count": len(refined),
            "results": refined,
        }


def _format_candidate(doc: dict) -> str:
    """Format a single candidate for the LLM refinement prompt."""
    price_str = f"{int(doc['price']):,}" if doc.get("price") else "N/A"
    return (
        f"ID: {doc['id']} | "
        f"{doc.get('name', 'N/A')} | "
        f"สี{doc.get('color', 'N/A')} | "
        f"ราคา {price_str} บาท | "
        f"คงเหลือ {doc.get('stock', 'N/A')} | "
        f"จอ {doc.get('screen_size', 'N/A')} นิ้ว | "
        f"SKU: {doc.get('sku', 'N/A')} | "
        f"source: {doc.get('source', 'unknown')}"
    )


def _llm_refine(query: str, candidates: list[dict]) -> list[dict]:
    """Use LLM to filter out irrelevant candidates.

    Sends the query + candidate list to GPT-4o-mini and asks it to
    return only the IDs of results that are truly relevant.
    Falls back to returning all candidates if LLM call fails.
    """
    candidate_lines = "\n".join(
        _format_candidate(doc) for doc in candidates
    )

    system_prompt = (
        "You are a search result refinement assistant for a phone store.\n"
        "Given the user's search query and a list of product candidates,\n"
        "determine which products are RELEVANT to the query.\n"
        "Remove products that are clearly NOT what the user is looking for.\n\n"
        "Rules:\n"
        "- If the user asks for a specific brand, keep only that brand\n"
        "- If the user asks for a price range, keep only products in that range\n"
        "- If the user asks for a specific color, keep only that color\n"
        "- If the query is general (e.g. 'มือถือจอใหญ่'), keep products that match the intent\n"
        "- When in doubt, KEEP the result (prefer recall over precision)\n\n"
        "Respond with ONLY a JSON array of relevant product IDs.\n"
        'Example: [1, 3, 7]\n'
        "No other text."
    )

    user_prompt = (
        f"Query: {query}\n\n"
        f"Candidates:\n{candidate_lines}"
    )

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=200,
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        relevant_ids = set(json.loads(raw))
    except Exception:
        # Fallback: return all candidates if LLM fails
        return _clean_candidates(candidates)

    # Filter to only relevant IDs, preserve original order
    refined = [doc for doc in candidates if doc["id"] in relevant_ids]
    return _clean_candidates(refined) if refined else _clean_candidates(candidates)


def _parse_text_fallback(text: str) -> dict:
    """Try to extract metadata from the natural language text field.

    Handles two formats:
      NL:  "iPhone 16 Pro Max สีดำไทเทเนียม หน้าจอ 6.9 นิ้ว ราคา 52,900 บาท มีสินค้า 15 เครื่อง (SKU: IPH-16PM-BLK-256)"
      Pipe: "001|iPhone 16 Pro Max|IPH-16PM-BLK-256|52900|15|ดำไทเทเนียม|iPhone 16 Pro Max|6.9"
    """
    import re

    # Try pipe-delimited format first (old data)
    parts = text.split("|")
    if len(parts) == 8:
        try:
            return {
                "name": parts[1].strip(),
                "sku": parts[2].strip(),
                "price": float(parts[3].strip()),
                "stock": int(parts[4].strip()),
                "color": parts[5].strip(),
                "model": parts[6].strip(),
                "screen_size": float(parts[7].strip()),
            }
        except (ValueError, IndexError):
            pass

    # Try natural language format
    meta: dict = {}
    sku_match = re.search(r"\(SKU:\s*([^)]+)\)", text)
    if sku_match:
        meta["sku"] = sku_match.group(1).strip()

    price_match = re.search(r"ราคา\s+([\d,]+)\s*บาท", text)
    if price_match:
        meta["price"] = float(price_match.group(1).replace(",", ""))

    stock_match = re.search(r"มีสินค้า\s+(\d+)\s*เครื่อง", text)
    if stock_match:
        meta["stock"] = int(stock_match.group(1))

    screen_match = re.search(r"หน้าจอ\s+([\d.]+)\s*นิ้ว", text)
    if screen_match:
        meta["screen_size"] = float(screen_match.group(1))

    color_match = re.search(r"สี(\S+)", text)
    if color_match:
        meta["color"] = color_match.group(1)

    # Name = everything before "สี"
    name_match = re.match(r"^(.+?)\s+สี", text)
    if name_match:
        meta["name"] = name_match.group(1).strip()

    return meta


def _clean_candidates(candidates: list[dict]) -> list[dict]:
    """Remove internal fields and ensure metadata is present.

    If metadata columns are null (old data), falls back to parsing the text field.
    """
    clean = []
    for doc in candidates:
        # If metadata is missing, try to parse from text field
        if not doc.get("name") and doc.get("text"):
            fallback = _parse_text_fallback(doc["text"])
            for key in ("name", "sku", "price", "stock", "color", "model", "screen_size"):
                if not doc.get(key) and key in fallback:
                    doc[key] = fallback[key]

        price_str = f"{int(doc['price']):,}" if doc.get("price") else None
        clean.append({
            "id": doc["id"],
            "name": doc.get("name"),
            "sku": doc.get("sku"),
            "price": doc.get("price"),
            "price_formatted": f"{price_str} บาท" if price_str else None,
            "stock": doc.get("stock"),
            "color": doc.get("color"),
            "model": doc.get("model"),
            "screen_size": doc.get("screen_size"),
            "score": doc.get("score"),
            "source": doc.get("source"),
        })
    return clean
