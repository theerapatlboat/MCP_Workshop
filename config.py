"""Shared configuration for MCP tools."""

import os
import httpx
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

UAT_API_KEY = os.getenv("UAT_API_KEY", "")
UAT_API_URL = os.getenv("UAT_API_URL", "").rstrip("/")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

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
