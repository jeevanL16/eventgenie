"""Unit tests for the Ollama local LLM provider implementation."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import BaseModel, Field

from app.llm.base import (
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMValidationError,
)
from app.llm.ollama import OllamaLLM


class SampleTestSchema(BaseModel):
    title: str
    budget: float = Field(gt=0)


def test_ollama_generate_json_success():
    llm = OllamaLLM(base_url="http://localhost:11434", model_name="llama3.2")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "llama3.2",
        "message": {"role": "assistant", "content": '{"title": "Gala Night", "budget": 50000.0}'},
        "prompt_eval_count": 40,
        "eval_count": 25,
    }

    with patch.object(httpx.Client, "post", return_value=mock_resp):
        result = llm.generate_json(
            system="System instructions",
            prompt="Generate event",
            schema=SampleTestSchema,
        )

        assert isinstance(result, SampleTestSchema)
        assert result.title == "Gala Night"
        assert result.budget == 50000.0

        assert llm.last_metadata is not None
        assert llm.last_metadata.model == "llama3.2"
        assert llm.last_metadata.prompt_tokens == 40
        assert llm.last_metadata.completion_tokens == 25
        assert llm.last_metadata.total_tokens == 65


def test_ollama_generate_json_with_code_fences():
    llm = OllamaLLM(base_url="http://localhost:11434", model_name="llama3.2")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "llama3.2",
        "message": {
            "role": "assistant",
            "content": '```json\n{"title": "Anniversary Dinner", "budget": 12000.0}\n```',
        },
        "prompt_eval_count": 30,
        "eval_count": 20,
    }

    with patch.object(httpx.Client, "post", return_value=mock_resp):
        result = llm.generate_json(
            system="System instructions",
            prompt="Generate event",
            schema=SampleTestSchema,
        )

        assert result.title == "Anniversary Dinner"
        assert result.budget == 12000.0


def test_ollama_generate_json_validation_error():
    llm = OllamaLLM(base_url="http://localhost:11434", model_name="llama3.2")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "llama3.2",
        "message": {"role": "assistant", "content": '{"budget": -100}'},
        "prompt_eval_count": 10,
        "eval_count": 5,
    }

    with patch.object(httpx.Client, "post", return_value=mock_resp):
        with pytest.raises(LLMValidationError) as exc_info:
            llm.generate_json(
                system="System instructions",
                prompt="Generate event",
                schema=SampleTestSchema,
            )
        assert '{"budget": -100}' in exc_info.value.raw_response


def test_ollama_generate_text_success():
    llm = OllamaLLM(base_url="http://localhost:11434", model_name="llama3.2")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "llama3.2",
        "message": {"role": "assistant", "content": "A lovely evening reception."},
        "prompt_eval_count": 15,
        "eval_count": 10,
    }

    with patch.object(httpx.Client, "post", return_value=mock_resp):
        text = llm.generate_text(system="System instructions", prompt="Describe party")
        assert text == "A lovely evening reception."
        assert llm.last_metadata is not None
        assert llm.last_metadata.completion_tokens == 10


def test_ollama_timeout_error():
    llm = OllamaLLM(base_url="http://localhost:11434", max_retries=1, initial_delay=0.01)

    with patch.object(
        httpx.Client, "post", side_effect=httpx.TimeoutException("Timed out")
    ) as mock_post:
        with patch("time.sleep"):
            with pytest.raises(LLMTimeoutError):
                llm.generate_text(system="sys", prompt="user")
        assert mock_post.call_count == 2  # initial + 1 retry


def test_ollama_connection_error():
    llm = OllamaLLM(base_url="http://localhost:11434", max_retries=1, initial_delay=0.01)

    with patch.object(
        httpx.Client, "post", side_effect=httpx.ConnectError("Connection refused")
    ) as mock_post:
        with patch("time.sleep"):
            with pytest.raises(LLMError, match="Ollama call failed"):
                llm.generate_text(system="sys", prompt="user")
        assert mock_post.call_count == 2


def test_ollama_model_not_found_404():
    llm = OllamaLLM(base_url="http://localhost:11434", model_name="nonexistent:latest", max_retries=0)

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 404
    mock_resp.text = "model not found"

    with patch.object(httpx.Client, "post", return_value=mock_resp):
        with pytest.raises(LLMError, match="not found"):
            llm.generate_text(system="sys", prompt="user")


def test_ollama_rate_limit_429():
    llm = OllamaLLM(base_url="http://localhost:11434", max_retries=0)

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 429
    mock_resp.text = "Rate limit"

    with patch.object(httpx.Client, "post", return_value=mock_resp):
        with pytest.raises(LLMRateLimitError):
            llm.generate_text(system="sys", prompt="user")
