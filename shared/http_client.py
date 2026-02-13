"""HTTP client utilities for forwarding messages to the Agent API."""

import httpx


async def forward_to_agent(
    agent_url: str,
    session_id: str,
    message: str,
    timeout: float = 30,
) -> dict:
    """Forward a message to the Agent API and return the parsed response.

    Args:
        agent_url: Full URL to the agent chat endpoint
        session_id: Session identifier
        message: User message text
        timeout: Request timeout in seconds

    Returns:
        Dict with keys: response (str), image_ids (list[str]), memory_count (int)

    Raises:
        Exception: If the request fails (caller should handle)
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            agent_url,
            json={"session_id": session_id, "message": message},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "response": data.get("response", data.get("reply", "")),
            "image_ids": data.get("image_ids", []),
            "memory_count": data.get("memory_count", 0),
        }
