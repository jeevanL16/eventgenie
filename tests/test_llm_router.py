"""Unit tests for the LLM multi-provider router with failover."""

from unittest.mock import MagicMock

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
from app.pipeline import generate_plan_v0
from app.schemas import PlanInputs


class SampleSchema(BaseModel):
    title: str
    score: int = Field(ge=0)


def test_router_first_provider_succeeds():
    mock_p1 = MagicMock()
    mock_p1.generate_json.return_value = SampleSchema(title="Plan from P1", score=10)
    mock_p1.last_metadata = LLMMetadata(model="m1", latency_ms=120.0, prompt_tokens=10, completion_tokens=10, total_tokens=20)

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
    mock_p2.last_metadata = LLMMetadata(model="m2", latency_ms=85.0, prompt_tokens=15, completion_tokens=10, total_tokens=25)

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
    assert "All LLM providers in chain failed" in result.notices[0]
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
    import time
    from unittest.mock import patch

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
        assert any("fallback" in n.lower() or "unavailable" in n.lower() for n in result.notices)
        assert result.plan.total_budget == 500000.0
