"""Knowledge search tool — semantic + substring search for product knowledge base."""

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
    def knowledge_search(
        query: str,
        top_k: int = 5,
        category: str | None = None,
    ) -> dict:
        """
        ค้นหาข้อมูลสินค้าและความรู้ แบบ hybrid (semantic + substring).

        ค้นหาได้ทั้ง: ข้อมูลสินค้า, สูตรอาหาร, ราคา, วิธีใช้, รีวิว, ใบรับรอง, ช่องทางขาย

        ระบบจะค้นหา 2 แบบพร้อมกัน:
        1. Semantic Search — ค้นหาตามความหมาย (เช่น "ผงเครื่องเทศทำก๋วยเตี๋ยว")
        2. Substring Search — ค้นหาตรงตัวอักษร (เช่น "raggan_001", "IMG_PROD_001")

        จากนั้นใช้ LLM กรองผลลัพธ์ที่ไม่เกี่ยวข้องออก (refinement) เพื่อความแม่นยำ

        Args:
            query: คำค้นหา (ภาษาไทยหรืออังกฤษ)
            top_k: จำนวนผลลัพธ์สูงสุดต่อแบบค้นหา (default: 5)
            category: กรองตามหมวด (product_overview, product_features, certifications,
                      recipe, recipe_ingredients, pricing, sales_channels, how_to_use,
                      customer_reviews, product_variant, image_description)

        Returns:
            Search results with content and image_ids for each result
        """
        try:
            conn = get_connection()
        except FileNotFoundError as e:
            return {"success": False, "error": str(e)}

        try:
            # If user explicitly requests a specific category, search only that
            if category is not None:
                candidates = _hybrid_search(
                    client=openai_client,
                    conn=conn,
                    query=query,
                    top_k=top_k,
                    filters={"category": category},
                )
            else:
                # Two-phase search: knowledge records first, then supplement
                # Phase 1: Search knowledge records (exclude image_description)
                knowledge_candidates = _hybrid_search(
                    client=openai_client,
                    conn=conn,
                    query=query,
                    top_k=top_k,
                    filters={"exclude_category": "image_description"},
                )

                # Phase 2: Search image_descriptions separately (top 3)
                image_candidates = _hybrid_search(
                    client=openai_client,
                    conn=conn,
                    query=query,
                    top_k=3,
                    filters={"category": "image_description"},
                )

                # Merge: knowledge first, then images (deduplicated)
                seen_ids = {doc["id"] for doc in knowledge_candidates}
                candidates = list(knowledge_candidates)
                for doc in image_candidates:
                    if doc["id"] not in seen_ids:
                        candidates.append(doc)
        except Exception as e:
            return {"success": False, "error": f"Search failed: {e}"}
        finally:
            conn.close()

        if not candidates:
            return {
                "success": True,
                "query": query,
                "filters": {"category": category} if category else None,
                "total_candidates": 0,
                "refined_count": 0,
                "results": [],
            }

        # ── LLM Refinement — remove noise ────────────────
        refined = _llm_refine(query, candidates)

        return {
            "success": True,
            "query": query,
            "filters": {"category": category} if category else None,
            "total_candidates": len(candidates),
            "refined_count": len(refined),
            "results": refined,
        }


def _format_candidate(doc: dict) -> str:
    """Format a single candidate for the LLM refinement prompt."""
    image_ids = doc.get("image_ids", [])
    image_str = ", ".join(image_ids) if image_ids else "none"
    # Include a content preview so LLM can judge relevance
    content_preview = (doc.get("text") or "")[:150]
    return (
        f"ID: {doc['id']} | "
        f"doc_id: {doc.get('doc_id', 'N/A')} | "
        f"category: {doc.get('category', 'N/A')} | "
        f"title: {doc.get('title', 'N/A')} | "
        f"images: {image_str} | "
        f"source: {doc.get('source', 'unknown')} | "
        f"preview: {content_preview}"
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
        "You are a search result refinement assistant for a spice product knowledge base.\n"
        "Given the user's search query and a list of knowledge base entries,\n"
        "determine which entries are RELEVANT to the query.\n"
        "Remove entries that are clearly NOT what the user is looking for.\n\n"
        "Rules:\n"
        "- If the user asks about pricing, keep pricing entries\n"
        "- If the user asks about recipes, keep recipe and recipe_ingredients entries\n"
        "- If the user asks about reviews, keep customer_reviews entries\n"
        "- If the user asks about product info, keep product_overview, product_features, and product_variant\n"
        "- Image descriptions are supplementary — keep them ONLY if they directly match the query context\n"
        "- When in doubt, KEEP the result (prefer recall over precision)\n\n"
        "Respond with ONLY a JSON array of relevant entry IDs (the integer 'id' field).\n"
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


def _clean_candidates(candidates: list[dict]) -> list[dict]:
    """Clean up candidate dicts for API response."""
    clean = []
    for doc in candidates:
        image_ids = doc.get("image_ids", [])
        if isinstance(image_ids, str):
            try:
                image_ids = json.loads(image_ids)
            except (json.JSONDecodeError, TypeError):
                image_ids = []

        clean.append({
            "id": doc["id"],
            "doc_id": doc.get("doc_id"),
            "category": doc.get("category"),
            "title": doc.get("title"),
            "content": doc.get("text"),
            "image_ids": image_ids,
            "score": doc.get("score"),
            "source": doc.get("source"),
        })
    return clean
