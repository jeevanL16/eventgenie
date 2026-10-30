"""Groq LLM provider implementation using the official Groq SDK (OpenAI-compatible).

Supports structured JSON output and plain text generation with retry/exponential backoff,
timeout handling, token accounting, and latency telemetry.
"""

import json
import logging
import random
import re
import time
from collections.abc import Callable
from typing import Any, TypeVar

import groq
from pydantic import BaseModel, ValidationError

from app import config
from app.llm.base import (
    LLMAuthError,
    LLMError,
    LLMMetadata,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMValidationError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class GroqLLM:
    """Groq API client adhering to the LLM protocol."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        initial_delay: float = 1.0,
        backoff_multiplier: float = 2.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else config.GROQ_API_KEY
        self.model_name = model_name or config.GROQ_MODEL
        self.timeout = timeout if timeout is not None else config.LLM_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else config.LLM_MAX_RETRIES
        self.initial_delay = initial_delay
        self.backoff_multiplier = backoff_multiplier
        self.last_metadata: LLMMetadata | None = None

        self._client: groq.Groq | None = None
        if self.api_key:
            self._client = groq.Groq(
                api_key=self.api_key,
                timeout=self.timeout,
            )

    def _ensure_authenticated(self) -> None:
        if not self.api_key:
            raise LLMAuthError(
                "GROQ_API_KEY is not configured. Please set GROQ_API_KEY in your .env file or UI."
            )
        if self._client is None:
            raise LLMAuthError("Groq client not initialized. Check API key configuration.")

    @staticmethod
    def _clean_json_text(text: str) -> str:
        """Strip markdown code fence blocks if present."""
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    def _classify_error(self, e: Exception) -> None:
        """Map Groq API exceptions to the standard LLM exception hierarchy."""
        if isinstance(e, groq.AuthenticationError):
            raise LLMAuthError(f"Groq authentication failed: {e}") from e
        if isinstance(e, groq.APITimeoutError):
            raise LLMTimeoutError(f"Groq request timed out: {e}") from e
        if isinstance(e, groq.RateLimitError):
            raise LLMRateLimitError(f"Groq rate limit exceeded: {e}") from e
        if isinstance(e, (groq.APIConnectionError, groq.InternalServerError)):
            raise LLMError(f"Groq service error ({type(e).__name__}): {e}") from e
        if isinstance(e, groq.APIStatusError):
            if e.status_code in (401, 403):
                raise LLMAuthError(f"Groq authentication failed ({e.status_code}): {e}") from e
            if e.status_code == 429:
                raise LLMRateLimitError(f"Groq rate limit exceeded (429): {e}") from e
            if e.status_code >= 500:
                raise LLMError(f"Groq server error ({e.status_code}): {e}") from e
            raise LLMError(f"Groq API error ({e.status_code}): {e}") from e
        raise LLMError(f"Unexpected error during Groq call: {e}") from e

    def _call_with_retry(self, fn: Callable[[], Any]) -> Any:
        """Execute callable with exponential backoff on retryable failures."""
        self._ensure_authenticated()
        delay = self.initial_delay

        for attempt in range(self.max_retries + 1):
            try:
                return fn()
            except groq.AuthenticationError as e:
                # Auth errors are not retryable
                raise LLMAuthError(f"Groq authentication failed: {e}") from e
            except (groq.RateLimitError, groq.InternalServerError, groq.APIConnectionError, groq.APITimeoutError) as e:
                if attempt == self.max_retries:
                    logger.error("Groq call failed after %d retries: %s", self.max_retries, e)
                    self._classify_error(e)
                jitter = random.uniform(0.1, 0.5)
                sleep_time = delay + jitter
                logger.warning(
                    "Groq transient error on attempt %d/%d (%s). Retrying in %.2fs...",
                    attempt + 1,
                    self.max_retries,
                    type(e).__name__,
                    sleep_time,
                )
                time.sleep(sleep_time)
                delay *= self.backoff_multiplier
            except Exception as e:
                # Classify and map immediately
                self._classify_error(e)

    def generate_json(
        self,
        system: str,
        prompt: str,
        schema: type[T],
        temperature: float = 0.3,
    ) -> T:
        """Generate structured JSON and validate against a Pydantic schema."""
        json_schema_str = json.dumps(schema.model_json_schema(), indent=2)
        augmented_system = (
            f"{system}\n\n"
            "CRITICAL SCHEMA INSTRUCTION:\n"
            "You MUST respond with a valid JSON object matching the following JSON Schema exactly.\n"
            "Do NOT include markdown fences, comments, or any extra text.\n"
            f"Schema:\n{json_schema_str}"
        )

        def _execute():
            assert self._client is not None
            return self._client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": augmented_system},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
            )

        start_time = time.perf_counter()
        resp = self._call_with_retry(_execute)
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        raw_text = resp.choices[0].message.content or ""

        # Extract token usage if available
        prompt_tokens = getattr(resp.usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(resp.usage, "completion_tokens", 0) or 0
        total_tokens = getattr(resp.usage, "total_tokens", prompt_tokens + completion_tokens) or 0

        self.last_metadata = LLMMetadata(
            model=self.model_name,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            raw_response=raw_text,
        )

        cleaned_text = self._clean_json_text(raw_text)

        try:
            return schema.model_validate_json(cleaned_text)
        except (ValidationError, json.JSONDecodeError) as val_err:
            logger.error("Failed to parse/validate Groq response against schema: %s", val_err)
            raise LLMValidationError(
                f"Groq response failed schema validation: {val_err}",
                raw_response=raw_text,
            ) from val_err

    def generate_text(
        self,
        system: str,
        prompt: str,
        temperature: float = 0.7,
    ) -> str:
        """Generate unstructured free text."""

        def _execute():
            assert self._client is not None
            return self._client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
            )

        start_time = time.perf_counter()
        resp = self._call_with_retry(_execute)
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        raw_text = resp.choices[0].message.content or ""

        prompt_tokens = getattr(resp.usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(resp.usage, "completion_tokens", 0) or 0
        total_tokens = getattr(resp.usage, "total_tokens", prompt_tokens + completion_tokens) or 0

        self.last_metadata = LLMMetadata(
            model=self.model_name,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            raw_response=raw_text,
        )

        return raw_text
