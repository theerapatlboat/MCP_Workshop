"""Utility tools — address verification, FAQ, intent classification."""

import json

from mcp.server.fastmcp import FastMCP
from .config import openai_client
from .models import AddressVerificationResult


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def verify_address(
        name: str | None = None,
        tel: str | None = None,
        address: str | None = None,
        sub_district: str | None = None,
        district: str | None = None,
        province: str | None = None,
        postal_code: str | None = None,
    ) -> AddressVerificationResult:
        """
        ตรวจสอบว่าข้อมูลที่อยู่ครบถ้วนสำหรับจัดส่ง.

        Args:
            name: ชื่อลูกค้า
            tel: เบอร์โทร
            address: ที่อยู่
            sub_district: ตำบล/แขวง
            district: อำเภอ/เขต
            province: จังหวัด
            postal_code: รหัสไปรษณีย์

        Returns:
            AddressVerificationResult with validation status and missing fields
        """
        required_fields = {
            "name": name,
            "tel": tel,
            "address": address,
            "sub_district": sub_district,
            "district": district,
            "province": province,
            "postal_code": postal_code,
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
            message=message,
        )

    @mcp.tool()
    def faq(question: str) -> dict:
        """
        ตอบคำถามที่พบบ่อยเกี่ยวกับคำสั่งซื้อ สินค้า และบริการ โดยใช้ AI.

        Args:
            question: คำถามของลูกค้า

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

    @mcp.tool()
    def intent_classify(message: str) -> dict:
        """
        จัดประเภท intent ของข้อความผู้ใช้ด้วย AI.

        Possible intents: order, inquiry, complaint, return, tracking, greeting, other

        Args:
            message: ข้อความที่ต้องการจัดประเภท

        Returns:
            Classified intent and confidence
        """
        system_prompt = (
            "You are an intent classifier. Classify the user message into exactly one intent.\n"
            "Possible intents: order, inquiry, complaint, return, tracking, greeting, other\n\n"
            'Respond in JSON format only: {"intent": "...", "confidence": 0.0-1.0}\n'
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
