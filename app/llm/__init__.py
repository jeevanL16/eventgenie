"""LLM package exports and provider factory."""

from app import config
from app.llm.base import (
    LLM,
    LLMAuthError,
    LLMError,
    LLMMetadata,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMValidationError,
)
from app.llm.gemini import GeminiLLM
from app.llm.groq import GroqLLM


def get_llm(provider: str | None = None) -> LLM:
    """Return an instantiated LLM client based on provider name or configuration."""
    selected_provider = (provider or config.LLM_PROVIDER).lower()
    if selected_provider == "gemini":
        return GeminiLLM()
    elif selected_provider == "groq":
        return GroqLLM()
    else:
        raise ValueError(
            f"Unsupported LLM provider: '{selected_provider}'. Supported providers: 'gemini', 'groq'."
        )


__all__ = [
    "LLM",
    "LLMAuthError",
    "LLMError",
    "LLMMetadata",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "LLMValidationError",
    "GeminiLLM",
    "GroqLLM",
    "get_llm",
]
