"""Unit tests for the LLM multi-provider router with failover and error sanitization."""

import time
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from app.llm.base import (
    LLMAuthError,
    LLMError,
    LLMMetadata,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.llm.router import LLMRouter
from app.pipeline import generate_plan_v0, sanitize_error_message
from app.schemas import PlanInputs


class SampleSchema(BaseModel):
    title: str
    score: int = Field(ge=0)


def test_router_first_provider_succeeds():
    mock_p1 = MagicMock()
    mock_p1.generate_json.return_value = SampleSchema(title="Plan from P1", score=10)
    mock_p1.last_metadata = LLMMetadata(
        model="m1", latency_ms=120.0, prompt_tokens=10, completion_tokens=10, total_tokens=20
    )

    mock_p2 = MagicMock()

    router = LLMRouter(chain=[("mock1", mock_p1), ("mock2", mock_p2)])
    result = router.generate_json(system="sys", prompt="prompt", schema=SampleSchema)

    assert result.title == "Plan from P1"
    assert router.active_provider == "mock1"
    assert router.last_metadata is not None
    assert router.last_metadata.latency_ms == 120.0
    mock_p1.generate_json.assert_called_once()
    mock_p2.generate_json.assert_not_called()
    assert len(router.failover_history) == 0


def test_router_failover_on_rate_limit_429():
    mock_p1 = MagicMock()
    mock_p1.generate_json.side_effect = LLMRateLimitError("Gemini quota exceeded (429)")

    mock_p2 = MagicMock()
    mock_p2.generate_json.return_value = SampleSchema(title="Plan from P2", score=9)
    mock_p2.last_metadata = LLMMetadata(
        model="m2", latency_ms=85.0, prompt_tokens=15, completion_tokens=10, total_tokens=25
    )

    router = LLMRouter(chain=[("gemini", mock_p1), ("groq", mock_p2)])
    result = router.generate_json(system="sys", prompt="prompt", schema=SampleSchema)

    assert result.title == "Plan from P2"
    assert router.active_provider == "groq"
    mock_p1.generate_json.assert_called_once()
    mock_p2.generate_json.assert_called_once()
    assert len(router.failover_history) == 1
    assert router.failover_history[0]["provider"] == "gemini"
    assert router.failover_history[0]["error_type"] == "LLMRateLimitError"


def test_router_multi_step_failover():
    # P1 fails with AuthError, P2 fails with Timeout, P3 succeeds
    mock_p1 = MagicMock()
    mock_p1.generate_text.side_effect = LLMAuthError("Invalid Groq Key")

    mock_p2 = MagicMock()
    mock_p2.generate_text.side_effect = LLMTimeoutError("Gemini timed out")

    mock_p3 = MagicMock()
    mock_p3.generate_text.return_value = "Result from Ollama"
    mock_p3.last_metadata = LLMMetadata(model="llama3.2", latency_ms=450.0)

    router = LLMRouter(chain=[("groq", mock_p1), ("gemini", mock_p2), ("ollama", mock_p3)])
    text = router.generate_text(system="sys", prompt="prompt")

    assert text == "Result from Ollama"
    assert router.active_provider == "ollama"
    assert len(router.failover_history) == 2
    assert router.failover_history[0]["provider"] == "groq"
    assert router.failover_history[1]["provider"] == "gemini"


def test_router_all_providers_fail_raises_llm_error():
    mock_p1 = MagicMock()
    mock_p1.generate_json.side_effect = LLMRateLimitError("Groq 429")

    mock_p2 = MagicMock()
    mock_p2.generate_json.side_effect = LLMRateLimitError("Gemini 429")

    router = LLMRouter(chain=[("groq", mock_p1), ("gemini", mock_p2)])

    with pytest.raises(LLMError) as exc_info:
        router.generate_json(system="sys", prompt="prompt", schema=SampleSchema)

    msg = str(exc_info.value)
    assert "All LLM providers in chain failed" in msg
    assert "groq (LLMRateLimitError" in msg
    assert "gemini (LLMRateLimitError" in msg


def test_pipeline_generate_plan_v0_fallback_when_router_fails_all():
    mock_p1 = MagicMock()
    mock_p1.generate_json.side_effect = LLMRateLimitError("Groq 429")

    mock_p2 = MagicMock()
    mock_p2.generate_json.side_effect = LLMError("Gemini 500")

    router = LLMRouter(chain=[("groq", mock_p1), ("gemini", mock_p2)])

    inputs = PlanInputs(
        event_type="birthday",
        event_date="2027-02-15",
        guests=20,
        total_budget=50000.0,
        currency="INR",
        city="Bengaluru",
    )

    result = generate_plan_v0(inputs=inputs, llm=router)
    assert result.is_fallback is True
    assert len(result.notices) > 0
    assert "AI service is busy" in result.notices[0]
    assert "{" not in result.notices[0]  # Verify no raw JSON dumped to user
    assert result.plan.total_budget == 50000.0
    assert result.plan.event_type == "birthday"


def test_router_skips_provider_with_missing_key():
    mock_p1 = MagicMock()
    mock_p1.api_key = ""  # Missing key
    mock_p1.generate_json.side_effect = AssertionError("Should never be called when key is missing")

    mock_p2 = MagicMock()
    mock_p2.api_key = "valid-key"
    mock_p2.generate_json.return_value = SampleSchema(title="Plan from P2", score=99)
    mock_p2.last_metadata = LLMMetadata(model="m2", latency_ms=50.0)

    router = LLMRouter(chain=[("groq", mock_p1), ("gemini", mock_p2)])
    result = router.generate_json(system="sys", prompt="prompt", schema=SampleSchema)

    assert result.title == "Plan from P2"
    assert router.active_provider == "gemini"
    mock_p1.generate_json.assert_not_called()
    mock_p2.generate_json.assert_called_once()
    assert len(router.failover_history) == 1
    assert "Skipped: API key not configured" in router.failover_history[0]["error_message"]


def test_router_no_keys_and_no_ollama_returns_fallback_instantly():
    with (
        patch("app.config.GROQ_API_KEY", ""),
        patch("app.config.GEMINI_API_KEY", ""),
        patch("app.config.OLLAMA_BASE_URL", ""),
        patch("app.config.LLM_CHAIN", "groq,gemini"),
    ):
        router = LLMRouter()
        assert len(router.providers) == 0

        inputs = PlanInputs(
            event_type="wedding",
            event_date="2027-05-20",
            guests=100,
            total_budget=500000.0,
            currency="INR",
            city="Bengaluru",
        )

        start = time.perf_counter()
        result = generate_plan_v0(inputs=inputs, llm=router)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.2  # Must execute instantly without retry loops or timeouts
        assert result.is_fallback is True
        assert any("busy" in n.lower() or "benchmark" in n.lower() for n in result.notices)
        assert result.plan.total_budget == 500000.0


def test_simulated_429_sanitizes_raw_json_dump():
    # Simulate a raw Gemini 429 quota failure with nested JSON payload
    raw_rpc_error = (
        "Gemini rate limit exceeded after 3 retries: 429 RESOURCE_EXHAUSTED. "
        "{'error': {'code': 429, 'message': 'You exceeded your current quota...', "
        "'details': [{'@type': 'type.googleapis.com/google.rpc.QuotaFailure'}]}}"
    )

    mock_llm = MagicMock()
    mock_llm.api_key = "valid-key"
    mock_llm.generate_json.side_effect = LLMRateLimitError(raw_rpc_error)

    inputs = PlanInputs(
        event_type="wedding",
        event_date="2027-06-10",
        guests=50,
        total_budget=100000.0,
        currency="INR",
        city="Bengaluru",
    )

    result = generate_plan_v0(inputs=inputs, llm=mock_llm)
    assert result.is_fallback is True
    assert len(result.notices) > 0
    notice = result.notices[0]

    # Verify user message is short, polite, and completely free of JSON payloads or code blocks
    assert "AI service is busy, showing a benchmark plan" in notice
    assert "{" not in notice
    assert "}" not in notice
    assert "429" not in notice
    assert "RESOURCE_EXHAUSTED" not in notice
    assert "googleapis.com" not in notice


def test_sanitize_error_message_helper():
    assert "busy" in sanitize_error_message("429 RESOURCE_EXHAUSTED").lower()
    assert "invalid" in sanitize_error_message("Invalid API key").lower()
    assert "timed out" in sanitize_error_message("Request timed out after 30s").lower()
    assert "{" not in sanitize_error_message("{'error': {'code': 500}}")
