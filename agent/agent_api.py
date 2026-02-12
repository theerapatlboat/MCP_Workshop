"""FastAPI wrapper for the GoSaaS Agent — exposes POST /chat for the webhook.

Usage:
    1. Start the MCP server:  python mcp-server/server.py
    2. Start this API:        python agent/agent_api.py
    3. Start the webhook:     python webhook/main.py
"""

import asyncio
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp

load_dotenv()

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")
AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-4o-mini")

AGENT_INSTRUCTIONS = """\
You are GoSaaS Order Management Assistant.

You help users with:
- Order drafts: create, view, delete, attach payments
- Product search and details
- Shipping status tracking
- Sales reports and summaries
- Address verification
- FAQ and intent classification

Rules:
- Reply in the same language the user writes in
- Always use tools to get real data — never guess or fabricate
- When creating orders, first verify the address and fetch meta data
- Show results clearly and concisely
"""

# ---------------------------------------------------------------------------
# Conversation history per sender (in-memory)
# ---------------------------------------------------------------------------
conversations: dict[str, list] = {}

# ---------------------------------------------------------------------------
# Shared MCP server + Agent (initialized at startup)
# ---------------------------------------------------------------------------
mcp_server = None
agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start MCP connection on startup, close on shutdown."""
    global mcp_server, agent

    mcp_server = MCPServerStreamableHttp(
        name="GoSaaS MCP",
        params={"url": MCP_SERVER_URL},
        cache_tools_list=True,
    )
    await mcp_server.__aenter__()

    agent = Agent(
        name="GoSaaS Assistant",
        instructions=AGENT_INSTRUCTIONS,
        mcp_servers=[mcp_server],
        model=AGENT_MODEL,
    )

    tools = await mcp_server.list_tools()
    print(f"Agent API ready — {len(tools)} tools loaded, model: {AGENT_MODEL}")

    yield

    await mcp_server.__aexit__(None, None, None)


app = FastAPI(title="GoSaaS Agent API", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    sender_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    history = conversations.get(req.sender_id, [])
    messages = history + [{"role": "user", "content": req.message}]

    result = await Runner.run(agent, input=messages)

    # Save conversation history
    conversations[req.sender_id] = result.to_input_list()

    return ChatResponse(reply=result.final_output)


# ---------------------------------------------------------------------------
# POST /chat/clear — reset a user's conversation
# ---------------------------------------------------------------------------
@app.post("/chat/clear")
async def clear_chat(req: ChatRequest):
    conversations.pop(req.sender_id, None)
    return {"status": "cleared"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("agent_api:app", host="0.0.0.0", port=8002, reload=True)
