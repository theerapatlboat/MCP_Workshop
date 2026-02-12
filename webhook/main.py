import hashlib
import hmac
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

load_dotenv()

FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "")
FB_APP_SECRET = os.getenv("FB_APP_SECRET", "")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
AI_AGENT_URL = os.getenv("AI_AGENT_URL", "http://localhost:8000/chat")

GRAPH_API_URL = "https://graph.facebook.com/v24.0/me/messages"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("webhook")
logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s")

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

file_handler = RotatingFileHandler(
    LOG_DIR / "webhook.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Facebook Messenger Webhook")

STATIC_DIR = Path(__file__).parent / "static"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def verify_signature(payload: bytes, signature_header: str) -> bool:
    """Verify X-Hub-Signature-256 using HMAC SHA-256."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        FB_APP_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header.removeprefix("sha256="))


async def send_message(recipient_id: str, text: str) -> None:
    """Send a text message via the Facebook Send API."""
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GRAPH_API_URL,
            params={"access_token": FB_PAGE_ACCESS_TOKEN},
            json=payload,
            timeout=10,
        )
    if resp.status_code != 200:
        logger.error("Send API error %s: %s", resp.status_code, resp.text)
    else:
        logger.info("Message sent to %s", recipient_id)


async def forward_to_agent(sender_id: str, text: str) -> str:
    """Forward the user message to the AI Agent and return its reply."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                AI_AGENT_URL,
                json={"session_id": sender_id, "message": text},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("reply", data.get("response", ""))
    except Exception as exc:
        logger.error("AI Agent request failed: %s", exc)
        return "ขออภัย ระบบไม่สามารถประมวลผลได้ในขณะนี้"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/webhook")
async def verify_webhook(
    request: Request,
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
):
    """Webhook verification endpoint required by Facebook."""
    logger.info("GET /webhook  mode=%s  token=%s", hub_mode, hub_verify_token)

    if hub_mode == "subscribe" and hub_verify_token == FB_VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return PlainTextResponse(hub_challenge)

    logger.warning("Webhook verification failed")
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def receive_webhook(request: Request):
    """Receive and process webhook events from Facebook."""
    body = await request.body()

    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    if FB_APP_SECRET and not verify_signature(body, signature):
        logger.warning("Invalid signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    data = await request.json()
    logger.info("Webhook event: %s", data)

    if data.get("object") != "page":
        raise HTTPException(status_code=404, detail="Not a page event")

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event.get("sender", {}).get("id")
            recipient_id = event.get("recipient", {}).get("id")

            # Skip echo messages
            message = event.get("message", {})
            if message.get("is_echo"):
                logger.info("Skipping echo message from %s", sender_id)
                continue

            # Text message
            text = message.get("text")
            if text:
                logger.info(
                    "Message from %s to %s: %s", sender_id, recipient_id, text
                )
                reply = await forward_to_agent(sender_id, text)
                if reply:
                    await send_message(sender_id, reply)

            # Attachments
            attachments = message.get("attachments")
            if attachments:
                logger.info(
                    "Attachments from %s: %s",
                    sender_id,
                    [a.get("type") for a in attachments],
                )

            # Postback
            postback = event.get("postback")
            if postback:
                logger.info(
                    "Postback from %s: title=%s payload=%s",
                    sender_id,
                    postback.get("title"),
                    postback.get("payload"),
                )
                reply = await forward_to_agent(
                    sender_id, postback.get("payload", "")
                )
                if reply:
                    await send_message(sender_id, reply)

    return PlainTextResponse("EVENT_RECEIVED")


# ---------------------------------------------------------------------------
# Static pages for Facebook App Review
# ---------------------------------------------------------------------------
@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    return (STATIC_DIR / "privacy.html").read_text(encoding="utf-8")


@app.get("/terms", response_class=HTMLResponse)
async def terms_of_service():
    return (STATIC_DIR / "terms.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
