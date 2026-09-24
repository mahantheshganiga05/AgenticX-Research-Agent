"""Application configuration and environment settings.

Provides clean access to API keys, model choices, and agent step limits.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if present
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


class Config:
    """Central configuration class."""

    # API Keys
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "").strip()

    # Gemini Model
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash").strip()


    # Agent Constraints (Hard Step Limit required by AgenticX)
    MAX_AGENT_STEPS: int = int(os.getenv("MAX_AGENT_STEPS", "6"))

    # Tool Parameters
    DEFAULT_SEARCH_MAX_RESULTS: int = 4
    FETCH_PAGE_MAX_CHARS: int = 2500
    HTTP_TIMEOUT_SECONDS: float = 12.0

    # Server Settings
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))


config = Config()
