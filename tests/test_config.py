"""Unit tests for configuration loading from env and Streamlit secrets."""

from unittest.mock import MagicMock, patch

from app.config import get_setting


def test_get_setting_from_env():
    with patch.dict("os.environ", {"TEST_KEY": "from_env"}):
        assert get_setting("TEST_KEY", default="default") == "from_env"


def test_get_setting_fallback_to_st_secrets():
    mock_secrets = {"TEST_KEY": "from_secrets"}

    with patch.dict("os.environ", {}, clear=True):
        with patch("streamlit.secrets", mock_secrets, create=True):
            assert get_setting("TEST_KEY", default="default") == "from_secrets"


def test_get_setting_env_takes_precedence_over_secrets():
    mock_secrets = {"TEST_KEY": "from_secrets"}

    with patch.dict("os.environ", {"TEST_KEY": "from_env"}):
        with patch("streamlit.secrets", mock_secrets, create=True):
            assert get_setting("TEST_KEY", default="default") == "from_env"


def test_get_setting_when_secrets_raises_file_not_found():
    mock_st = MagicMock()
    # Emulate accessing st.secrets when no secrets.toml exists
    type(mock_st).secrets = property(
        lambda self: (_ for _ in ()).throw(FileNotFoundError("No secrets file"))
    )

    with patch.dict("os.environ", {}, clear=True):
        with patch.dict("sys.modules", {"streamlit": mock_st}):
            assert get_setting("MISSING_KEY", default="fallback_val") == "fallback_val"
