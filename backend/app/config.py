"""
Centralized settings loader.

Every other file that needs an environment variable (GROQ_API_KEY, DATABASE_URL, etc.)
should import `settings` from here instead of calling os.environ directly.
That way there's exactly ONE place that knows how config is loaded.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Always load backend/.env, even when uvicorn is started from the project root.
BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=True)


class Settings:
    # Groq LLM settings
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip().strip('"').strip("'")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./leadpilot.db")

    # CORS - comma-separated string in .env, turned into a real Python list here
    ALLOW_ORIGINS: list[str] = os.getenv("ALLOW_ORIGINS", "http://localhost:8501").split(",")

    # RAG / vector store
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")

    # Public website enrichment is optional. CSV data remains the reliable base.
    ENABLE_WEB_ENRICHMENT: bool = os.getenv("ENABLE_WEB_ENRICHMENT", "true").lower() == "true"


# A single shared instance every other file will import:
#   from app.config import settings
#   settings.GROQ_API_KEY
settings = Settings()


# Small safety check: warn (don't crash) if the key is missing, since it's easy to forget.
if not settings.GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY is not set. Add it to your .env file.")
