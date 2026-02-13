- ให้ดูการแก้ไขทั้งหมดในโปรเจ็คนี้แล้วให้ commit พร้อมคำอธิบายสั้นๆ แล้ว push

วิเคราะห์ทั้งโปรเจ็คนี้แล้ว Create proxy api in guardrail folder before we send the prompt to chatbot. This proxy api will handle the incoming topic and determind which user query will be pass to chatbot or not. key component for determind is have 2 systems.                       
1. Vectory similarity (use for allow topic)                                                                                  
2. LLM policy (use for determind the incoming request is follow by our policy and topic or not)                                                                                    
The request MUST pass both system.