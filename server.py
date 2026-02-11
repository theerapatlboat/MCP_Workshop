"""MCP Server for Order Management.

This server provides tools for:
1. create_order - Save order details from user
2. verify_address - Verify if address has sufficient data
3. get_product - Get a single product by ID from GoSaaS API
4. list_product - List products from GoSaaS API
5. faq - Answer frequently asked questions using OpenAI
6. intent_classify - Classify user message intent using OpenAI

Run the server:
    python server.py
"""

import os
import httpx
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

load_dotenv()

# Create MCP server
mcp = FastMCP("Order Management")

# API config
UAT_API_KEY = os.getenv("UAT_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PRODUCT_API_URL = "https://oapi.uatgosaasapi.co/api/v1/product/"

openai_client = OpenAI(api_key=OPENAI_API_KEY)

# In-memory storage for orders (in production, use a database)
orders: list[dict] = []


# Models for structured output
class OrderResult(BaseModel):
    """Result of order creation."""
    success: bool = Field(description="Whether the order was created successfully")
    order_id: str = Field(description="Unique identifier for the order")
    message: str = Field(description="Status message")


class AddressVerificationResult(BaseModel):
    """Result of address verification."""
    is_valid: bool = Field(description="Whether the address has sufficient data")
    missing_fields: list[str] = Field(description="List of missing required fields")
    message: str = Field(description="Verification status message")


# ──────────────────────────────────────────────
# Tool 1: create_order
# ──────────────────────────────────────────────
@mcp.tool()
def create_order(
    name: str,
    tel: str,
    address: str,
    payment_method: str
) -> OrderResult:
    """
    Create and save an order with the provided details.

    Args:
        name: Customer's full name
        tel: Customer's telephone/phone number
        address: Delivery address
        payment_method: Payment method (e.g., 'credit_card', 'cash_on_delivery', 'bank_transfer')

    Returns:
        OrderResult with success status, order_id, and message
    """
    import uuid
    from datetime import datetime

    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

    order = {
        "order_id": order_id,
        "name": name,
        "tel": tel,
        "address": address,
        "payment_method": payment_method,
        "created_at": datetime.now().isoformat()
    }

    orders.append(order)

    return OrderResult(
        success=True,
        order_id=order_id,
        message=f"Order created successfully for {name}"
    )


# ──────────────────────────────────────────────
# Tool 2: verify_address
# ──────────────────────────────────────────────
@mcp.tool()
def verify_address(
    name: str | None = None,
    tel: str | None = None,
    provinces: str | None = None,
    postcode: str | None = None
) -> AddressVerificationResult:
    """
    Verify if the address has sufficient data for delivery.

    Args:
        name: Customer's name
        tel: Customer's telephone number
        provinces: Province/state name
        postcode: Postal code

    Returns:
        AddressVerificationResult with validation status and missing fields
    """
    required_fields = {
        "name": name,
        "tel": tel,
        "provinces": provinces,
        "postcode": postcode
    }

    missing_fields = [
        field for field, value in required_fields.items()
        if value is None or (isinstance(value, str) and value.strip() == "")
    ]

    is_valid = len(missing_fields) == 0

    if is_valid:
        message = "Address verification passed. All required fields are present."
    else:
        message = f"Address verification failed. Missing fields: {', '.join(missing_fields)}"

    return AddressVerificationResult(
        is_valid=is_valid,
        missing_fields=missing_fields,
        message=message
    )


# ──────────────────────────────────────────────
# Tool 3: get_product
# ──────────────────────────────────────────────
@mcp.tool()
def get_product(product_id: int) -> dict:
    """
    Get a single product by its ID from the GoSaaS API.

    Args:
        product_id: The product ID to look up

    Returns:
        Product details dict or error message
    """
    headers = {"Authorization": f"Bearer {UAT_API_KEY}"}

    with httpx.Client(timeout=15) as client:
        resp = client.get(PRODUCT_API_URL, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    for product in data.get("data", []):
        if product.get("id") == product_id:
            return {
                "success": True,
                "product": {
                    "id": product["id"],
                    "name": product["name"],
                    "sku": product["sku"],
                    "barcode": product["barcode"],
                    "price": product["price"],
                    "original_price": product["original_price"],
                    "quantity": product["quantity"],
                    "description": product["description"],
                    "status": product["status"],
                }
            }

    return {"success": False, "message": f"Product with ID {product_id} not found"}


# ──────────────────────────────────────────────
# Tool 4: list_product
# ──────────────────────────────────────────────
@mcp.tool()
def list_product(limit: int = 10) -> dict:
    """
    List products from the GoSaaS API.

    Args:
        limit: Maximum number of products to return (default 10, max 100)

    Returns:
        List of products with basic info
    """
    limit = max(1, min(limit, 100))
    headers = {"Authorization": f"Bearer {UAT_API_KEY}"}

    with httpx.Client(timeout=15) as client:
        resp = client.get(PRODUCT_API_URL, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    products = []
    for product in data.get("data", [])[:limit]:
        products.append({
            "id": product["id"],
            "name": product["name"],
            "sku": product["sku"],
            "price": product["price"],
            "quantity": product["quantity"],
            "status": product["status"],
        })

    return {
        "success": True,
        "total": len(products),
        "products": products,
    }


# ──────────────────────────────────────────────
# Tool 5: faq
# ──────────────────────────────────────────────
@mcp.tool()
def faq(question: str) -> dict:
    """
    Answer frequently asked questions about orders, products, and services using AI.

    Args:
        question: The customer's question

    Returns:
        AI-generated answer based on FAQ knowledge
    """
    system_prompt = (
        "You are a helpful customer support assistant for an e-commerce store. "
        "Answer questions about orders, shipping, returns, payments, and products. "
        "Keep answers concise and friendly. Answer in the same language as the question. "
        "If you don't know the answer, say so honestly."
    )

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        max_tokens=500,
    )

    answer = response.choices[0].message.content
    return {"success": True, "question": question, "answer": answer}


# ──────────────────────────────────────────────
# Tool 6: intent_classify
# ──────────────────────────────────────────────
@mcp.tool()
def intent_classify(message: str) -> dict:
    """
    Classify the intent of a user message using AI.

    Possible intents: order, inquiry, complaint, return, tracking, greeting, other

    Args:
        message: The user message to classify

    Returns:
        Classified intent and confidence
    """
    system_prompt = (
        "You are an intent classifier. Classify the user message into exactly one intent.\n"
        "Possible intents: order, inquiry, complaint, return, tracking, greeting, other\n\n"
        "Respond in JSON format only: {\"intent\": \"...\", \"confidence\": 0.0-1.0}\n"
        "Do not include any other text."
    )

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        max_tokens=50,
    )

    import json
    raw = response.choices[0].message.content.strip()
    try:
        result = json.loads(raw)
        return {
            "success": True,
            "message": message,
            "intent": result.get("intent", "other"),
            "confidence": result.get("confidence", 0.0),
        }
    except json.JSONDecodeError:
        return {
            "success": True,
            "message": message,
            "intent": raw,
            "confidence": 0.0,
        }


# Run the server
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
