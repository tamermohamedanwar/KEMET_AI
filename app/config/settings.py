import os
import secrets
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY and os.getenv("FLASK_ENV", "development") != "production":
    SECRET_KEY = secrets.token_hex(32)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///supportai.db")

AI_PROVIDER = os.getenv("AI_PROVIDER", "openrouter")
MODEL_NAME = os.getenv("MODEL_NAME", "openai/gpt-4o-mini")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
CODECRAFT_API_KEY = os.getenv("CODECRAFT_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

AI_PRIMARY_PROVIDER = os.getenv("AI_PRIMARY_PROVIDER", "openai")
AI_REQUIRED_CAPABILITIES = os.getenv("AI_REQUIRED_CAPABILITIES", "reasoning")
CODECRAFT_MODEL = os.getenv("CODECRAFT_MODEL", "gpt-5.6-sol")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.8-flash"))
XAI_MODEL = os.getenv("XAI_MODEL", "grok-4.6")
