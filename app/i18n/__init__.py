"""Internationalization (i18n) module for EventGenie.

Loads translation dictionaries from JSON files with automatic English fallback.
Supports en (English), hi (Hindi), kn (Kannada), te (Telugu), ta (Tamil), mr (Marathi).
"""

import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

I18N_DIR = Path(__file__).resolve().parent
SUPPORTED_LANGUAGES = ["en", "hi", "kn", "te", "ta", "mr"]


@lru_cache(maxsize=16)
def load_strings(lang: str) -> dict[str, str]:
    """Load JSON translation dictionary for a given language code."""
    safe_lang = lang.lower().strip()
    file_path = I18N_DIR / f"{safe_lang}.json"
    if not file_path.exists():
        file_path = I18N_DIR / "en.json"

    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to load i18n file for '%s': %s", lang, e)
        return {}


def t(key: str, lang: str = "en") -> str:
    """Retrieve localized string for key with English fallback.

    Args:
        key: String key in translation dictionary.
        lang: Target ISO language code ('en', 'hi', 'kn', 'te', 'ta', 'mr').

    Returns:
        Translated text if found, English equivalent if fallback, or key itself.
    """
    data = load_strings(lang)
    if key in data:
        return data[key]

    en_data = load_strings("en")
    return en_data.get(key, key)
