"""Shared configuration for Guardrail Proxy."""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
AGENT_API_URL = os.getenv("AGENT_API_URL", "http://localhost:3000/chat")
GUARDRAIL_PORT = int(os.getenv("GUARDRAIL_PORT", "8002"))

# Similarity threshold — messages scoring below this are blocked
VECTOR_SIMILARITY_THRESHOLD = float(os.getenv("VECTOR_SIMILARITY_THRESHOLD", "0.45"))

# Model config
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
POLICY_MODEL = "gpt-4o-mini"

openai_client = OpenAI(api_key=OPENAI_API_KEY)
