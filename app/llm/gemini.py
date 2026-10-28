"""Google Gemini LLM implementation using the official google-genai unified SDK.

Migrated from deprecated `google-generativeai` to `google-genai` (Oct 2026).
Uses `genai.Client` pattern with per-call model specification and
`types.GenerateContentConfig` for structured JSON output.
"""

import json
import logging
import random
import re
import time
from collections.abc import Callable
from typing import Any, TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
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
    """Gemini API client supporting structured JSON generation and plain text.

    Uses the unified `google-genai` SDK with explicit Client instantiation
    and per-call model specification.
    """

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

        # Initialize the unified genai.Client
        self._client: genai.Client | None = None
        if self.api_key:
            self._client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=int(self.timeout * 1000)),
            )

    def _ensure_authenticated(self) -> None:
        if not self.api_key:
            raise LLMAuthError(
                "GEMINI_API_KEY is not configured. Please set GEMINI_API_KEY in your .env file."
            )
        if self._client is None:
            raise LLMAuthError("Gemini client not initialized. Check API key configuration.")

    @staticmethod
    def _clean_json_text(text: str) -> str:
        """Strip markdown code fence blocks if present."""
        cleaned = text.strip()
        # Remove ```json ... ``` or ``` ... ```
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    def _classify_client_error(self, e: genai_errors.ClientError) -> None:
        """Map ClientError HTTP status codes to our custom exception hierarchy."""
        code = getattr(e, "code", None) or getattr(e, "status", None)
        message = str(e)

        # Check for auth-related errors (401, 403)
        if code in (401, 403) or any(
            kw in message.lower()
            for kw in ("unauthorized", "permission denied", "forbidden", "api key not valid")
        ):
            raise LLMAuthError(f"Authentication failed: {e}") from e

        # Check for rate limit (429)
        if code == 429 or "resource exhausted" in message.lower() or "quota" in message.lower():
            raise LLMRateLimitError(f"Rate limit exceeded: {e}") from e

        # Other 4xx client errors are non-retryable
        raise LLMError(f"Gemini client error: {e}") from e

    def _execute_with_retry(self, fn: Callable[[], Any]) -> Any:
        """Execute a call with exponential backoff on retryable status codes."""
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                return fn()
            except genai_errors.ClientError as e:
                # Classify the client error
                code = getattr(e, "code", None) or getattr(e, "status", None)
                message = str(e)

                # Auth errors — do not retry
                if code in (401, 403) or any(
                    kw in message.lower()
                    for kw in (
                        "unauthorized",
                        "permission denied",
                        "forbidden",
                        "api key not valid",
                    )
                ):
                    raise LLMAuthError(f"Authentication failed: {e}") from e

                # Rate limit (429) — retry with backoff
                if (
                    code == 429
                    or "resource exhausted" in message.lower()
                    or "quota" in message.lower()
                ):
                    last_exception = e
                    if attempt >= self.max_retries:
                        raise LLMRateLimitError(
                            f"Gemini rate limit exceeded after {self.max_retries} retries: {e}"
                        ) from e
                    delay = (
                        self.initial_delay * (self.backoff_multiplier**attempt)
                    ) + random.uniform(0.0, 0.3)
                    logger.warning(
                        "Rate limit hit (429). Retrying attempt %d/%d in %.2fs...",
                        attempt + 1,
                        self.max_retries,
                        delay,
                    )
                    time.sleep(delay)
                    continue

                # Other client errors (400, 404, etc.) — do not retry
                raise LLMError(f"Gemini client error: {e}") from e

            except genai_errors.ServerError as e:
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

            except Exception as e:
                # Check for timeout errors from httpx / socket / urllib
                if "timed out" in str(e).lower() or "timeout" in str(e).lower() or isinstance(e, TimeoutError):
                    last_exception = e
                    if attempt >= self.max_retries:
                        raise LLMTimeoutError(
                            f"Gemini call timed out after {self.max_retries} retries: {e}"
                        ) from e
                    delay = (self.initial_delay * (self.backoff_multiplier**attempt)) + random.uniform(
                        0.0, 0.3
                    )
                    logger.warning(
                        "Timeout occurred (%s). Retrying attempt %d/%d in %.2fs...",
                        e,
                        attempt + 1,
                        self.max_retries,
                        delay,
                    )
                    time.sleep(delay)
                    continue

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

    @staticmethod
    def _prepare_response_schema(schema: Any) -> Any:
        """Sanitize Pydantic schemas for google-genai OpenAPI compatibility.

        Converts OpenAPI-incompatible fields (e.g. exclusiveMinimum/exclusiveMaximum
        produced by Pydantic's gt/lt) into minimum/maximum so google.genai types.Schema
        validation succeeds.
        """
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            schema_dict = schema.model_json_schema()

            def _clean(d: Any) -> None:
                if isinstance(d, dict):
                    if "exclusiveMinimum" in d:
                        d["minimum"] = d.pop("exclusiveMinimum")
                    if "exclusiveMaximum" in d:
                        d["maximum"] = d.pop("exclusiveMaximum")
                    for v in d.values():
                        _clean(v)
                elif isinstance(d, list):
                    for item in d:
                        _clean(item)

            _clean(schema_dict)
            return schema_dict
        return schema

    def generate_json(
        self,
        system: str,
        prompt: str,
        schema: type[T],
        temperature: float = 0.3,
    ) -> T:
        """Generate structured output validated against a Pydantic schema."""
        self._ensure_authenticated()
        assert self._client is not None  # guaranteed by _ensure_authenticated

        prepared_schema = self._prepare_response_schema(schema)

        gen_config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=prepared_schema,
            system_instruction=system if system else None,
        )

        start_time = time.perf_counter()
        response = self._execute_with_retry(
            lambda: self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=gen_config,
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

        # Try the SDK's built-in parsed attribute first (auto-Pydantic parsing)
        parsed = getattr(response, "parsed", None)
        if parsed is not None and isinstance(parsed, schema):
            return parsed

        # Fall back to manual JSON parsing
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
        assert self._client is not None  # guaranteed by _ensure_authenticated

        gen_config = types.GenerateContentConfig(
            temperature=temperature,
            system_instruction=system if system else None,
        )

        start_time = time.perf_counter()
        response = self._execute_with_retry(
            lambda: self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=gen_config,
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
