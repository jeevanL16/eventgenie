"""Configuration settings for EventGenie."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _get_setting(key: str, default: str = "") -> str:
    """Retrieve setting from environment or Streamlit secrets with fallback."""
    val = os.getenv(key)
    if not val:
        try:
            import streamlit as st

            if hasattr(st, "secrets") and key in st.secrets:
                val = str(st.secrets[key])
        except Exception:
            pass
    return val if val is not None else default


# LLM provider settings
LLM_PROVIDER = _get_setting("LLM_PROVIDER", "router").lower()
LLM_CHAIN = _get_setting("LLM_CHAIN", "groq,gemini")

# Gemini configuration
GEMINI_API_KEY = _get_setting("GEMINI_API_KEY", "")
GEMINI_MODEL = _get_setting("GEMINI_MODEL", "gemini-flash-lite-latest")

# Groq configuration
GROQ_API_KEY = _get_setting("GROQ_API_KEY", "")
GROQ_MODEL = _get_setting("GROQ_MODEL", "qwen/qwen3.8-27b")

# Ollama configuration (local offline inference; disabled by default in cloud)
OLLAMA_BASE_URL = _get_setting("OLLAMA_BASE_URL", "")
OLLAMA_MODEL = _get_setting("OLLAMA_MODEL", "llama3.2")

# Default network / retry parameters
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30.0"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
