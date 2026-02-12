"""Long-term memory tools — store and retrieve user memories across sessions."""

import json

from mcp.server.fastmcp import FastMCP
from config import mem0_memory


def register(mcp: FastMCP) -> None:

    @mcp.tool()
    def memory_add(messages: str, user_id: str) -> dict:
        """
        บันทึก memory ระยะยาวสำหรับผู้ใช้ (long-term memory).

        ใช้เมื่อผู้ใช้บอกข้อมูลสำคัญที่ควรจดจำข้ามเซสชัน เช่น:
        - ชื่อ, ที่อยู่, เบอร์โทร
        - ยี่ห้อที่ชอบ, งบประมาณ, สีที่ชอบ
        - ประวัติการสั่งซื้อ, preference ต่าง ๆ

        mem0 จะใช้ LLM สกัดข้อมูลสำคัญจากบทสนทนาอัตโนมัติ
        ไม่ต้องสกัดข้อมูลเอง แค่ส่ง messages ทั้งหมดมา

        Args:
            messages: JSON string ของ messages array
                      เช่น '[{"role":"user","content":"ผมชื่อต้น ชอบ iPhone"}]'
            user_id: รหัสผู้ใช้ (เช่น Facebook user ID)

        Returns:
            Stored memories with IDs
        """
        try:
            parsed = json.loads(messages)
        except json.JSONDecodeError:
            # Fallback: treat as plain text from user
            parsed = [{"role": "user", "content": messages}]

        try:
            result = mem0_memory.add(parsed, user_id=user_id)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    def memory_search(query: str, user_id: str, limit: int = 5) -> dict:
        """
        ค้นหา memory ที่เกี่ยวข้องกับคำถามของผู้ใช้.

        ใช้เมื่อต้องการดึงข้อมูลที่เคยจำไว้ เช่น:
        - "ผู้ใช้คนนี้ชอบยี่ห้ออะไร?"
        - "งบประมาณของผู้ใช้คนนี้?"
        - "เคยสั่งอะไรไปแล้ว?"

        ควรเรียกใช้เมื่อเริ่มสนทนากับผู้ใช้ที่เคยคุยมาก่อน
        เพื่อ personalize การตอบ

        Args:
            query: คำค้นหา (เช่น "ยี่ห้อที่ชอบ", "งบประมาณ")
            user_id: รหัสผู้ใช้
            limit: จำนวนผลลัพธ์สูงสุด (default: 5)

        Returns:
            List of relevant memories
        """
        try:
            results = mem0_memory.search(query, user_id=user_id, limit=limit)
            return {"success": True, "memories": results}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    def memory_get_all(user_id: str) -> dict:
        """
        ดึง memory ทั้งหมดของผู้ใช้.

        ใช้เมื่อต้องการดูภาพรวมข้อมูลทั้งหมดที่จำไว้สำหรับผู้ใช้คนนี้

        Args:
            user_id: รหัสผู้ใช้

        Returns:
            All memories for this user
        """
        try:
            results = mem0_memory.get_all(user_id=user_id)
            return {"success": True, "memories": results}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    def memory_delete(memory_id: str) -> dict:
        """
        ลบ memory ที่ระบุ.

        ใช้เมื่อผู้ใช้ขอให้ลืมข้อมูลบางอย่าง เช่น "ลืมที่อยู่เก่าของผมทิ้ง"

        Args:
            memory_id: ID ของ memory ที่ต้องการลบ (ได้จาก memory_search หรือ memory_get_all)

        Returns:
            Deletion confirmation
        """
        try:
            mem0_memory.delete(memory_id=memory_id)
            return {"success": True, "message": f"Memory {memory_id} deleted"}
        except Exception as e:
            return {"success": False, "error": str(e)}
