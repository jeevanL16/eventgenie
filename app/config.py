"""Configuration settings for EventGenie."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def get_setting(key: str, default: str = "") -> str:
    """Retrieve setting from environment variables first, then Streamlit secrets."""
    val = os.getenv(key)
    if val:
        return val

    # Fallback to Streamlit secrets (safe when running locally or on Streamlit Cloud)
    try:
        import streamlit as st

        if hasattr(st, "secrets"):
            try:
                if key in st.secrets:
                    secret_val = st.secrets[key]
                    if secret_val is not None:
                        return str(secret_val)
            except Exception:
                pass
    except Exception:
        pass

    return default


# Alias for backward compatibility
_get_setting = get_setting


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
