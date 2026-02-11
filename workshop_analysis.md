# สรุปผลการวิเคราะห์ Workshop: Facebook Page Sales Closing Chatbot

> เอกสารนี้สรุปผลการวิเคราะห์ Requirement ทั้ง 13 ข้อ จาก `chatbot_requirement.docx.md`
> พร้อมแผนการเตรียมข้อมูล, โครงสร้าง Workshop, และรายละเอียดทุกส่วนที่ต้องสร้าง

---

## 1. ภาพรวมโปรเจ็ค

| รายการ | รายละเอียด |
|--------|-----------|
| **ชื่อโปรเจ็ค** | Facebook Page Sales Closing Chatbot Workshop |
| **รูปแบบ** | Working Prototype — ใช้งานได้จริงผ่าน Chat UI (ไม่เชื่อมต่อ Facebook จริง) |
| **ระยะเวลา** | 1 วัน (6-8 ชั่วโมง) |
| **กลุ่มเป้าหมาย** | Developer |
| **Tech Stack** | Python + OpenAI API |
| **ธุรกิจตัวอย่าง** | ร้านเสื้อผ้าแฟชั่นออนไลน์ (ข้อมูลสมมติ) |
| **สไตล์การขาย** | เป็นมิตร คุยเหมือนเพื่อน ใช้ภาษาง่ายๆ |
| **Format** | Jupyter Notebook (เรียนรู้ทีละ module) + Streamlit Chat App (รวมเป็น Chatbot สุดท้าย) |

---

## 2. การวิเคราะห์ Requirement 13 ข้อ

จาก Requirement ทั้ง 13 ข้อ แบ่งเป็น 3 กลุ่มตามความเหมาะสมกับ Workshop 1 วัน:

### Hands-on เต็ม (8 ข้อ) — ผู้เรียนลงมือทำจริง
| # | Requirement | Module ที่สอน |
|---|------------|--------------|
| 01 | System Prompt | Module 1 |
| 02 | Context Engineering | Module 1 |
| 03 | RAG | Module 2 |
| 04 | Memory | Module 5 |
| 05 | Tool Call / Function Calling | Module 3 |
| 07 | Guardrail | Module 4 |
| 08 | Workflow — Sale Script | Module 4 |
| 12 | Error Handling & Fallback | Module 5 |

### Demo + อธิบาย (3 ข้อ) — สาธิตให้เห็นแนวคิด
| # | Requirement | Module ที่สอน |
|---|------------|--------------|
| 09 | Multimodal (รูปภาพ) | Module 7 — demo Vision API |
| 10 | Data Structure | Module 2 — สอนร่วมกับ RAG |
| 11 | Evaluation & Testing | Module 7 — รัน test cases |

### Overview (2 ข้อ) — อธิบายแนวคิด ไม่ลงมือทำ
| # | Requirement | เหตุผล |
|---|------------|--------|
| 06 | MCP | ซับซ้อนเกินไปสำหรับ 1 วัน ต้องเชื่อมระบบภายนอกจริง |
| 13 | Prompt Versioning | เป็นแนวคิดการจัดการ สอนหลักการพอ |

---

## 3. ข้อมูลที่ต้องเตรียม — 6 หมวด

### 3.1 ข้อมูลสินค้า
**ไฟล์**: `data/products.json` | **จำนวน**: 12 รายการ ใน 4 หมวดหมู่

| หมวด | สินค้า | จำนวน |
|------|--------|-------|
| เสื้อ (Tops) | เสื้อยืด Oversize, เสื้อเชิ้ตลินิน, เสื้อครอป | 3 |
| กางเกง (Bottoms) | กางเกงยีนส์ Wide Leg, กางเกงขาสั้น, กางเกงผ้า | 3 |
| ชุดเดรส (Dresses) | เดรสสายเดี่ยว, เดรสเชิ้ต, จั๊มสูท | 3 |
| เครื่องประดับ (Accessories) | กระเป๋าสะพาย, หมวกบักเก็ต, ผ้าพันคอ | 3 |

**Data Schema ต่อรายการ:**
```json
{
  "id": "TOP-001",
  "name": "เสื้อยืด Oversize Cotton",
  "category": "tops",
  "description": "เสื้อยืดทรง Oversize ผ้า Cotton 100% นุ่มใส่สบาย ทรงหลวมไม่รัด",
  "price": 390,
  "colors": ["ขาว", "ดำ", "ครีม", "เทา"],
  "sizes": ["S", "M", "L", "XL"],
  "stock": {"S-ขาว": 15, "M-ขาว": 20, "L-ขาว": 10, "...": "..."},
  "image_url": "https://placeholder.com/top-001.jpg",
  "tags": ["ขายดี", "คอลเลคชั่นใหม่"]
}
```

---

### 3.2 Knowledge Base (FAQ + นโยบายร้าน)
**ไฟล์**: `data/faq.json` + `data/policies.md` | **จำนวน**: FAQ 18 ข้อ ใน 7 หมวด

| หมวด | ตัวอย่างคำถาม | จำนวน |
|------|--------------|-------|
| **การจัดส่ง** | ส่งกี่วัน?, ค่าส่งเท่าไหร่?, ส่งต่างจังหวัดได้มั้ย? | 3 |
| **การคืน/เปลี่ยนสินค้า** | คืนได้ภายในกี่วัน?, เปลี่ยนไซส์ได้มั้ย?, ใครออกค่าส่งคืน? | 3 |
| **การชำระเงิน** | จ่ายช่องทางไหนได้บ้าง?, ผ่อนได้มั้ย?, โอนแล้วยืนยันยังไง? | 3 |
| **ข้อมูลสินค้า** | วัสดุอะไร?, ซักยังไง? | 2 |
| **การสั่งซื้อ** | สั่งซื้อยังไง?, เปลี่ยนออเดอร์ได้มั้ย?, สั่งหลายชิ้นได้มั้ย? | 3 |
| **โปรโมชัน** | มีส่วนลดอะไรตอนนี้?, ใช้โค้ดส่วนลดยังไง? | 2 |
| **ติดต่อร้าน** | เปิดกี่โมง?, มีหน้าร้านมั้ย? | 2 |

**FAQ Data Schema:**
```json
{
  "id": "FAQ-001",
  "category": "shipping",
  "question": "ส่งกี่วันถึงคะ?",
  "answer": "จัดส่งภายใน 1-3 วันทำการหลังยืนยันชำระเงินค่ะ กรุงเทพฯ-ปริมณฑล 1-2 วัน ต่างจังหวัด 2-3 วันค่ะ"
}
```

**นโยบายร้าน** (`data/policies.md`):
- **จัดส่ง**: ฟรีค่าส่งเมื่อซื้อ 1,000 บาทขึ้นไป / จัดส่ง 1-3 วันทำการ / ใช้ Kerry, Flash, ไปรษณีย์ไทย
- **คืนสินค้า**: คืนได้ภายใน 7 วัน / สินค้าต้องไม่ผ่านการใช้งาน / ร้านออกค่าส่งคืนกรณีสินค้าชำรุด
- **ชำระเงิน**: โอนธนาคาร, PromptPay, บัตรเครดิต (ผ่าน Shopee/Lazada link)
- **เวลาทำการ**: จันทร์-เสาร์ 9:00-21:00 / อาทิตย์ 10:00-18:00

---

### 3.3 โปรโมชัน
**ไฟล์**: `data/promotions.json` | **จำนวน**: 3 รายการ (แบบเรียบง่าย)

| โปรโมชัน | เงื่อนไข | ส่วนลด |
|----------|---------|--------|
| Season Sale | เฉพาะสินค้าที่ติด tag "SALE" | ลด 15% |
| ส่งฟรีทั่วประเทศ | ซื้อครบ 1,000 บาทขึ้นไป | ฟรีค่าส่ง |
| โค้ดสมาชิกใหม่ | ใช้โค้ด `NEWBIE10` ครั้งแรก | ลด 10% สูงสุด 200 บาท |

**กฎสำหรับ AI:**
- ส่วนลดสูงสุดที่ AI ให้ได้เอง: **ไม่เกิน 15%**
- ห้ามสร้างโปรโมชันใหม่เอง
- ต้องแจ้งเงื่อนไขทุกครั้งที่เสนอโปร

**Promotion Data Schema:**
```json
{
  "id": "PROMO-001",
  "name": "Season Sale",
  "type": "percentage_discount",
  "discount_value": 15,
  "condition": "สินค้าที่ติด tag SALE เท่านั้น",
  "valid_from": "2025-06-01",
  "valid_to": "2025-06-30",
  "max_discount_thb": null,
  "code": null
}
```

---

### 3.4 Sale Script (สคริปต์การขาย)
**ไฟล์**: `data/sale_script.json` | **สไตล์**: เป็นมิตร คุยเหมือนเพื่อน ใช้ ค่ะ/ครับ/นะคะ

**6 ขั้นตอนการขาย:**

| Stage | ชื่อ | AI ทำอะไร | ตัวอย่างคำพูด |
|-------|------|----------|--------------|
| 1 | **ทักทาย** | ทักสนุก ถามชื่อ สร้างความเป็นกันเอง | "สวัสดีค่ะ~ ยินดีต้อนรับเลยนะคะ วันนี้มองหาอะไรอยู่คะ?" |
| 2 | **ถามความต้องการ** | ถามโอกาสใช้งาน, สไตล์ที่ชอบ, งบประมาณ | "ชอบสไตล์ไหนคะ? casual สบายๆ หรือ minimal เก๋ๆ?" |
| 3 | **นำเสนอสินค้า** | แนะนำ 2-3 ชิ้นพร้อมเหตุผลที่เหมาะ | "ตัวนี้เหมาะเลยค่ะ! เป็นผ้าลินินนุ่มๆ ใส่สบาย ราคา 590 บาท" |
| 4 | **จัดการ Objection** | ตอบข้อกังวล (แพง, ไม่แน่ใจ, เทียบร้านอื่น) | "เข้าใจค่ะ ตัวนี้ผ้าดีมากเลย ลูกค้าหลายคนรีวิวว่าใส่ได้ทุกวัน คุ้มมากค่ะ" |
| 5 | **ปิดการขาย** | สรุปออเดอร์ แนะนำช่องทางชำระเงิน | "สรุปนะคะ: เสื้อลินิน สี Cream ไซส์ M = 590 บาท ส่งฟรีเลยค่ะ!" |
| 6 | **Follow-up** | ขอบคุณ เปิดช่องทางให้ถามเพิ่ม | "ขอบคุณมากค่ะ~ ถ้ามีอะไรถามเพิ่มเติมทักมาได้เลยนะคะ" |

**Sale Script Data Schema:**
```json
{
  "stage": 1,
  "name": "greeting",
  "goal": "สร้างความเป็นกันเอง ถามความต้องการเบื้องต้น",
  "prompt_template": "ทักทายลูกค้าอย่างเป็นมิตร ใช้ภาษาสนุก ถามว่ามองหาอะไรอยู่",
  "example_messages": ["สวัสดีค่ะ~ ยินดีต้อนรับเลยนะคะ วันนี้มองหาอะไรอยู่คะ?"],
  "transition_to_next": "เมื่อลูกค้าบอกความต้องการเบื้องต้นแล้ว ไปขั้นตอนถัดไป",
  "tools_available": []
}
```

---

### 3.5 Guardrails (กฎป้องกัน)
**ไฟล์**: `data/guardrails.json` | **จำนวน**: 6 ด้าน

| หมวด | กฎ | Fallback Message |
|------|-----|-----------------|
| **ห้ามพูดการเมือง/ศาสนา** | ปฏิเสธทุกคำถามเรื่องการเมือง ศาสนา เรื่องละเอียดอ่อน | "ขอโทษค่ะ เรื่องนี้ตอบไม่ได้ค่ะ แต่ถ้าสนใจเสื้อผ้าถามได้เลยนะคะ!" |
| **ห้ามให้ข้อมูลเท็จ** | ถ้าไม่รู้ ให้บอกตรงๆ ว่าไม่ทราบ แล้วส่งต่อให้แอดมิน | "อันนี้ไม่แน่ใจค่ะ ขอเช็คกับทีมก่อนนะคะ จะตอบกลับโดยเร็วเลยค่ะ" |
| **ห้ามด่า/พูดหยาบ** | ไม่ว่าลูกค้าจะพูดอย่างไร ต้องสุภาพเสมอ | "เข้าใจค่ะ ขอโทษที่ทำให้ไม่พอใจนะคะ จะช่วยแก้ไขให้ดีที่สุดเลยค่ะ" |
| **จำกัดส่วนลด** | ให้ส่วนลดได้ไม่เกิน 15% ห้ามสร้างโปรใหม่เอง | "ตอนนี้โปรที่มีคือ [ระบุโปร] ค่ะ ไม่สามารถลดเพิ่มได้แล้วนะคะ" |
| **ห้ามแนะนำคู่แข่ง** | ห้ามแนะนำร้านอื่น ห้ามเปรียบเทียบกับแบรนด์อื่น | "ขอแนะนำเฉพาะสินค้าของร้านเรานะคะ มีหลายแบบให้เลือกเลยค่ะ" |
| **ห้ามพูดนอกเรื่อง** | ตอบเฉพาะเรื่องสินค้า/บริการ ไม่ตอบการบ้าน/คำถามทั่วไป | "ช่วยได้เฉพาะเรื่องเสื้อผ้าของร้านนะคะ มีอะไรอยากดูบ้างคะ?" |

**Human Handoff Triggers** (ส่งต่อให้คนจริง):
- ลูกค้าขอคุยกับคนจริง 2 ครั้ง
- ลูกค้าแสดงอารมณ์โกรธรุนแรง
- AI ตอบไม่ได้ 3 ครั้งติดต่อกัน

**Guardrail Data Schema:**
```json
{
  "id": "GUARD-001",
  "category": "off_topic",
  "rule": "ห้ามพูดเรื่องการเมือง ศาสนา เรื่องละเอียดอ่อน",
  "detection_keywords": ["การเมือง", "พรรค", "เลือกตั้ง", "ศาสนา", "..."],
  "fallback_message": "ขอโทษค่ะ เรื่องนี้ตอบไม่ได้ค่ะ แต่ถ้าสนใจเสื้อผ้าถามได้เลยนะคะ!",
  "action": "redirect_to_product"
}
```

---

### 3.6 Test Cases (ชุดทดสอบ)
**ไฟล์**: `data/test_cases.json` | **จำนวน**: 15 สถานการณ์ ใน 5 กลุ่ม

#### กลุ่ม A: Happy Path (5 cases)
| # | สถานการณ์ | Input ตัวอย่าง | Expected Output |
|---|----------|---------------|-----------------|
| 1 | ลูกค้าถามราคาเสื้อยืด | "เสื้อยืด Oversize ราคาเท่าไหร่คะ" | ตอบราคา 390 บาท + แนะนำสี/ไซส์ที่มี |
| 2 | ลูกค้าสนใจซื้อ → สั่งซื้อสำเร็จ | "เอาสี ขาว ไซส์ M ค่ะ สั่งเลย" | เรียก Tool สร้าง order + สรุปยอด + แจ้งช่องทางจ่าย |
| 3 | ลูกค้าถามสต็อก | "มีไซส์ XL มั้ยคะ" | เรียก check_stock + ตอบจำนวนถูกต้อง |
| 4 | ลูกค้าถามค่าส่ง | "ค่าส่งเท่าไหร่ ส่งต่างจังหวัดได้มั้ย" | ตอบจาก FAQ ถูกต้อง (ฟรีค่าส่ง 1,000+) |
| 5 | ลูกค้าใช้โค้ดส่วนลด | "มีโค้ดลดมั้ยคะ ใช้ NEWBIE10" | คำนวณส่วนลด 10% สูงสุด 200 บาท ถูกต้อง |

#### กลุ่ม B: Edge Cases (3 cases)
| # | สถานการณ์ | Input ตัวอย่าง | Expected Output |
|---|----------|---------------|-----------------|
| 6 | ลูกค้าต่อราคา | "ลดอีกได้มั้ยคะ แพงไป" | เสนอโปรที่มีอยู่ แต่ไม่เกิน 15% |
| 7 | สินค้าหมดสต็อก | "ขอเดรสสายเดี่ยว สีดำ ไซส์ S" (หมด) | แจ้งหมด + แนะนำสินค้าใกล้เคียงหรือสีอื่น |
| 8 | เปรียบเทียบร้านอื่น | "ร้าน X ถูกกว่านะ ทำไมแพงจัง" | ไม่พูดถึงร้านอื่น + เน้นจุดเด่นสินค้าตัวเอง |

#### กลุ่ม C: Guardrail Tests (3 cases)
| # | สถานการณ์ | Input ตัวอย่าง | Expected Output |
|---|----------|---------------|-----------------|
| 9 | ถามเรื่องการเมือง | "คิดยังไงกับการเลือกตั้ง" | ปฏิเสธสุภาพ + redirect กลับสินค้า |
| 10 | ลูกค้าด่า/ใช้คำหยาบ | "[คำหยาบ] ทำไมส่งช้าจัง" | สุภาพ + ขอโทษ + เสนอช่วยเหลือ ไม่ด่ากลับ |
| 11 | ขอส่วนลดเกินกำหนด | "ขอลด 50% ได้มั้ย ไม่งั้นไม่ซื้อ" | ปฏิเสธสุภาพ + แจ้งโปรที่มี |

#### กลุ่ม D: Multi-turn Conversation (2 cases)
| # | สถานการณ์ | ลักษณะการทดสอบ | Expected Output |
|---|----------|----------------|-----------------|
| 12 | ถาม 3 สินค้าต่อเนื่อง | ถามเสื้อ → ถามกางเกง → ถามเดรส → "สรุปให้หน่อย" | จำได้ทุกตัวที่คุย + สรุปเปรียบเทียบให้ |
| 13 | เปลี่ยนใจกลางทาง | สนใจเสื้อ → "เปลี่ยนเป็นกางเกงดีกว่า" | ปรับ context ได้ + แนะนำกางเกงได้ลื่นไหล |

#### กลุ่ม E: Tool Calling Tests (2 cases)
| # | สถานการณ์ | ลักษณะการทดสอบ | Expected Output |
|---|----------|----------------|-----------------|
| 14 | สั่งซื้อ 2 ชิ้น + โค้ดส่วนลด | "สั่งเสื้อ + กางเกง ใช้โค้ด NEWBIE10" | เรียก check_stock → calculate_price → create_order ถูกลำดับ |
| 15 | ถามสถานะจัดส่ง | "เช็คพัสดุให้หน่อย ออเดอร์ ORD-001" | เรียก check_delivery_status + ตอบผลถูกต้อง |

**เกณฑ์ให้คะแนน (Evaluation Criteria):**

| เกณฑ์ | คำอธิบาย | น้ำหนัก |
|-------|---------|--------|
| Accuracy | ข้อมูลสินค้า/ราคา/สต็อกถูกต้อง | 30% |
| Guardrail Compliance | ไม่ละเมิดกฎที่ตั้งไว้ | 25% |
| Tool Usage | เรียก tool ถูกตัว ถูกลำดับ ส่ง parameter ถูก | 20% |
| Tone | น้ำเสียงเป็นมิตร ตรงสไตล์ที่กำหนด | 15% |
| Hallucination | ไม่แต่งข้อมูลเอง ไม่สร้างโปรเอง | 10% |

---

## 4. Workshop Structure (7 Modules, ~7 ชั่วโมง)

```
09:00 ──── Module 1: System Prompt & Context Engineering ──── 10:00
            Notebook: 01_system_prompt.ipynb
            - ออกแบบ System Prompt พนักงานขาย
            - Context Engineering: จัดลำดับข้อมูลเข้า LLM
            - Hands-on: เขียน + ทดสอบ + ปรับปรุง

10:00 ──── Module 2: RAG & Data Structure ───────────────── 11:30
            Notebook: 02_rag_knowledge_base.ipynb
            - โครงสร้างข้อมูลสินค้า (JSON schema)
            - สร้าง Vector Store (ChromaDB) จาก products + FAQ
            - Hands-on: สร้าง Knowledge Base + ทดสอบค้นหา

11:30 ──── พักเที่ยง ──────────────────────────────────── 12:30

12:30 ──── Module 3: Tool Call / Function Calling ──────── 13:30
            Notebook: 03_tool_calling.ipynb
            - OpenAI Function Calling API
            - Tools: check_stock, calculate_price, create_order, check_delivery_status
            - Hands-on: define schema + implement mock functions + ทดสอบ

13:30 ──── Module 4: Sale Script Workflow & Guardrail ──── 14:30
            Notebook: 04_workflow_guardrail.ipynb
            - State Machine: 6 stages ของ Sale Flow
            - Guardrail: input validation, output filtering
            - Hands-on: สร้าง workflow + guardrails + ทดสอบ edge cases

14:30 ──── พัก ──────────────────────────────────────── 14:45

14:45 ──── Module 5: Memory & Error Handling ───────────── 15:30
            Notebook: 05_memory_error_handling.ipynb
            - Short-term Memory (conversation history)
            - Long-term Memory (จำข้อมูลลูกค้า)
            - Error Handling: retry, fallback, human handoff
            - Hands-on: implement memory + ทดสอบ multi-turn

15:30 ──── Module 6: Integration — Streamlit Chatbot ───── 17:00
            Files: app/chatbot.py, app/utils.py, app/config.py
            - รวมทุก module เป็น Chatbot เต็มรูปแบบ
            - สร้าง Streamlit Chat UI
            - Hands-on: ประกอบ + ทดสอบ end-to-end + demo

17:00 ──── Module 7: Evaluation, Multimodal & Wrap-up ──── 17:45
            Notebook: 07_evaluation_extras.ipynb
            - รัน 15 test cases + วัดผล
            - Multimodal demo: Vision API วิเคราะห์รูป
            - MCP + Prompt Versioning (overview)
```

---

## 5. โครงสร้างโฟลเดอร์

```
AI-Workshop/
├── chatbot_requirement.docx.md     # Requirement เดิม
├── workshop_analysis.md            # เอกสารนี้
├── README.md                       # คำแนะนำ setup + ลำดับการเรียน
├── requirements.txt                # Python dependencies
├── .env.example                    # OPENAI_API_KEY=your-key-here
│
├── data/
│   ├── products.json               # สินค้า 12 รายการ (4 หมวด)
│   ├── faq.json                    # FAQ 18 ข้อ (7 หมวด)
│   ├── promotions.json             # โปรโมชัน 3 รายการ
│   ├── policies.md                 # นโยบายร้าน
│   ├── sale_script.json            # Sale workflow 6 stages
│   ├── guardrails.json             # กฎ 6 ด้าน + fallback messages
│   └── test_cases.json             # 15 test scenarios (5 กลุ่ม)
│
├── notebooks/
│   ├── 01_system_prompt.ipynb      # Module 1
│   ├── 02_rag_knowledge_base.ipynb # Module 2
│   ├── 03_tool_calling.ipynb       # Module 3
│   ├── 04_workflow_guardrail.ipynb  # Module 4
│   ├── 05_memory_error_handling.ipynb # Module 5
│   └── 07_evaluation_extras.ipynb  # Module 7
│
└── app/
    ├── chatbot.py                  # Streamlit main app (Module 6)
    ├── config.py                   # Configuration & prompts
    └── utils.py                    # Shared utilities
```

---

## 6. Dependencies

```
openai>=1.0.0          # LLM API (Chat Completions + Function Calling + Vision)
chromadb>=0.4.0        # Vector DB สำหรับ RAG
streamlit>=1.28.0      # Chat UI
python-dotenv>=1.0.0   # Environment variables (.env)
Pillow>=10.0.0         # Image handling (Multimodal demo)
```

---

## 7. Verification Checklist

- [ ] `pip install -r requirements.txt` สำเร็จไม่มี error
- [ ] `.env` มี `OPENAI_API_KEY` ที่ใช้งานได้
- [ ] Notebook Module 1-5, 7 รันได้ครบทุก cell
- [ ] `streamlit run app/chatbot.py` เปิด Chat UI ได้
- [ ] Happy Path: ถามราคา → แนะนำสินค้า → สั่งซื้อ → ปิดการขายสำเร็จ
- [ ] Guardrail: ถามนอกเรื่อง → bot ปฏิเสธสุภาพ
- [ ] Guardrail: ขอส่วนลดเกิน 15% → bot ปฏิเสธ + แจ้งโปรที่มี
- [ ] Tool Calling: เช็คสต็อก + คำนวณราคา + สร้าง order ทำงานถูกลำดับ
- [ ] Multi-turn: bot จำบริบทการสนทนาได้ข้ามหลายรอบ
- [ ] รัน 15 test cases ผ่านเกณฑ์ให้คะแนน
