"""Base protocol and data structures for LLM providers."""

from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMMetadata:
    """Metadata recorded for an LLM generation call."""

    model: str
    latency_ms: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    raw_response: str = ""


class LLMError(Exception):
    """Base exception for LLM operations."""


class LLMAuthError(LLMError):
    """Raised when authentication/API key is missing or invalid."""


class LLMRateLimitError(LLMError):
    """Raised when provider rate limit is exceeded (HTTP 429)."""


class LLMTimeoutError(LLMError):
    """Raised when an LLM call exceeds the allowed timeout."""


class LLMValidationError(LLMError):
    """Raised when LLM output cannot be parsed or validated against the Pydantic schema."""

    def __init__(self, message: str, raw_response: str = ""):
        super().__init__(message)
        self.raw_response = raw_response


class LLM(Protocol):
    """Protocol defining the standard LLM interface for EventGenie."""

    last_metadata: LLMMetadata | None

    def generate_json(
        self,
        system: str,
        prompt: str,
        schema: type[T],
        temperature: float = 0.3,
    ) -> T:
        """Generate structured output validated against a Pydantic schema."""
        ...

    def generate_text(
        self,
        system: str,
        prompt: str,
        temperature: float = 0.7,
    ) -> str:
        """Generate unstructured free text."""
        ...
