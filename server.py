"""MCP Server for Order Management.

This server provides two tools:
1. create_order - Save order details from user
2. verify_address - Verify if address has sufficient data

Run the server:
    uv run order_mcp_server.py

Or with Python directly:
    python order_mcp_server.py
"""

from typing import TypedDict
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP

# Create MCP server
mcp = FastMCP("Order Management")

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

    # Generate unique order ID
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

    # Create order object
    order = {
        "order_id": order_id,
        "name": name,
        "tel": tel,
        "address": address,
        "payment_method": payment_method,
        "created_at": datetime.now().isoformat()
    }

    # Save order to storage
    orders.append(order)

    return OrderResult(
        success=True,
        order_id=order_id,
        message=f"Order created successfully for {name}"
    )


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

    # Find missing fields
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


# Run the server
if __name__ == "__main__":
    mcp.run(transport="streamable-http")
