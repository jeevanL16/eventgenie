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


def test_streamlit_theme_config_exists_and_forces_light_mode():
    """Task C-01: .streamlit/config.toml forces light theme with accessible brand colors."""
    from pathlib import Path

    config_path = Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml"
    assert config_path.exists(), ".streamlit/config.toml must exist"
    content = config_path.read_text(encoding="utf-8")
    assert "[theme]" in content
    assert 'base = "light"' in content or 'base="light"' in content
    assert 'primaryColor = "#F5A623"' in content
    assert 'backgroundColor = "#FBF7F0"' in content
    assert 'secondaryBackgroundColor = "#FFFFFF"' in content
    assert 'textColor = "#2D1B4E"' in content
