"""Unit tests for GeminiLLM with mocked client and retry logic."""

from unittest.mock import MagicMock, patch

import pytest
from google.api_core import exceptions as google_exceptions
from pydantic import BaseModel, Field

from app.llm import (
    GeminiLLM,
    LLMAuthError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMValidationError,
    get_llm,
)


class TinyEvent(BaseModel):
    title: str
    guest_count: int = Field(gt=0)
    city: str


class MockUsageMetadata:
    prompt_token_count = 12
    candidates_token_count = 24
    total_token_count = 36


class MockResponse:
    def __init__(self, text: str, usage=None):
        self.text = text
        self.usage_metadata = usage or MockUsageMetadata()


def test_missing_api_key_raises_auth_error():
    client = GeminiLLM(api_key="")
    with pytest.raises(LLMAuthError, match="GEMINI_API_KEY is not configured"):
        client.generate_text("System", "Hello")

    with pytest.raises(LLMAuthError, match="GEMINI_API_KEY is not configured"):
        client.generate_json("System", "Generate JSON", TinyEvent)


def test_generate_json_success():
    client = GeminiLLM(api_key="fake-key", model_name="gemini-1.5-flash")

    mock_resp = MockResponse('{"title": "Birthday Party", "guest_count": 25, "city": "Bengaluru"}')

    with patch("google.generativeai.GenerativeModel") as mock_model_cls:
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = mock_resp
        mock_model_cls.return_value = mock_instance

        result = client.generate_json(
            system="You are an event planner.",
            prompt="Plan a birthday.",
            schema=TinyEvent,
            temperature=0.2,
        )

        assert isinstance(result, TinyEvent)
        assert result.title == "Birthday Party"
        assert result.guest_count == 25
        assert result.city == "Bengaluru"

        # Verify metadata
        assert client.last_metadata is not None
        assert client.last_metadata.model == "gemini-1.5-flash"
        assert client.last_metadata.latency_ms >= 0
        assert client.last_metadata.prompt_tokens == 12
        assert client.last_metadata.completion_tokens == 24
        assert client.last_metadata.total_tokens == 36
        assert "Birthday Party" in client.last_metadata.raw_response


def test_generate_json_with_markdown_fences():
    client = GeminiLLM(api_key="fake-key")

    mock_resp = MockResponse(
        '```json\n{"title": "Anniversary Dinner", "guest_count": 10, "city": "Mumbai"}\n```'
    )

    with patch("google.generativeai.GenerativeModel") as mock_model_cls:
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = mock_resp
        mock_model_cls.return_value = mock_instance

        result = client.generate_json("System", "Prompt", TinyEvent)
        assert result.title == "Anniversary Dinner"
        assert result.guest_count == 10
        assert result.city == "Mumbai"


def test_generate_json_schema_validation_error():
    client = GeminiLLM(api_key="fake-key")

    # guest_count <= 0 violates gt=0 constraint in TinyEvent
    mock_resp = MockResponse('{"title": "Invalid Party", "guest_count": -5, "city": "Delhi"}')

    with patch("google.generativeai.GenerativeModel") as mock_model_cls:
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = mock_resp
        mock_model_cls.return_value = mock_instance

        with pytest.raises(LLMValidationError) as exc_info:
            client.generate_json("System", "Prompt", TinyEvent)
        assert "Failed to validate response against schema TinyEvent" in str(exc_info.value)
        assert exc_info.value.raw_response == mock_resp.text


def test_generate_json_malformed_json_error():
    client = GeminiLLM(api_key="fake-key")
    mock_resp = MockResponse("This is not JSON at all!")

    with patch("google.generativeai.GenerativeModel") as mock_model_cls:
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = mock_resp
        mock_model_cls.return_value = mock_instance

        with pytest.raises(LLMValidationError):
            client.generate_json("System", "Prompt", TinyEvent)


def test_generate_text_success():
    client = GeminiLLM(api_key="fake-key", model_name="gemini-1.5-flash")
    mock_resp = MockResponse("Here are three themes for the party.")

    with patch("google.generativeai.GenerativeModel") as mock_model_cls:
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = mock_resp
        mock_model_cls.return_value = mock_instance

        text = client.generate_text("System", "Generate ideas", temperature=0.7)
        assert text == "Here are three themes for the party."
        assert client.last_metadata is not None
        assert client.last_metadata.raw_response == "Here are three themes for the party."


def test_retry_on_429_success_after_retry():
    client = GeminiLLM(api_key="fake-key", max_retries=2, initial_delay=0.01)

    mock_resp = MockResponse("Success after 429")

    with patch("google.generativeai.GenerativeModel") as mock_model_cls:
        mock_instance = MagicMock()
        # Fail once with ResourceExhausted (429), then succeed
        mock_instance.generate_content.side_effect = [
            google_exceptions.ResourceExhausted("Rate limit exceeded"),
            mock_resp,
        ]
        mock_model_cls.return_value = mock_instance

        result = client.generate_text("System", "Prompt")
        assert result == "Success after 429"
        assert mock_instance.generate_content.call_count == 2


def test_retry_on_429_exhausted_raises_rate_limit_error():
    client = GeminiLLM(api_key="fake-key", max_retries=2, initial_delay=0.01)

    with patch("google.generativeai.GenerativeModel") as mock_model_cls:
        mock_instance = MagicMock()
        mock_instance.generate_content.side_effect = google_exceptions.ResourceExhausted(
            "Quota exceeded"
        )
        mock_model_cls.return_value = mock_instance

        with pytest.raises(LLMRateLimitError, match="Gemini rate limit exceeded"):
            client.generate_text("System", "Prompt")

        assert mock_instance.generate_content.call_count == 3  # initial + 2 retries


def test_retry_on_503_service_unavailable():
    client = GeminiLLM(api_key="fake-key", max_retries=1, initial_delay=0.01)

    with patch("google.generativeai.GenerativeModel") as mock_model_cls:
        mock_instance = MagicMock()
        mock_instance.generate_content.side_effect = google_exceptions.ServiceUnavailable(
            "Server down"
        )
        mock_model_cls.return_value = mock_instance

        with pytest.raises(LLMError, match="Gemini server error after 1 retries"):
            client.generate_text("System", "Prompt")

        assert mock_instance.generate_content.call_count == 2


def test_retry_on_timeout():
    client = GeminiLLM(api_key="fake-key", max_retries=1, initial_delay=0.01)

    with patch("google.generativeai.GenerativeModel") as mock_model_cls:
        mock_instance = MagicMock()
        mock_instance.generate_content.side_effect = google_exceptions.DeadlineExceeded(
            "Deadline exceeded"
        )
        mock_model_cls.return_value = mock_instance

        with pytest.raises(LLMTimeoutError, match="Gemini call timed out"):
            client.generate_text("System", "Prompt")


def test_fatal_auth_error_not_retried():
    client = GeminiLLM(api_key="fake-key", max_retries=3, initial_delay=0.01)

    with patch("google.generativeai.GenerativeModel") as mock_model_cls:
        mock_instance = MagicMock()
        mock_instance.generate_content.side_effect = google_exceptions.PermissionDenied(
            "API key not valid"
        )
        mock_model_cls.return_value = mock_instance

        with pytest.raises(LLMAuthError, match="Authentication failed"):
            client.generate_text("System", "Prompt")

        # Must not retry fatal auth errors
        assert mock_instance.generate_content.call_count == 1


def test_get_llm_factory():
    with patch("app.config.GEMINI_API_KEY", "test-key"):
        gemini_client = get_llm("gemini")
        assert isinstance(gemini_client, GeminiLLM)

    with pytest.raises(NotImplementedError, match="Groq provider is scheduled"):
        get_llm("groq")

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        get_llm("invalid-provider")


def test_script_main_without_api_key(capsys):
    import scripts.test_gemini_call as script

    with (
        patch.dict("os.environ", {"GEMINI_API_KEY": ""}, clear=True),
        patch("app.config.GEMINI_API_KEY", ""),
    ):
        code = script.main()
        assert code == 0
        captured = capsys.readouterr()
        assert "NOTICE: GEMINI_API_KEY is not set" in captured.out


def test_script_main_with_api_key_and_mock(capsys):
    import scripts.test_gemini_call as script

    mock_resp = MockResponse(
        '{"title": "Birthday Dinner", "guest_count": 15, "city": "Bengaluru", "estimated_budget": 30000.0}'
    )

    with (
        patch.dict("os.environ", {"GEMINI_API_KEY": "dummy-key"}),
        patch("app.config.GEMINI_API_KEY", "dummy-key"),
        patch("google.generativeai.GenerativeModel") as mock_model_cls,
    ):
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = mock_resp
        mock_model_cls.return_value = mock_instance

        code = script.main()
        assert code == 0
        captured = capsys.readouterr()
        assert "Real Call Successful!" in captured.out
        assert "Birthday Dinner" in captured.out
