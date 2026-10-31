"""Ollama local LLM provider implementation for offline development, CI, and evaluations.

Communicates with Ollama's REST API (`/api/chat`) using `httpx`, supporting structured JSON
output (`format="json"` or schema instruction), plain text generation, retry/backoff,
token reporting, and latency telemetry.
"""

import json
import logging
import random
import re
import time
from collections.abc import Callable
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app import config
from app.llm.base import (
    LLMError,
    LLMMetadata,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMValidationError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OllamaLLM:
    """Ollama local API client adhering to the LLM protocol."""

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        initial_delay: float = 1.0,
        backoff_multiplier: float = 2.0,
    ) -> None:
        self.base_url = (base_url or config.OLLAMA_BASE_URL).rstrip("/")
        self.model_name = model_name or config.OLLAMA_MODEL
        self.timeout = timeout if timeout is not None else config.LLM_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else config.LLM_MAX_RETRIES
        self.initial_delay = initial_delay
        self.backoff_multiplier = backoff_multiplier
        self.last_metadata: LLMMetadata | None = None

        # API key is not required for local Ollama, but attribute is kept for protocol consistency
        self.api_key: str | None = "local"

    @staticmethod
    def _clean_json_text(text: str) -> str:
        """Strip markdown code fence blocks if present."""
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    def _call_with_retry(self, fn: Callable[[], httpx.Response]) -> httpx.Response:
        """Execute HTTP request with exponential backoff on transient errors."""
        delay = self.initial_delay

        for attempt in range(self.max_retries + 1):
            try:
                resp = fn()
                if resp.status_code == 429:
                    raise LLMRateLimitError(f"Ollama rate limit exceeded (429): {resp.text}")
                if resp.status_code == 404:
                    raise LLMError(
                        f"Ollama model '{self.model_name}' not found (404). Run 'ollama pull {self.model_name}' first."
                    )
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"Server error {resp.status_code}", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                return resp
            except LLMError:
                raise
            except (httpx.TimeoutException, LLMTimeoutError) as e:
                if attempt == self.max_retries:
                    logger.error(
                        "Ollama request timed out after %d retries: %s", self.max_retries, e
                    )
                    raise LLMTimeoutError(f"Ollama call timed out: {e}") from e
                sleep_time = delay + random.uniform(0.1, 0.4)
                logger.warning(
                    "Ollama timeout on attempt %d/%d. Retrying in %.2fs...",
                    attempt + 1,
                    self.max_retries,
                    sleep_time,
                )
                time.sleep(sleep_time)
                delay *= self.backoff_multiplier
            except (httpx.ConnectError, httpx.HTTPStatusError) as e:
                if attempt == self.max_retries:
                    logger.error("Ollama service error after %d retries: %s", self.max_retries, e)
                    raise LLMError(f"Ollama call failed: {e}") from e
                sleep_time = delay + random.uniform(0.1, 0.4)
                logger.warning(
                    "Ollama transient failure on attempt %d/%d (%s). Retrying in %.2fs...",
                    attempt + 1,
                    self.max_retries,
                    type(e).__name__,
                    sleep_time,
                )
                time.sleep(sleep_time)
                delay *= self.backoff_multiplier
            except Exception as e:
                logger.error("Unexpected Ollama error: %s", e)
                raise LLMError(f"Unexpected Ollama call failure: {e}") from e

        raise LLMError("Exceeded retry budget without response.")

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

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": augmented_system},
                {"role": "user", "content": prompt},
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        url = f"{self.base_url}/api/chat"

        def _execute() -> httpx.Response:
            with httpx.Client(timeout=self.timeout) as client:
                return client.post(url, json=payload)

        start_time = time.perf_counter()
        resp = self._call_with_retry(_execute)
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        data = resp.json()
        raw_text = data.get("message", {}).get("content", "")

        prompt_tokens = data.get("prompt_eval_count", 0) or 0
        completion_tokens = data.get("eval_count", 0) or 0
        total_tokens = prompt_tokens + completion_tokens

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
            logger.error("Failed to parse/validate Ollama response against schema: %s", val_err)
            raise LLMValidationError(
                f"Ollama response failed schema validation: {val_err}",
                raw_response=raw_text,
            ) from val_err

    def generate_text(
        self,
        system: str,
        prompt: str,
        temperature: float = 0.7,
    ) -> str:
        """Generate unstructured free text."""
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        url = f"{self.base_url}/api/chat"

        def _execute() -> httpx.Response:
            with httpx.Client(timeout=self.timeout) as client:
                return client.post(url, json=payload)

        start_time = time.perf_counter()
        resp = self._call_with_retry(_execute)
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        data = resp.json()
        raw_text = data.get("message", {}).get("content", "")

        prompt_tokens = data.get("prompt_eval_count", 0) or 0
        completion_tokens = data.get("eval_count", 0) or 0
        total_tokens = prompt_tokens + completion_tokens

        self.last_metadata = LLMMetadata(
            model=self.model_name,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            raw_response=raw_text,
        )

        return raw_text
