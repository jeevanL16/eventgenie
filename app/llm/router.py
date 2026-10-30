"""LLM Router with ordered multi-provider failover.

Iterates through a configurable chain of LLM providers (e.g. Groq -> Gemini -> Ollama),
failing over automatically upon 429 (rate limits), 5xx errors, timeouts, auth errors,
or validation failures. Tracks telemetry and active provider history.
Skips unconfigured providers instantly without delay.
"""

import logging
from typing import Any, TypeVar

from pydantic import BaseModel

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
from app.llm.ollama import OllamaLLM

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMRouter:
    """Ordered multi-provider LLM router adhering to the LLM protocol."""

    def __init__(
        self,
        chain: list[str] | list[LLM] | None = None,
        gemini_api_key: str | None = None,
        groq_api_key: str | None = None,
    ) -> None:
        """Initialize router with provider chain and optional explicit API keys.

        Args:
            chain: List of provider names (e.g. ['groq', 'gemini']) or LLM instances.
                   If None, reads from config.LLM_CHAIN.
            gemini_api_key: Optional override for Gemini API key (e.g. user session key).
            groq_api_key: Optional override for Groq API key (e.g. user session key).
        """
        self.gemini_api_key = gemini_api_key
        self.groq_api_key = groq_api_key
        self.raw_chain_spec = chain if chain is not None else config.LLM_CHAIN

        self.providers: list[tuple[str, LLM]] = []
        self._initialize_chain(self.raw_chain_spec)

        self.last_metadata: LLMMetadata | None = None
        self.active_provider: str | None = None
        self.failover_history: list[dict[str, Any]] = []
        self.api_key: str | None = "router"

    def _initialize_chain(self, chain_spec: list[str] | list[LLM] | str) -> None:
        """Instantiate LLM instances for each provider in the chain."""
        items: list[Any]
        if isinstance(chain_spec, str):
            items = [item.strip() for item in chain_spec.split(",") if item.strip()]
        else:
            items = list(chain_spec)

        for item in items:
            if isinstance(item, str):
                name = item.lower()
                llm_instance = self._build_provider_by_name(name)
                if llm_instance is not None:
                    self.providers.append((name, llm_instance))
            elif isinstance(item, tuple) and len(item) == 2:
                self.providers.append((str(item[0]), item[1]))
            else:
                name = getattr(item, "__class__", type(item)).__name__.lower().replace("llm", "")
                self.providers.append((name, item))

    def _build_provider_by_name(self, name: str) -> LLM | None:
        """Build provider instance by name with any available session keys.

        Skips providers without valid API keys or unconfigured endpoints immediately
        without throwing errors or incurring latency.
        """
        if name == "groq":
            api_key = self.groq_api_key or config.GROQ_API_KEY
            if not api_key:
                logger.info("Skipping Groq: GROQ_API_KEY is not configured.")
                return None
            return GroqLLM(api_key=api_key)
        elif name == "gemini":
            api_key = self.gemini_api_key or config.GEMINI_API_KEY
            if not api_key:
                logger.info("Skipping Gemini: GEMINI_API_KEY is not configured.")
                return None
            return GeminiLLM(api_key=api_key)
        elif name == "ollama":
            # Ollama must be tried only if explicitly listed in LLM_CHAIN or if OLLAMA_BASE_URL is set
            if not config.OLLAMA_BASE_URL:
                logger.info("Skipping Ollama: OLLAMA_BASE_URL is not set.")
                return None
            return OllamaLLM(base_url=config.OLLAMA_BASE_URL)
        else:
            logger.warning("Unknown provider '%s' in LLM_CHAIN; skipping.", name)
            return None

    def generate_json(
        self,
        system: str,
        prompt: str,
        schema: type[T],
        temperature: float = 0.3,
    ) -> T:
        """Execute structured JSON generation with failover across the provider chain."""
        self.failover_history.clear()

        if not self.providers:
            raise LLMError("No active LLM providers configured in chain (missing API keys).")

        for name, provider in self.providers:
            # Skip provider instantly if API key is missing
            if hasattr(provider, "api_key") and not provider.api_key:
                logger.info("Skipping provider '%s': API key is missing.", name)
                self.failover_history.append({
                    "provider": name,
                    "error_type": "LLMAuthError",
                    "error_message": "Skipped: API key not configured",
                })
                continue

            try:
                logger.info("LLMRouter attempting generate_json with provider: %s", name)
                result = provider.generate_json(
                    system=system,
                    prompt=prompt,
                    schema=schema,
                    temperature=temperature,
                )
                self.last_metadata = provider.last_metadata
                self.active_provider = name
                logger.info(
                    "LLMRouter call successfully served by '%s' (latency: %.1fms)",
                    name,
                    self.last_metadata.latency_ms if self.last_metadata else 0.0,
                )
                return result
            except (
                LLMRateLimitError,
                LLMTimeoutError,
                LLMAuthError,
                LLMValidationError,
                LLMError,
                Exception,
            ) as e:
                err_type = type(e).__name__
                err_msg = str(e)
                logger.warning(
                    "LLMRouter provider '%s' failed (%s: %s). Failing over...",
                    name,
                    err_type,
                    err_msg,
                )
                self.failover_history.append({
                    "provider": name,
                    "error_type": err_type,
                    "error_message": err_msg,
                })

        # All providers exhausted or skipped
        summary = "; ".join(
            f"{item['provider']} ({item['error_type']}: {item['error_message']})"
            for item in self.failover_history
        )
        raise LLMError(f"All LLM providers in chain failed or were skipped: [{summary}]")

    def generate_text(
        self,
        system: str,
        prompt: str,
        temperature: float = 0.7,
    ) -> str:
        """Execute free text generation with failover across the provider chain."""
        self.failover_history.clear()

        if not self.providers:
            raise LLMError("No active LLM providers configured in chain (missing API keys).")

        for name, provider in self.providers:
            # Skip provider instantly if API key is missing
            if hasattr(provider, "api_key") and not provider.api_key:
                logger.info("Skipping provider '%s': API key is missing.", name)
                self.failover_history.append({
                    "provider": name,
                    "error_type": "LLMAuthError",
                    "error_message": "Skipped: API key not configured",
                })
                continue

            try:
                logger.info("LLMRouter attempting generate_text with provider: %s", name)
                result = provider.generate_text(
                    system=system,
                    prompt=prompt,
                    temperature=temperature,
                )
                self.last_metadata = provider.last_metadata
                self.active_provider = name
                logger.info(
                    "LLMRouter call successfully served by '%s' (latency: %.1fms)",
                    name,
                    self.last_metadata.latency_ms if self.last_metadata else 0.0,
                )
                return result
            except (
                LLMRateLimitError,
                LLMTimeoutError,
                LLMAuthError,
                LLMValidationError,
                LLMError,
                Exception,
            ) as e:
                err_type = type(e).__name__
                err_msg = str(e)
                logger.warning(
                    "LLMRouter provider '%s' failed (%s: %s). Failing over...",
                    name,
                    err_type,
                    err_msg,
                )
                self.failover_history.append({
                    "provider": name,
                    "error_type": err_type,
                    "error_message": err_msg,
                })

        # All providers exhausted or skipped
        summary = "; ".join(
            f"{item['provider']} ({item['error_type']}: {item['error_message']})"
            for item in self.failover_history
        )
        raise LLMError(f"All LLM providers in chain failed or were skipped: [{summary}]")
