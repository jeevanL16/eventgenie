"""Unit tests for GeminiLLM with mocked client and retry logic.

Tests the google-genai unified SDK integration (v2.x).
"""

from unittest.mock import MagicMock, patch

import pytest
from google.genai import errors as genai_errors
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
    def __init__(self, text: str, usage=None, parsed=None):
        self.text = text
        self.usage_metadata = usage or MockUsageMetadata()
        self.parsed = parsed


def _make_client_error(code: int, message: str) -> genai_errors.ClientError:
    """Create a ClientError with the correct constructor signature."""
    return genai_errors.ClientError(code, {"error": {"message": message}})


def _make_server_error(code: int, message: str) -> genai_errors.ServerError:
    """Create a ServerError with the correct constructor signature."""
    return genai_errors.ServerError(code, {"error": {"message": message}})


def test_missing_api_key_raises_auth_error():
    client = GeminiLLM(api_key="")
    with pytest.raises(LLMAuthError, match="GEMINI_API_KEY is not configured"):
        client.generate_text("System", "Hello")

    with pytest.raises(LLMAuthError, match="GEMINI_API_KEY is not configured"):
        client.generate_json("System", "Generate JSON", TinyEvent)


def test_generate_json_success():
    with patch("google.genai.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_resp = MockResponse(
            '{"title": "Birthday Party", "guest_count": 25, "city": "Bengaluru"}'
        )
        mock_client_instance.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client_instance

        client = GeminiLLM(api_key="fake-key", model_name="gemini-2.5-flash")

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
        assert client.last_metadata.model == "gemini-2.5-flash"
        assert client.last_metadata.latency_ms >= 0
        assert client.last_metadata.prompt_tokens == 12
        assert client.last_metadata.completion_tokens == 24
        assert client.last_metadata.total_tokens == 36
        assert "Birthday Party" in client.last_metadata.raw_response


def test_generate_json_uses_parsed_attribute():
    """Test that the SDK's built-in parsed attribute is used when available."""
    parsed_event = TinyEvent(title="Parsed Event", guest_count=50, city="Mumbai")

    with patch("google.genai.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_resp = MockResponse(
            '{"title": "Parsed Event", "guest_count": 50, "city": "Mumbai"}',
            parsed=parsed_event,
        )
        mock_client_instance.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client_instance

        client = GeminiLLM(api_key="fake-key")
        result = client.generate_json("System", "Prompt", TinyEvent)

        assert result is parsed_event
        assert result.title == "Parsed Event"


def test_generate_json_with_markdown_fences():
    with patch("google.genai.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_resp = MockResponse(
            '```json\n{"title": "Anniversary Dinner", "guest_count": 10, "city": "Mumbai"}\n```'
        )
        mock_client_instance.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client_instance

        client = GeminiLLM(api_key="fake-key")
        result = client.generate_json("System", "Prompt", TinyEvent)
        assert result.title == "Anniversary Dinner"
        assert result.guest_count == 10
        assert result.city == "Mumbai"


def test_generate_json_schema_validation_error():
    with patch("google.genai.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        # guest_count <= 0 violates gt=0 constraint in TinyEvent
        mock_resp = MockResponse('{"title": "Invalid Party", "guest_count": -5, "city": "Delhi"}')
        mock_client_instance.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client_instance

        client = GeminiLLM(api_key="fake-key")
        with pytest.raises(LLMValidationError) as exc_info:
            client.generate_json("System", "Prompt", TinyEvent)
        assert "Failed to validate response against schema TinyEvent" in str(exc_info.value)
        assert exc_info.value.raw_response == mock_resp.text


def test_generate_json_malformed_json_error():
    with patch("google.genai.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_resp = MockResponse("This is not JSON at all!")
        mock_client_instance.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client_instance

        client = GeminiLLM(api_key="fake-key")
        with pytest.raises(LLMValidationError):
            client.generate_json("System", "Prompt", TinyEvent)


def test_generate_text_success():
    with patch("google.genai.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_resp = MockResponse("Here are three themes for the party.")
        mock_client_instance.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client_instance

        client = GeminiLLM(api_key="fake-key", model_name="gemini-2.5-flash")
        text = client.generate_text("System", "Generate ideas", temperature=0.7)
        assert text == "Here are three themes for the party."
        assert client.last_metadata is not None
        assert client.last_metadata.raw_response == "Here are three themes for the party."


def test_retry_on_429_success_after_retry():
    with patch("google.genai.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_resp = MockResponse("Success after 429")
        # First call raises a 429 ClientError, then succeeds
        rate_limit_err = _make_client_error(429, "Resource Exhausted: quota exceeded")
        mock_client_instance.models.generate_content.side_effect = [
            rate_limit_err,
            mock_resp,
        ]
        mock_client_cls.return_value = mock_client_instance

        client = GeminiLLM(api_key="fake-key", max_retries=2, initial_delay=0.01)
        result = client.generate_text("System", "Prompt")
        assert result == "Success after 429"
        assert mock_client_instance.models.generate_content.call_count == 2


def test_retry_on_429_exhausted_raises_rate_limit_error():
    with patch("google.genai.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        rate_limit_err = _make_client_error(429, "Resource Exhausted: quota exceeded")
        mock_client_instance.models.generate_content.side_effect = rate_limit_err
        mock_client_cls.return_value = mock_client_instance

        client = GeminiLLM(api_key="fake-key", max_retries=2, initial_delay=0.01)
        with pytest.raises(LLMRateLimitError, match="Gemini rate limit exceeded"):
            client.generate_text("System", "Prompt")

        assert mock_client_instance.models.generate_content.call_count == 3  # initial + 2 retries


def test_retry_on_server_error():
    with patch("google.genai.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_content.side_effect = _make_server_error(
            503, "Service Unavailable"
        )
        mock_client_cls.return_value = mock_client_instance

        client = GeminiLLM(api_key="fake-key", max_retries=1, initial_delay=0.01)
        with pytest.raises(LLMError, match="Gemini server error after 1 retries"):
            client.generate_text("System", "Prompt")

        assert mock_client_instance.models.generate_content.call_count == 2


def test_retry_on_timeout():
    with patch("google.genai.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_content.side_effect = TimeoutError("Request timed out")
        mock_client_cls.return_value = mock_client_instance

        client = GeminiLLM(api_key="fake-key", max_retries=1, initial_delay=0.01)
        with pytest.raises(LLMTimeoutError, match="Gemini call timed out"):
            client.generate_text("System", "Prompt")


def test_fatal_auth_error_not_retried():
    with patch("google.genai.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        auth_err = _make_client_error(403, "Permission Denied: API key not valid")
        mock_client_instance.models.generate_content.side_effect = auth_err
        mock_client_cls.return_value = mock_client_instance

        client = GeminiLLM(api_key="fake-key", max_retries=3, initial_delay=0.01)
        with pytest.raises(LLMAuthError, match="Authentication failed"):
            client.generate_text("System", "Prompt")

        # Must not retry fatal auth errors
        assert mock_client_instance.models.generate_content.call_count == 1


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
        patch("google.genai.Client") as mock_client_cls,
    ):
        mock_client_instance = MagicMock()
        mock_client_instance.models.generate_content.return_value = mock_resp
        mock_client_cls.return_value = mock_client_instance

        code = script.main()
        assert code == 0
        captured = capsys.readouterr()
        assert "Real Call Successful!" in captured.out
        assert "Birthday Dinner" in captured.out
