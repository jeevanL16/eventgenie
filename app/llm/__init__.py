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


def get_llm(provider: str | None = None) -> LLM:
    """Return an instantiated LLM client based on provider name or configuration."""
    selected_provider = (provider or config.LLM_PROVIDER).lower()
    if selected_provider == "gemini":
        return GeminiLLM()
    elif selected_provider == "groq":
        # Placeholder until T-33
        raise NotImplementedError(
            "Groq provider is scheduled for implementation in T-33. Use LLM_PROVIDER=gemini."
        )
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
    "get_llm",
]
