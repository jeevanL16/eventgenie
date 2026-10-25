"""Google Gemini LLM implementation with retry, backoff, and schema validation."""

import json
import logging
import random
import re
import time
from collections.abc import Callable
from typing import Any, TypeVar

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from google.generativeai.types import GenerationConfig, RequestOptions
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


class GeminiLLM:
    """Gemini API client supporting structured JSON generation and plain text."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        initial_delay: float = 1.0,
        backoff_multiplier: float = 2.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else config.GEMINI_API_KEY
        self.model_name = model_name or config.GEMINI_MODEL
        self.timeout = timeout if timeout is not None else config.LLM_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else config.LLM_MAX_RETRIES
        self.initial_delay = initial_delay
        self.backoff_multiplier = backoff_multiplier
        self.last_metadata: LLMMetadata | None = None

        if self.api_key:
            genai.configure(api_key=self.api_key)

    def _ensure_authenticated(self) -> None:
        if not self.api_key:
            raise LLMAuthError(
                "GEMINI_API_KEY is not configured. Please set GEMINI_API_KEY in your .env file."
            )

    @staticmethod
    def _clean_json_text(text: str) -> str:
        """Strip markdown code fence blocks if present."""
        cleaned = text.strip()
        # Remove ```json ... ``` or ``` ... ```
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    def _execute_with_retry(self, fn: Callable[[], Any]) -> Any:
        """Execute a call with exponential backoff on retryable status codes."""
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                return fn()
            except (
                google_exceptions.Unauthenticated,
                google_exceptions.PermissionDenied,
            ) as e:
                # Fatal auth error — do not retry
                raise LLMAuthError(f"Authentication failed: {e}") from e
            except google_exceptions.ResourceExhausted as e:
                last_exception = e
                if attempt >= self.max_retries:
                    raise LLMRateLimitError(
                        f"Gemini rate limit exceeded after {self.max_retries} retries: {e}"
                    ) from e
                delay = (self.initial_delay * (self.backoff_multiplier**attempt)) + random.uniform(
                    0.0, 0.3
                )
                logger.warning(
                    "Rate limit hit (429). Retrying attempt %d/%d in %.2fs...",
                    attempt + 1,
                    self.max_retries,
                    delay,
                )
                time.sleep(delay)
            except (
                google_exceptions.ServiceUnavailable,
                google_exceptions.InternalServerError,
                google_exceptions.BadGateway,
            ) as e:
                last_exception = e
                if attempt >= self.max_retries:
                    raise LLMError(
                        f"Gemini server error after {self.max_retries} retries: {e}"
                    ) from e
                delay = (self.initial_delay * (self.backoff_multiplier**attempt)) + random.uniform(
                    0.0, 0.3
                )
                logger.warning(
                    "Server error (%s). Retrying attempt %d/%d in %.2fs...",
                    type(e).__name__,
                    attempt + 1,
                    self.max_retries,
                    delay,
                )
                time.sleep(delay)
            except (
                google_exceptions.DeadlineExceeded,
                TimeoutError,
            ) as e:
                last_exception = e
                if attempt >= self.max_retries:
                    raise LLMTimeoutError(
                        f"Gemini call timed out after {self.max_retries} retries: {e}"
                    ) from e
                delay = (self.initial_delay * (self.backoff_multiplier**attempt)) + random.uniform(
                    0.0, 0.3
                )
                logger.warning(
                    "Timeout occurred. Retrying attempt %d/%d in %.2fs...",
                    attempt + 1,
                    self.max_retries,
                    delay,
                )
                time.sleep(delay)
            except google_exceptions.GoogleAPIError as e:
                last_exception = e
                raise LLMError(f"Gemini API error: {e}") from e
            except Exception as e:
                last_exception = e
                raise LLMError(f"Unexpected error during Gemini call: {e}") from e

        raise LLMError(f"Call failed after retries: {last_exception}")

    def _extract_usage(self, response: Any) -> tuple[int, int, int]:
        """Extract prompt, completion, and total tokens from response usage metadata."""
        try:
            usage = getattr(response, "usage_metadata", None)
            if usage is not None:
                p_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
                c_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
                t_tokens = int(getattr(usage, "total_token_count", 0) or (p_tokens + c_tokens))
                return p_tokens, c_tokens, t_tokens
        except Exception as e:
            logger.debug("Could not parse usage metadata: %s", e)
        return 0, 0, 0

    def generate_json(
        self,
        system: str,
        prompt: str,
        schema: type[T],
        temperature: float = 0.3,
    ) -> T:
        """Generate structured output validated against a Pydantic schema."""
        self._ensure_authenticated()

        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system if system else None,
        )

        gen_config = GenerationConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
        )

        request_options = RequestOptions(timeout=self.timeout)

        start_time = time.perf_counter()
        response = self._execute_with_retry(
            lambda: model.generate_content(
                prompt,
                generation_config=gen_config,
                request_options=request_options,
            )
        )
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        raw_text = response.text or ""
        p_tokens, c_tokens, t_tokens = self._extract_usage(response)

        self.last_metadata = LLMMetadata(
            model=self.model_name,
            latency_ms=round(latency_ms, 2),
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            total_tokens=t_tokens,
            raw_response=raw_text,
        )

        clean_text = self._clean_json_text(raw_text)

        try:
            return schema.model_validate_json(clean_text)
        except (ValidationError, json.JSONDecodeError) as e:
            logger.error("JSON schema validation failed for %s: %s", schema.__name__, e)
            raise LLMValidationError(
                f"Failed to validate response against schema {schema.__name__}: {e}",
                raw_response=raw_text,
            ) from e

    def generate_text(
        self,
        system: str,
        prompt: str,
        temperature: float = 0.7,
    ) -> str:
        """Generate unstructured free text."""
        self._ensure_authenticated()

        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=system if system else None,
        )

        gen_config = GenerationConfig(temperature=temperature)
        request_options = RequestOptions(timeout=self.timeout)

        start_time = time.perf_counter()
        response = self._execute_with_retry(
            lambda: model.generate_content(
                prompt,
                generation_config=gen_config,
                request_options=request_options,
            )
        )
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        raw_text = response.text or ""
        p_tokens, c_tokens, t_tokens = self._extract_usage(response)

        self.last_metadata = LLMMetadata(
            model=self.model_name,
            latency_ms=round(latency_ms, 2),
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            total_tokens=t_tokens,
            raw_response=raw_text,
        )

        return raw_text
