"""Tests for app.i18n internationalization utilities."""

import json

import pytest

from app.i18n import I18N_DIR, SUPPORTED_LANGUAGES, t


def test_all_i18n_files_have_identical_keys():
    """Verify that every supported language has the exact same set of translation keys."""
    key_sets = {}
    for lang in SUPPORTED_LANGUAGES:
        file_path = I18N_DIR / f"{lang}.json"
        assert file_path.exists(), f"Missing i18n file: {file_path}"
        data = json.loads(file_path.read_text(encoding="utf-8"))
        key_sets[lang] = set(data.keys())

    base_keys = key_sets["en"]
    for lang in SUPPORTED_LANGUAGES:
        diff = base_keys.symmetric_difference(key_sets[lang])
        assert not diff, f"Language '{lang}' has mismatched keys with 'en': {diff}"


@pytest.mark.parametrize("lang", ["hi", "kn", "te", "ta", "mr"])
def test_t_function_translates_indic_languages(lang: str):
    """Verify that helper t() returns non-empty localized strings for Indic languages."""
    val = t("wedding", lang)
    assert val is not None and len(val) > 0
    # Must be different from empty string
    assert val != ""


def test_t_fallback_to_english():
    """Unknown or unconfigured languages must fall back safely to English."""
    assert t("wedding", "fr") == "Wedding"
    assert t("non_existent_key_12345", "en") == "non_existent_key_12345"
