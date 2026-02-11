# Implementation Flow: Facebook Page Sales Closing Chatbot Workshop

## Context
จาก `workshop_analysis.md` ที่วิเคราะห์ Requirement 13 ข้อแล้ว เอกสารนี้คือ **แผนการ implement ทั้งหมด**
แบ่งเป็น 5 Phase, 20 Tasks, 113 Steps เพื่อสร้าง Workshop ให้พร้อมใช้งาน

```
Phase 1 (Setup)  →  Phase 2 (Data)  →  Phase 3 (Notebooks)  →  Phase 4 (App)  →  Phase 5 (Test)
     ↓                    ↓                    ↓                    ↓                   ↓
  30 นาที             2-3 ชั่วโมง          4-5 ชั่วโมง          2-3 ชั่วโมง         1-2 ชั่วโมง
```

| Phase | Tasks | Steps | ไฟล์ที่สร้าง |
|-------|-------|-------|-------------|
| **1** Project Setup | 2 | 7 | requirements.txt, .env.example, .gitignore, README.md |
| **2** Data Preparation | 6 | 25 | products.json, faq.json, policies.md, promotions.json, sale_script.json, guardrails.json, test_cases.json |
| **3** Notebooks | 6 | 55 | 6 notebooks (.ipynb) |
| **4** Streamlit App | 3 | 12 | config.py, utils.py, chatbot.py |
| **5** Testing | 3 | 14 | — (ทดสอบไฟล์ที่มี) |
| **รวม** | **20** | **113** | **17 ไฟล์** |

---

## Phase 1: Project Setup — สร้างโครงสร้างโปรเจ็ค

### Task 1.1: สร้างโครงสร้างโฟลเดอร์
> **ทำอะไร**: สร้าง directory structure ทั้งหมดที่ Workshop ต้องใช้
> **ทำอย่างไร**: สร้างโฟลเดอร์ `data/`, `notebooks/`, `app/` ภายใต้ `AI-Workshop/`

| Step | ทำอะไร | ไฟล์/โฟลเดอร์ |
|------|--------|--------------|
| 1.1.1 | สร้างโฟลเดอร์ `data/` | `data/` |
| 1.1.2 | สร้างโฟลเดอร์ `notebooks/` | `notebooks/` |
| 1.1.3 | สร้างโฟลเดอร์ `app/` | `app/` |

### Task 1.2: สร้างไฟล์ Configuration
> **ทำอะไร**: สร้างไฟล์ตั้งค่าโปรเจ็ค ได้แก่ dependencies, environment variables, README
> **ทำอย่างไร**: เขียนไฟล์ทีละไฟล์ ระบุ package versions ที่เข้ากันได้

| Step | ทำอะไร | วิธีทำ | ไฟล์ |
|------|--------|--------|------|
| 1.2.1 | สร้าง `requirements.txt` | ระบุ packages: `openai>=1.0.0`, `chromadb>=0.4.0`, `streamlit>=1.28.0`, `python-dotenv>=1.0.0`, `Pillow>=10.0.0` | `requirements.txt` |
| 1.2.2 | สร้าง `.env.example` | เขียน template: `OPENAI_API_KEY=your-api-key-here` พร้อมคอมเมนต์อธิบายวิธี copy เป็น `.env` | `.env.example` |
| 1.2.3 | สร้าง `.gitignore` | เพิ่ม `.env`, `__pycache__/`, `*.pyc`, `.chroma/`, `.ipynb_checkpoints/` | `.gitignore` |
| 1.2.4 | สร้าง `README.md` | เขียนคำแนะนำ: prerequisites, วิธี setup, ลำดับการเรียน Module 1-7, วิธีรัน Streamlit | `README.md` |

---

## Phase 2: Data Preparation — สร้างข้อมูลทั้ง 6 หมวด

### Task 2.1: สร้างข้อมูลสินค้า
> **ทำอะไร**: สร้างข้อมูลสินค้าสมมติร้านเสื้อผ้าแฟชั่น 12 รายการ ใน 4 หมวด
> **ทำอย่างไร**: เขียน JSON array โดยแต่ละรายการมี fields ตาม schema ที่กำหนดใน analysis

| Step | ทำอะไร | วิธีทำ | ไฟล์ |
|------|--------|--------|------|
| 2.1.1 | สร้างสินค้าหมวด Tops 3 รายการ | เขียนข้อมูล: เสื้อยืด Oversize (390 บาท), เสื้อเชิ้ตลินิน (590 บาท), เสื้อครอป (350 บาท) — แต่ละตัวมี id, name, category, description, price, colors[], sizes[], stock{}, image_url, tags[] | `data/products.json` |
| 2.1.2 | สร้างสินค้าหมวด Bottoms 3 รายการ | เขียนข้อมูล: กางเกงยีนส์ Wide Leg (690 บาท), กางเกงขาสั้น (450 บาท), กางเกงผ้าลินิน (550 บาท) — ตั้ง stock บาง size/สี ให้เป็น 0 (สำหรับทดสอบหมดสต็อก) | `data/products.json` |
| 2.1.3 | สร้างสินค้าหมวด Dresses 3 รายการ | เขียนข้อมูล: เดรสสายเดี่ยว (650 บาท), เดรสเชิ้ต (750 บาท), จั๊มสูท (890 บาท) — ติด tag "SALE" ที่เดรสสายเดี่ยว เพื่อทดสอบ Season Sale promo | `data/products.json` |
| 2.1.4 | สร้างสินค้าหมวด Accessories 3 รายการ | เขียนข้อมูล: กระเป๋าสะพาย (490 บาท), หมวกบักเก็ต (290 บาท), ผ้าพันคอ (250 บาท) — ติด tag "ขายดี" ที่กระเป๋า, tag "Limited" ที่ผ้าพันคอ | `data/products.json` |

### Task 2.2: สร้าง Knowledge Base (FAQ + นโยบาย)
> **ทำอะไร**: สร้าง FAQ 18 ข้อใน 7 หมวด และเอกสารนโยบายร้าน
> **ทำอย่างไร**: เขียน FAQ เป็น JSON array (id, category, question, answer) และนโยบายเป็น Markdown

| Step | ทำอะไร | วิธีทำ | ไฟล์ |
|------|--------|--------|------|
| 2.2.1 | เขียน FAQ หมวดจัดส่ง (3 ข้อ) | คำถาม: ส่งกี่วัน?, ค่าส่งเท่าไหร่?, ส่งต่างจังหวัดได้มั้ย? — คำตอบสไตล์เป็นมิตร ใช้ค่ะ/นะคะ | `data/faq.json` |
| 2.2.2 | เขียน FAQ หมวดคืน/เปลี่ยน (3 ข้อ) | คำถาม: คืนได้กี่วัน?, เปลี่ยนไซส์ได้มั้ย?, ใครออกค่าส่งคืน? | `data/faq.json` |
| 2.2.3 | เขียน FAQ หมวดชำระเงิน (3 ข้อ) | คำถาม: จ่ายช่องทางไหน?, ผ่อนได้มั้ย?, โอนแล้วยืนยันยังไง? | `data/faq.json` |
| 2.2.4 | เขียน FAQ หมวดข้อมูลสินค้า (2 ข้อ) | คำถาม: วัสดุอะไร?, ไซส์เป็นยังไง? | `data/faq.json` |
| 2.2.5 | เขียน FAQ หมวดการสั่งซื้อ (3 ข้อ) | คำถาม: สั่งซื้อยังไง?, เปลี่ยนออเดอร์ได้มั้ย?, สั่งหลายชิ้นได้มั้ย? | `data/faq.json` |
| 2.2.6 | เขียน FAQ หมวดโปรโมชัน (2 ข้อ) | คำถาม: มีส่วนลดอะไร?, ใช้โค้ดยังไง? | `data/faq.json` |
| 2.2.7 | เขียน FAQ หมวดติดต่อร้าน (2 ข้อ) | คำถาม: เปิดกี่โมง?, มีหน้าร้านมั้ย? | `data/faq.json` |
| 2.2.8 | เขียนนโยบายร้าน | เขียน Markdown 4 หมวด: จัดส่ง (ฟรีค่าส่ง 1,000+, 1-3 วัน, Kerry/Flash), คืนสินค้า (7 วัน, ไม่ผ่านการใช้งาน), ชำระเงิน (โอน/PromptPay/บัตร), เวลาทำการ (จ-ส 9-21, อา 10-18) | `data/policies.md` |

### Task 2.3: สร้างข้อมูลโปรโมชัน
> **ทำอะไร**: สร้างโปรโมชัน 3 รายการ แบบเรียบง่าย
> **ทำอย่างไร**: เขียน JSON array ตาม Promotion schema (id, name, type, discount_value, condition, valid dates, code)

| Step | ทำอะไร | วิธีทำ | ไฟล์ |
|------|--------|--------|------|
| 2.3.1 | สร้างโปร Season Sale | type: percentage_discount, discount: 15%, condition: สินค้าติด tag "SALE", code: null | `data/promotions.json` |
| 2.3.2 | สร้างโปรส่งฟรี | type: free_shipping, condition: ซื้อครบ 1,000+, code: null | `data/promotions.json` |
| 2.3.3 | สร้างโปรโค้ด NEWBIE10 | type: percentage_discount, discount: 10%, max: 200 บาท, code: "NEWBIE10", condition: ลูกค้าใหม่ครั้งแรก | `data/promotions.json` |
| 2.3.4 | เพิ่ม AI rules ใน JSON | เพิ่ม field `ai_rules`: max_discount 15%, cannot_create_new_promo: true, must_state_conditions: true | `data/promotions.json` |

### Task 2.4: สร้าง Sale Script
> **ทำอะไร**: สร้าง Workflow การขาย 6 ขั้นตอน พร้อม prompt template แต่ละ stage
> **ทำอย่างไร**: เขียน JSON array 6 objects ตาม Sale Script schema — สไตล์เป็นมิตร คุยเหมือนเพื่อน

| Step | ทำอะไร | วิธีทำ | ไฟล์ |
|------|--------|--------|------|
| 2.4.1 | สร้าง Stage 1: ทักทาย | goal: สร้างความเป็นกันเอง, prompt: ทักทายเป็นมิตร ถามมองหาอะไร, transition: เมื่อลูกค้าบอกความต้องการ, tools: [] | `data/sale_script.json` |
| 2.4.2 | สร้าง Stage 2: ถามความต้องการ | goal: เข้าใจสิ่งที่ลูกค้าต้องการ, prompt: ถามสไตล์/โอกาส/งบ, transition: เมื่อเข้าใจความต้องการชัดแล้ว, tools: [] | `data/sale_script.json` |
| 2.4.3 | สร้าง Stage 3: นำเสนอสินค้า | goal: แนะนำสินค้าที่เหมาะ, prompt: แนะนำ 2-3 ชิ้นพร้อมเหตุผล+ราคา, transition: เมื่อลูกค้าสนใจตัวใดตัวหนึ่ง, tools: [search_products, check_stock] | `data/sale_script.json` |
| 2.4.4 | สร้าง Stage 4: จัดการ Objection | goal: ตอบข้อกังวล, prompt: เข้าใจก่อน→ให้ข้อมูล→เสนอทางเลือก, transition: เมื่อลูกค้าพร้อมซื้อ, tools: [calculate_price] | `data/sale_script.json` |
| 2.4.5 | สร้าง Stage 5: ปิดการขาย | goal: สรุปออเดอร์+ช่องทางจ่าย, prompt: สรุปรายการ+ราคา+ส่วนลด ถามยืนยัน, transition: เมื่อลูกค้ายืนยัน, tools: [calculate_price, create_order] | `data/sale_script.json` |
| 2.4.6 | สร้าง Stage 6: Follow-up | goal: ขอบคุณ+เปิดช่องทางติดต่อ, prompt: ขอบคุณ+แจ้งติดตามสถานะได้, transition: จบสนทนา, tools: [check_delivery_status] | `data/sale_script.json` |

### Task 2.5: สร้าง Guardrails
> **ทำอะไร**: สร้างกฎป้องกัน 6 ด้าน พร้อม detection keywords และ fallback messages
> **ทำอย่างไร**: เขียน JSON array 6 objects + human handoff config ตาม Guardrail schema

| Step | ทำอะไร | วิธีทำ | ไฟล์ |
|------|--------|--------|------|
| 2.5.1 | สร้างกฎ: ห้ามการเมือง/ศาสนา | keywords: ["การเมือง", "พรรค", "เลือกตั้ง", "ศาสนา", "วัด", "โบสถ์"], action: redirect_to_product, fallback: "ขอโทษค่ะ เรื่องนี้ตอบไม่ได้..." | `data/guardrails.json` |
| 2.5.2 | สร้างกฎ: ห้ามข้อมูลเท็จ | rule: ถ้าไม่รู้ให้บอกตรงๆ, action: escalate_to_admin, fallback: "อันนี้ไม่แน่ใจค่ะ ขอเช็คกับทีม..." | `data/guardrails.json` |
| 2.5.3 | สร้างกฎ: ห้ามพูดหยาบ | rule: สุภาพเสมอไม่ว่าลูกค้าพูดอะไร, action: de_escalate, fallback: "เข้าใจค่ะ ขอโทษที่ทำให้ไม่พอใจ..." | `data/guardrails.json` |
| 2.5.4 | สร้างกฎ: จำกัดส่วนลด | rule: ไม่เกิน 15% ห้ามสร้างโปรใหม่, action: offer_existing_promo, fallback: "ตอนนี้โปรที่มีคือ..." | `data/guardrails.json` |
| 2.5.5 | สร้างกฎ: ห้ามแนะนำคู่แข่ง | keywords: ["ร้านอื่น", "แบรนด์อื่น", "Uniqlo", "H&M", "Zara"], action: redirect_to_own_product, fallback: "ขอแนะนำเฉพาะสินค้าของร้านเรา..." | `data/guardrails.json` |
| 2.5.6 | สร้างกฎ: ห้ามนอกเรื่อง | keywords: ["การบ้าน", "สอนเขียนโค้ด", "ข่าว", "หวย"], action: redirect_to_product, fallback: "ช่วยได้เฉพาะเรื่องเสื้อผ้าของร้าน..." | `data/guardrails.json` |
| 2.5.7 | สร้าง Human Handoff config | triggers: ลูกค้าขอคุยกับคนจริง 2 ครั้ง / ลูกค้าโกรธรุนแรง / AI ตอบไม่ได้ 3 ครั้งติด, message: "ขอส่งต่อให้แอดมินดูแลต่อนะคะ รอสักครู่ค่ะ" | `data/guardrails.json` |

### Task 2.6: สร้าง Test Cases
> **ทำอะไร**: สร้างชุดทดสอบ 15 สถานการณ์ ใน 5 กลุ่ม พร้อมเกณฑ์ให้คะแนน
> **ทำอย่างไร**: เขียน JSON array — แต่ละ case มี id, group, scenario, user_input, expected_output, evaluation_criteria

| Step | ทำอะไร | วิธีทำ | ไฟล์ |
|------|--------|--------|------|
| 2.6.1 | สร้าง Happy Path 5 cases | Case 1-5: ถามราคา, สั่งซื้อ, เช็คสต็อก, ถามค่าส่ง, ใช้โค้ดลด — ระบุ input + expected output + criteria ของแต่ละ case | `data/test_cases.json` |
| 2.6.2 | สร้าง Edge Cases 3 cases | Case 6-8: ต่อราคา, สินค้าหมด, เทียบร้านอื่น — ระบุ expected behavior ที่ AI ต้องจัดการ | `data/test_cases.json` |
| 2.6.3 | สร้าง Guardrail Tests 3 cases | Case 9-11: ถามการเมือง, ลูกค้าด่า, ขอลด 50% — ระบุ guardrail rule ที่ต้อง trigger | `data/test_cases.json` |
| 2.6.4 | สร้าง Multi-turn Tests 2 cases | Case 12-13: ถาม 3 สินค้าต่อเนื่อง, เปลี่ยนใจ — ระบุ conversation history ที่ต้องจำ | `data/test_cases.json` |
| 2.6.5 | สร้าง Tool Calling Tests 2 cases | Case 14-15: สั่ง 2 ชิ้น+โค้ดลด, ถามสถานะจัดส่ง — ระบุลำดับ tool calls ที่คาดหวัง | `data/test_cases.json` |
| 2.6.6 | สร้าง Evaluation Criteria | เพิ่ม scoring config: Accuracy 30%, Guardrail Compliance 25%, Tool Usage 20%, Tone 15%, Hallucination 10% | `data/test_cases.json` |

---

## Phase 3: Notebook Development — สร้าง Jupyter Notebooks

### Task 3.1: Notebook Module 1 — System Prompt & Context Engineering
> **ทำอะไร**: สร้าง Notebook สอนการออกแบบ System Prompt และจัดการ Context
> **ทำอย่างไร**: เขียน Notebook แบบ step-by-step มี Markdown อธิบาย + Code cells ให้รัน
> **ไฟล์**: `notebooks/01_system_prompt.ipynb`

| Step | ทำอะไร | วิธีทำ | Cell |
|------|--------|--------|------|
| 3.1.1 | Introduction | อธิบาย: System Prompt คืออะไร ทำไมสำคัญ บทบาทในการขาย | MD |
| 3.1.2 | Setup | `pip install openai python-dotenv` + load API key จาก `.env` + สร้าง OpenAI client | Code |
| 3.1.3 | Basic System Prompt | เขียน System Prompt แบบง่าย: "คุณคือพนักงานขายร้านเสื้อผ้า" → ทดสอบส่งข้อความ → ดูผลลัพธ์ | Code |
| 3.1.4 | อธิบาย Component | สอน 5 ส่วน: Role, Personality, Goal, Constraints, Tone — อธิบายแต่ละส่วนทำหน้าที่อะไร | MD |
| 3.1.5 | Advanced System Prompt | เขียน System Prompt ฉบับเต็ม: รวม role (พนักงานขายร้าน FASHIONISTA), personality (เป็นมิตร ค่ะ/นะคะ), goal (ปิดการขาย), constraints (ห้ามพูดนอกเรื่อง), tone (เหมือนเพื่อน) → ทดสอบ | Code |
| 3.1.6 | อธิบาย Context Engineering | สอน: อะไรต้องส่งเสมอ (system prompt + product info), อะไรส่งตามสถานการณ์ (sale stage + promo), อะไรตัดได้ (ประวัติเก่า) | MD |
| 3.1.7 | Context Assembly Demo | สร้าง function `build_context()` ที่รับ: system_prompt + product_data + faq + current_stage + conversation_history → ประกอบเป็น messages array → ทดสอบ token count | Code |
| 3.1.8 | เปรียบเทียบ | เปรียบเทียบ: Basic vs Advanced prompt → ส่งคำถามเดียวกัน 3 ข้อ → ดูความแตกต่างของคำตอบ | Code |
| 3.1.9 | แบบฝึกหัด | ให้ผู้เรียนลองปรับ System Prompt ของตัวเอง เปลี่ยน personality/tone → ทดสอบ → เปรียบเทียบผล | MD+Code |

### Task 3.2: Notebook Module 2 — RAG & Data Structure
> **ทำอะไร**: สร้าง Notebook สอนการสร้าง Knowledge Base ด้วย RAG
> **ทำอย่างไร**: โหลดข้อมูลสินค้า+FAQ → สร้าง embeddings → เก็บใน ChromaDB → สร้าง retrieval pipeline
> **ไฟล์**: `notebooks/02_rag_knowledge_base.ipynb`

| Step | ทำอะไร | วิธีทำ | Cell |
|------|--------|--------|------|
| 3.2.1 | Introduction | อธิบาย: RAG คืออะไร ทำไมต้องใช้ (ไม่ต้องท่องจำ ข้อมูลอัปเดตได้ ลด hallucination) | MD |
| 3.2.2 | Setup | `pip install chromadb` + import libraries | Code |
| 3.2.3 | โหลดข้อมูลสินค้า | โหลด `data/products.json` → แสดง schema → อธิบาย fields | Code |
| 3.2.4 | โหลด FAQ | โหลด `data/faq.json` + `data/policies.md` → แสดงตัวอย่าง | Code |
| 3.2.5 | อธิบาย Embedding | สอน: text → vector คืออะไร, ทำไม similar text → similar vectors, OpenAI embedding model | MD |
| 3.2.6 | สร้าง Product Collection | สร้าง ChromaDB collection "products" — แปลงสินค้าเป็น documents (name+description+price+colors+sizes) → embed → เก็บ | Code |
| 3.2.7 | สร้าง FAQ Collection | สร้าง collection "faq" — แปลง question+answer เป็น documents → embed → เก็บ | Code |
| 3.2.8 | ทดสอบค้นหาสินค้า | query: "อยากได้เสื้อใส่สบายๆ" → ดูผลลัพธ์ top 3 → อธิบาย relevance score | Code |
| 3.2.9 | ทดสอบค้นหา FAQ | query: "ส่งกี่วัน", "คืนสินค้ายังไง" → ดูว่าดึง FAQ ถูกข้อหรือไม่ | Code |
| 3.2.10 | สร้าง Retrieval Pipeline | สร้าง `retrieve_context(query, top_k=3)`: ค้นทั้ง products + faq → รวมผล → format เป็น string พร้อมใส่ prompt | Code |
| 3.2.11 | RAG + LLM Integration | สร้าง `rag_chat(user_message)`: retrieve context → inject เข้า system prompt → ส่ง LLM → แสดงคำตอบ | Code |
| 3.2.12 | แบบฝึกหัด | ให้ผู้เรียนถามคำถามหลายแบบ → ดูว่า RAG ดึงข้อมูลถูกหรือไม่ → ปรับ top_k | MD+Code |

### Task 3.3: Notebook Module 3 — Tool Call / Function Calling
> **ทำอะไร**: สร้าง Notebook สอน OpenAI Function Calling + implement mock tools 4 ตัว
> **ทำอย่างไร**: สอน concept → define function schema → implement functions → ทดสอบ AI เรียก tools
> **ไฟล์**: `notebooks/03_tool_calling.ipynb`

| Step | ทำอะไร | วิธีทำ | Cell |
|------|--------|--------|------|
| 3.3.1 | Introduction | อธิบาย: Function Calling คืออะไร AI ตัดสินใจเรียก tool เอง แล้วได้ผลลัพธ์กลับมาตอบลูกค้า | MD |
| 3.3.2 | Define: `check_stock` | JSON schema: params = product_id, size, color → return จำนวนสต็อก | Code |
| 3.3.3 | Define: `calculate_price` | JSON schema: params = product_id, quantity, promo_code (optional) → return ราคารวม+ส่วนลด | Code |
| 3.3.4 | Define: `create_order` | JSON schema: params = product_id, size, color, quantity, customer_name, address → return order_id + summary | Code |
| 3.3.5 | Define: `check_delivery_status` | JSON schema: params = order_id → return สถานะจัดส่ง + tracking number | Code |
| 3.3.6 | Implement mock functions | เขียน Python functions 4 ตัวอ่านจาก `products.json` + `promotions.json` → return ผลลัพธ์ (create_order → generate order_id) | Code |
| 3.3.7 | รวม tools เป็น array | สร้าง `tools` list + `tool_functions` dict สำหรับ mapping ชื่อ tool → function | Code |
| 3.3.8 | ทดสอบ Function Calling | ส่ง "มีเสื้อยืดไซส์ L มั้ย" → ดูว่า AI เรียก check_stock → ได้ผล → ตอบลูกค้า | Code |
| 3.3.9 | Tool Calling Loop | สร้าง `chat_with_tools(user_message)`: ส่ง LLM → ถ้า AI เรียก tool → execute → ส่งผลกลับ LLM → loop จนได้คำตอบ | Code |
| 3.3.10 | ทดสอบ scenario สั่งซื้อ | "สั่งเสื้อยืด สีขาว ไซส์ M 1 ตัว" → AI เรียก check_stock → calculate_price → create_order ถูกลำดับ | Code |
| 3.3.11 | แบบฝึกหัด | ให้ผู้เรียนเพิ่ม tool ใหม่ เช่น `search_products` → ทดสอบ | MD+Code |

### Task 3.4: Notebook Module 4 — Workflow & Guardrail
> **ทำอะไร**: สร้าง Notebook สอนการสร้าง Sale Flow state machine + Guardrail system
> **ทำอย่างไร**: โหลด sale_script + guardrails → สร้าง state manager → สร้าง guardrail checker → รวมเข้าด้วยกัน
> **ไฟล์**: `notebooks/04_workflow_guardrail.ipynb`

| Step | ทำอะไร | วิธีทำ | Cell |
|------|--------|--------|------|
| 3.4.1 | Introduction | อธิบาย: Sale Workflow + Guardrail ทำไมต้องมีทั้งสอง | MD |
| 3.4.2 | โหลด Sale Script | โหลด `data/sale_script.json` → แสดง 6 stages → อธิบาย flow | Code |
| 3.4.3 | สร้าง SaleWorkflow class | class: current_stage, transition logic (ตรวจว่าควรเปลี่ยน stage), get_stage_prompt() return prompt template ของ stage ปัจจุบัน | Code |
| 3.4.4 | ทดสอบ Workflow | จำลองสนทนา 6 turn → ดูว่า stage เปลี่ยนถูกต้อง | Code |
| 3.4.5 | โหลด Guardrails | โหลด `data/guardrails.json` → แสดงกฎทั้ง 6 ด้าน | Code |
| 3.4.6 | สร้าง GuardrailChecker class | class: check_input(message) → ตรวจ keyword → return {is_safe, violated_rule, fallback_message}, check_output(response) → ตรวจว่า AI ไม่ละเมิดกฎ | Code |
| 3.4.7 | สร้าง Human Handoff logic | function: ตรวจ triggers (ขอคุยคนจริง 2 ครั้ง / โกรธ / ตอบไม่ได้ 3 ครั้ง) → return should_handoff + message | Code |
| 3.4.8 | รวม Workflow + Guardrail | `guarded_chat(message)`: check_input → safe? → get stage prompt → LLM → check_output → transition stage → return response | Code |
| 3.4.9 | ทดสอบ Guardrail | ถามการเมือง → ปฏิเสธ, ขอลด 50% → ปฏิเสธ, ถามเสื้อผ้า → ตอบปกติ | Code |
| 3.4.10 | แบบฝึกหัด | ให้ผู้เรียนเพิ่ม guardrail rule ใหม่ เช่น ห้ามให้ข้อมูลส่วนตัวร้าน → ทดสอบ | MD+Code |

### Task 3.5: Notebook Module 5 — Memory & Error Handling
> **ทำอะไร**: สร้าง Notebook สอน Short/Long-term Memory + Error Handling
> **ทำอย่างไร**: สร้าง memory store → implement retry/fallback → human handoff
> **ไฟล์**: `notebooks/05_memory_error_handling.ipynb`

| Step | ทำอะไร | วิธีทำ | Cell |
|------|--------|--------|------|
| 3.5.1 | Introduction | อธิบาย: Short-term (ภายในสนทนา) vs Long-term (ข้ามสนทนา) + Error Handling | MD |
| 3.5.2 | Short-term Memory | class `ConversationMemory`: messages list, add_message(), get_history(), summarize_if_long() (LLM สรุปเมื่อ history > 20 messages) | Code |
| 3.5.3 | ทดสอบ Short-term | จำลอง 5 turns → memory เก็บครบ → ถาม "เมื่อกี้คุยอะไร" → สรุปได้ | Code |
| 3.5.4 | Long-term Memory | class `CustomerMemory`: customer profiles dict (ชื่อ, สินค้าที่สนใจ, ไซส์, ประวัติสั่งซื้อ), save_to_json(), load_from_json() | Code |
| 3.5.5 | ทดสอบ Long-term | ลูกค้าบอกชื่อ+ไซส์ → save → session ใหม่ → load → AI ทักด้วยชื่อ+แนะนำตาม size | Code |
| 3.5.6 | Error Handling: Retry | `safe_llm_call(messages, max_retries=3)`: try → API error → retry exponential backoff → ครบ 3 ครั้ง → fallback message | Code |
| 3.5.7 | Error Handling: Fallback | fallback messages: API timeout, invalid response, unknown error → ตอบสุภาพ + แจ้งให้รอ | Code |
| 3.5.8 | Human Handoff Demo | จำลอง: AI ตอบไม่ได้ 3 ครั้ง → trigger handoff → แสดง "ขอส่งต่อให้แอดมิน" | Code |
| 3.5.9 | แบบฝึกหัด | ให้ผู้เรียนเพิ่ม field ใน customer profile / เปลี่ยน summarization strategy | MD+Code |

### Task 3.6: Notebook Module 7 — Evaluation & Extras
> **ทำอะไร**: สร้าง Notebook สำหรับรัน test cases + demo Multimodal + overview MCP/Versioning
> **ทำอย่างไร**: โหลด test cases → รันทดสอบอัตโนมัติ → คำนวณคะแนน + demo Vision API
> **ไฟล์**: `notebooks/07_evaluation_extras.ipynb`

| Step | ทำอะไร | วิธีทำ | Cell |
|------|--------|--------|------|
| 3.6.1 | Introduction | อธิบาย: ทำไมต้อง evaluate AI, เกณฑ์วัดผล 5 ด้าน | MD |
| 3.6.2 | โหลด Test Cases | โหลด `data/test_cases.json` → แสดงจำนวน case แต่ละกลุ่ม | Code |
| 3.6.3 | สร้าง Evaluator | `evaluate_response(test_case, actual_response)` → LLM ตรวจ 5 เกณฑ์ → score 0-10 + weighted total | Code |
| 3.6.4 | รัน Test Suite | Loop ทุก case → ส่ง input เข้า chatbot → evaluate → เก็บผล → summary table | Code |
| 3.6.5 | วิเคราะห์ผล | overall score, score แต่ละกลุ่ม, จุดอ่อน → สอนวิธีอ่านผลและปรับปรุง | Code+MD |
| 3.6.6 | Multimodal Demo | OpenAI Vision API: ส่งรูปเสื้อผ้า → AI อธิบายสินค้าจากรูป → demo รับ input รูปจากลูกค้า | Code |
| 3.6.7 | MCP Overview | อธิบาย: MCP คืออะไร, เชื่อม CRM/สต็อก/จัดส่งอย่างไร, architecture diagram | MD |
| 3.6.8 | Prompt Versioning Overview | อธิบาย: ทำไมต้อง version prompt, naming (v1.0, v1.1), changelog, A/B test | MD |

---

## Phase 4: Streamlit App — สร้าง Chat Application

### Task 4.1: สร้าง Configuration
> **ทำอะไร**: สร้างไฟล์ config ที่รวม System Prompt + settings ทั้งหมด
> **ทำอย่างไร**: รวม prompt, model settings, paths ไว้ที่เดียว
> **ไฟล์**: `app/config.py`

| Step | ทำอะไร | วิธีทำ |
|------|--------|--------|
| 4.1.1 | สร้าง config.py | เขียน: SYSTEM_PROMPT (ฉบับเต็ม), MODEL_NAME ("gpt-4o"), DATA_DIR path, MAX_HISTORY_LENGTH (20), MAX_RETRIES (3) |

### Task 4.2: สร้าง Utility Functions
> **ทำอะไร**: สร้าง shared functions ที่ Streamlit app เรียกใช้
> **ทำอย่างไร**: รวม functions จาก Notebooks ทั้งหมดเข้าด้วยกัน (RAG, Tools, Workflow, Guardrail, Memory)
> **ไฟล์**: `app/utils.py`

| Step | ทำอะไร | วิธีทำ |
|------|--------|--------|
| 4.2.1 | Data loading functions | `load_products()`, `load_faq()`, `load_promotions()`, `load_sale_script()`, `load_guardrails()` — อ่านจาก `data/` |
| 4.2.2 | RAG functions | `init_vector_store()` (สร้าง ChromaDB), `retrieve_context(query, top_k)` (ค้นหาสินค้า+FAQ) |
| 4.2.3 | Tool functions | `check_stock()`, `calculate_price()`, `create_order()`, `check_delivery_status()` + `TOOLS_SCHEMA` + `execute_tool(name, args)` dispatcher |
| 4.2.4 | Workflow & Guardrail | `SaleWorkflow` class + `GuardrailChecker` class (production-ready version จาก Notebook) |
| 4.2.5 | Memory functions | `ConversationMemory` class + `CustomerMemory` class |
| 4.2.6 | Chat orchestrator | `process_message(user_message, session_state)`: guardrail check → retrieve context → get stage prompt → build messages → call LLM with tools → handle tool calls → guardrail check output → update memory → update workflow → return response |

### Task 4.3: สร้าง Streamlit Chat App
> **ทำอะไร**: สร้าง Chat UI ด้วย Streamlit ที่รวมทุก module
> **ทำอย่างไร**: ใช้ `st.chat_message` + `st.chat_input` + session_state สำหรับ memory/workflow
> **ไฟล์**: `app/chatbot.py`

| Step | ทำอะไร | วิธีทำ |
|------|--------|--------|
| 4.3.1 | Page config + sidebar | page_title "FASHIONISTA Chatbot", sidebar: current sale stage, active promotions, reset button |
| 4.3.2 | Initialize session state | `st.session_state`: messages=[], workflow=SaleWorkflow(), memory=ConversationMemory(), customer=CustomerMemory(), vector_store=init_vector_store() |
| 4.3.3 | Display chat history | Loop `st.session_state.messages` → `st.chat_message(role)` |
| 4.3.4 | Handle user input | `st.chat_input()` → `process_message()` → แสดง response → อัปเดต sidebar |
| 4.3.5 | Tool Call indicators | เมื่อ AI เรียก tool → spinner + "กำลังเช็คสต็อก..." / "กำลังสร้างออเดอร์..." |
| 4.3.6 | Reset & Debug panel | Reset: ล้าง session state, Debug (expandable): current context, tool calls log, stage history |

---

## Phase 5: Testing & Verification — ทดสอบทั้งระบบ

### Task 5.1: ทดสอบ Data Files
> **ทำอะไร**: ตรวจว่าไฟล์ข้อมูลทั้ง 7 ไฟล์ถูกต้อง โหลดได้ ไม่มี syntax error
> **ทำอย่างไร**: รัน validation script หรือ cell ใน Notebook

| Step | ทำอะไร | วิธีทำ |
|------|--------|--------|
| 5.1.1 | Validate JSON files | โหลดทุก .json → ตรวจ parse ได้ → ตรวจจำนวน records (products 12, faq 18, promotions 3, sale_script 6, guardrails 6, test_cases 15) |
| 5.1.2 | ตรวจ cross-reference | test cases อ้าง product_id ที่มีจริง, promo code ตรงกับ promotions.json, guardrail keywords ไม่ซ้ำ |
| 5.1.3 | ตรวจ policies.md | ข้อมูลสอดคล้องกับ FAQ answers |

### Task 5.2: ทดสอบ Notebooks
> **ทำอะไร**: รันทุก Notebook ตั้งแต่ต้นจนจบ ตรวจว่าไม่มี error
> **ทำอย่างไร**: รันทีละ Notebook ตามลำดับ (ต้องมี OpenAI API key)

| Step | ทำอะไร | วิธีทำ |
|------|--------|--------|
| 5.2.1 | รัน Module 1 | 01_system_prompt.ipynb ครบทุก cell → LLM ตอบภาษาไทย สไตล์เป็นมิตร |
| 5.2.2 | รัน Module 2 | 02_rag_knowledge_base.ipynb → ChromaDB สร้างได้ + ค้นหาถูกต้อง |
| 5.2.3 | รัน Module 3 | 03_tool_calling.ipynb → AI เรียก tools ถูกตัว + ผลลัพธ์ถูก |
| 5.2.4 | รัน Module 4 | 04_workflow_guardrail.ipynb → workflow เปลี่ยน stage + guardrail block ได้ |
| 5.2.5 | รัน Module 5 | 05_memory_error_handling.ipynb → memory จำได้ + error handling ทำงาน |
| 5.2.6 | รัน Module 7 | 07_evaluation_extras.ipynb → test cases รันได้ + Multimodal demo ทำงาน |

### Task 5.3: ทดสอบ Streamlit App
> **ทำอะไร**: รัน Streamlit app + ทดสอบ end-to-end scenarios
> **ทำอย่างไร**: `streamlit run app/chatbot.py` → ทดสอบตาม test cases

| Step | ทำอะไร | วิธีทำ |
|------|--------|--------|
| 5.3.1 | รัน app สำเร็จ | `streamlit run app/chatbot.py` → เปิดหน้า chat ได้ → sidebar แสดงข้อมูลถูก |
| 5.3.2 | ทดสอบ Happy Path | ถามราคา → แนะนำสินค้า → สั่งซื้อ → ปิดการขาย → workflow stage เปลี่ยนถูก |
| 5.3.3 | ทดสอบ Guardrails | ถามการเมือง → ปฏิเสธ, ขอลด 50% → ปฏิเสธ, ถามนอกเรื่อง → redirect |
| 5.3.4 | ทดสอบ Multi-turn | คุย 5+ turns → bot จำบริบทได้ → เปลี่ยนใจ → bot ปรับได้ |
| 5.3.5 | ทดสอบ Reset | กด Reset → ล้างทุกอย่าง → เริ่มใหม่ได้ |

---

## Verification Checklist

- [ ] `pip install -r requirements.txt` สำเร็จไม่มี error
- [ ] ทุก JSON file โหลดได้ + จำนวน records ถูกต้อง
- [ ] ทุก Notebook รันครบทุก cell ไม่มี error
- [ ] `streamlit run app/chatbot.py` เปิดได้ + chat ได้
- [ ] Happy Path: ถามราคา → แนะนำ → สั่งซื้อ → ปิดการขายสำเร็จ
- [ ] Guardrail: ถามนอกเรื่อง → ปฏิเสธสุภาพ
- [ ] Guardrail: ขอส่วนลดเกิน 15% → ปฏิเสธ + แจ้งโปรที่มี
- [ ] Tool Calling: เช็คสต็อก + คำนวณราคา + สร้าง order ถูกลำดับ
- [ ] Multi-turn: bot จำบริบทได้ข้ามหลายรอบ
- [ ] รัน 15 test cases ผ่านเกณฑ์ให้คะแนน
