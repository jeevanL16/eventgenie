"""Automated tests for EventGenie landing page and UI components (Tasks U-01 to U-08).

Verifies component rendering, session state updates from event cards,
accessibility attributes, and complete multilingual coverage without placeholders.
"""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.i18n import SUPPORTED_LANGUAGES, load_strings, t
from app.ui.components import (
    cta_banner,
    disclaimer_banner,
    footer,
    hero,
    how_it_works,
    nav_bar,
    result_ribbon,
    sample_preview,
)

MAIN_APP_PATH = str(Path(__file__).resolve().parent.parent / "app" / "main.py")


class TestLandingPageComponents:
    """Unit and integration tests for landing page UI components."""

    def test_all_components_render_without_error(self):
        """All component functions execute safely for every supported language."""
        for lang in SUPPORTED_LANGUAGES:
            nav_bar(lang)
            hero(lang)
            how_it_works(lang)
            sample_preview(lang)
            cta_banner(lang)
            footer(lang)
            disclaimer_banner(lang)
            result_ribbon(
                provider="groq",
                is_fallback=False,
                is_cached=True,
                event_type="wedding",
                city="Jaipur",
                guests=200,
                event_date_str="December 15, 2027",
                currency_display="INR 1,200,000.00",
            )

    def test_app_test_renders_all_landing_sections(self):
        """Streamlit AppTest verifies all landing page sections appear in the rendered app."""
        at = AppTest.from_file(MAIN_APP_PATH, default_timeout=20)
        at.run(timeout=20)
        assert not at.exception

        # Check skip link and navigation landmarks
        html_content = " ".join(m.value for m in at.markdown)
        assert "skip-link" in html_content
        assert "eg-nav" in html_content
        assert "eg-hero" in html_content
        assert "eg-cards" in html_content
        assert "eg-steps" in html_content
        assert "eg-preview" in html_content
        assert "eg-cta-banner" in html_content
        assert "eg-footer" in html_content

    def test_skip_link_css_offscreen_until_focus(self):
        """Skip link must be positioned off-screen (-9999px) until focused."""
        css_path = Path(__file__).resolve().parent.parent / "app" / "ui" / "styles.css"
        css_text = css_path.read_text(encoding="utf-8")
        assert ".skip-link" in css_text
        assert "left: -9999px;" in css_text
        assert ".skip-link:focus" in css_text
        assert "left: var(--sp-4);" in css_text

    def test_event_card_buttons_exist_and_set_selection(self):
        """Clicking an event-type card button sets session state to that event type."""
        at = AppTest.from_file(MAIN_APP_PATH, default_timeout=20)
        at.run(timeout=20)
        assert not at.exception

        # Find event card button for birthday
        bday_btn = next(
            (b for b in at.button if "Birthday" in b.label and "card_btn" in b.key), None
        )
        assert bday_btn is not None
        bday_btn.click().run(timeout=20)
        assert not at.exception
        assert at.session_state["selected_event_type"] == "birthday"

    def test_i18n_keys_have_no_empty_placeholders(self):
        """Every translation file must have non-empty strings for all landing page keys."""
        en_strings = load_strings("en")
        for lang in SUPPORTED_LANGUAGES:
            data = load_strings(lang)
            assert len(data) == len(en_strings), f"{lang} key count mismatch"
            for key, val in data.items():
                if key == "beta_notice" and lang == "en":
                    continue  # English doesn't show beta notice
                assert len(val.strip()) > 0, f"Empty string for key '{key}' in language '{lang}'"

    def test_honest_statistics_present_in_hero(self):
        """Hero must display truthful metrics: 6 languages, 3 event types, 4 outputs."""
        at = AppTest.from_file(MAIN_APP_PATH, default_timeout=20)
        at.run(timeout=20)
        hero_html = next(m.value for m in at.markdown if '<div class="eg-hero"' in m.value)
        assert "6" in hero_html
        assert "3" in hero_html
        assert "4" in hero_html
        assert t("stat_languages", "en") in hero_html
        assert t("stat_events", "en") in hero_html
        assert t("stat_outputs", "en") in hero_html
