"""Unit tests for the Groq LLM provider implementation."""

from unittest.mock import MagicMock, patch

import groq
import pytest
from pydantic import BaseModel, Field

from app.llm.base import (
    LLMAuthError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMValidationError,
)
from app.llm.groq import GroqLLM


class SampleTestSchema(BaseModel):
    name: str
    count: int = Field(ge=1)


def test_groq_missing_api_key_raises_auth_error():
    llm = GroqLLM(api_key="")
    with pytest.raises(LLMAuthError, match="GROQ_API_KEY is not configured"):
        llm.generate_text(system="test", prompt="hello")


def test_groq_generate_json_success():
    llm = GroqLLM(api_key="gsk_test_key", model_name="qwen/qwen3.8-27b")

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '{"name": "Wedding", "count": 150}'
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 20
    mock_response.usage.completion_tokens = 15
    mock_response.usage.total_tokens = 35

    with patch.object(llm._client.chat.completions, "create", return_value=mock_response):
        result = llm.generate_json(
            system="System instructions",
            prompt="Generate sample",
            schema=SampleTestSchema,
        )

        assert isinstance(result, SampleTestSchema)
        assert result.name == "Wedding"
        assert result.count == 150

        assert llm.last_metadata is not None
        assert llm.last_metadata.model == "qwen/qwen3.8-27b"
        assert llm.last_metadata.prompt_tokens == 20
        assert llm.last_metadata.completion_tokens == 15
        assert llm.last_metadata.total_tokens == 35


def test_groq_generate_json_with_markdown_fences():
    llm = GroqLLM(api_key="gsk_test_key", model_name="qwen/qwen3.8-27b")

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '```json\n{"name": "Birthday Party", "count": 25}\n```'
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 10
    mock_response.usage.total_tokens = 20

    with patch.object(llm._client.chat.completions, "create", return_value=mock_response):
        result = llm.generate_json(
            system="System instructions",
            prompt="Generate sample",
            schema=SampleTestSchema,
        )

        assert result.name == "Birthday Party"
        assert result.count == 25


def test_groq_generate_json_validation_error():
    llm = GroqLLM(api_key="gsk_test_key", model_name="qwen/qwen3.8-27b")

    mock_response = MagicMock()
    mock_choice = MagicMock()
    # Invalid count (< 1) and missing name
    mock_choice.message.content = '{"count": 0}'
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 10
    mock_response.usage.total_tokens = 20

    with patch.object(llm._client.chat.completions, "create", return_value=mock_response):
        with pytest.raises(LLMValidationError) as exc_info:
            llm.generate_json(
                system="System instructions",
                prompt="Generate sample",
                schema=SampleTestSchema,
            )
        assert '{"count": 0}' in exc_info.value.raw_response


def test_groq_generate_text_success():
    llm = GroqLLM(api_key="gsk_test_key", model_name="qwen/qwen3.8-27b")

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Here is an event theme: Royal Palace."
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 12
    mock_response.usage.completion_tokens = 8
    mock_response.usage.total_tokens = 20

    with patch.object(llm._client.chat.completions, "create", return_value=mock_response):
        text = llm.generate_text(system="System instructions", prompt="Suggest theme")

        assert text == "Here is an event theme: Royal Palace."
        assert llm.last_metadata is not None
        assert llm.last_metadata.completion_tokens == 8


def test_groq_rate_limit_retry_exhausted():
    llm = GroqLLM(
        api_key="gsk_test_key",
        model_name="qwen/qwen3.8-27b",
        max_retries=2,
        initial_delay=0.01,
    )

    rate_err = groq.RateLimitError(
        message="Rate limit reached",
        response=MagicMock(status_code=429),
        body={"error": {"message": "Rate limit reached"}},
    )

    with patch.object(llm._client.chat.completions, "create", side_effect=rate_err) as mock_create:
        with patch("time.sleep", return_value=None):
            with pytest.raises(LLMRateLimitError):
                llm.generate_text(system="sys", prompt="user")

        assert mock_create.call_count == 3  # initial + 2 retries


def test_groq_auth_error_no_retry():
    llm = GroqLLM(api_key="gsk_invalid_key", model_name="qwen/qwen3.8-27b")

    auth_err = groq.AuthenticationError(
        message="Invalid API Key",
        response=MagicMock(status_code=401),
        body={"error": {"message": "Invalid API Key"}},
    )

    with patch.object(llm._client.chat.completions, "create", side_effect=auth_err) as mock_create:
        with patch("time.sleep") as mock_sleep:
            with pytest.raises(LLMAuthError):
                llm.generate_text(system="sys", prompt="user")

        mock_sleep.assert_not_called()
        assert mock_create.call_count == 1


def test_groq_timeout_error():
    llm = GroqLLM(
        api_key="gsk_test_key",
        model_name="qwen/qwen3.8-27b",
        max_retries=0,
    )

    timeout_err = groq.APITimeoutError(request=MagicMock())

    with patch.object(llm._client.chat.completions, "create", side_effect=timeout_err):
        with pytest.raises(LLMTimeoutError):
            llm.generate_text(system="sys", prompt="user")
