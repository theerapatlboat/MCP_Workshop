"""Shared configuration for MCP tools."""

import os
from pathlib import Path

import httpx
from openai import OpenAI
from dotenv import load_dotenv
from mem0 import Memory

load_dotenv()

UAT_API_KEY = os.getenv("UAT_API_KEY", "")
UAT_API_URL = os.getenv("UAT_API_URL", "").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

# ── mem0 Long-Term Memory ───────────────────────
mem0_memory = Memory.from_config({
    "llm": {
        "provider": "openai",
        "config": {
            "model": "gpt-4o-mini",
            "temperature": 0,
            "api_key": OPENAI_API_KEY,
        },
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "text-embedding-3-small",
            "api_key": OPENAI_API_KEY,
        },
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "path": str(Path(__file__).parent / "mem0_data" / "qdrant"),
        },
    },
})

AUTH_HEADERS = {
    "Authorization": f"Bearer {UAT_API_KEY}",
    "Content-Type": "application/json",
}


def api_get(path: str, params: dict | None = None) -> dict:
    """Helper for GET requests to the UAT API."""
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        resp = client.get(
            f"{UAT_API_URL}{path}",
            headers=AUTH_HEADERS,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()


def api_post(path: str, body: dict) -> dict:
    """Helper for POST requests to the UAT API."""
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        resp = client.post(
            f"{UAT_API_URL}{path}",
            headers=AUTH_HEADERS,
            json=body,
        )
        resp.raise_for_status()
        return resp.json()


def api_delete(path: str) -> dict:
    """Helper for DELETE requests to the UAT API."""
    with httpx.Client(timeout=15, follow_redirects=True) as client:
        resp = client.delete(
            f"{UAT_API_URL}{path}",
            headers=AUTH_HEADERS,
        )
        resp.raise_for_status()
        return resp.json()
