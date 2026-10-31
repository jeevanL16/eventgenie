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

    def test_scoped_link_and_button_css_overrides(self):
        """CSS must scope markdown links to prevent Streamlit default styles."""
        css_path = Path(__file__).resolve().parent.parent / "app" / "ui" / "styles.css"
        css_text = css_path.read_text(encoding="utf-8")
        assert ".stMarkdown a.eg-btn" in css_text
        assert ".stMarkdown .eg-brand" in css_text
        assert ".stMarkdown .eg-nav a:not(.eg-nav-cta)" in css_text
        assert "text-decoration: none !important;" in css_text
        assert "color: var(--btn-text) !important;" in css_text

    def test_color_contrast_ratios_meet_wcag_aa(self):
        """Text and button colors must meet WCAG AA (>= 4.5:1) contrast."""

        def luminance(hex_code: str) -> float:
            hex_code = hex_code.lstrip("#")
            r, g, b = [int(hex_code[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]

            def adjust(c):
                return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

            return 0.2126 * adjust(r) + 0.7152 * adjust(g) + 0.0722 * adjust(b)

        def contrast(c1: str, c2: str) -> float:
            l1 = luminance(c1)
            l2 = luminance(c2)
            return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

        # Plum text (#2D1B4E) on Ivory background (#FBF7F0) >= 4.5:1
        plum_ivory = contrast("#2D1B4E", "#FBF7F0")
        assert plum_ivory >= 4.5, f"Plum on ivory contrast {plum_ivory:.2f} < 4.5"

        # Ink text (#1C1235) on Gold button background (#F5A623) >= 4.5:1
        ink_gold = contrast("#1C1235", "#F5A623")
        assert ink_gold >= 4.5, f"Ink on gold contrast {ink_gold:.2f} < 4.5"

        # Verify white on gold does NOT meet AA (ensures we never use white text on gold)
        assert contrast("#FFFFFF", "#F5A623") < 4.5

    def test_streamlit_chrome_hidden_and_sticky_nav_z_index(self):
        """Task B-04: Streamlit chrome hidden and sticky nav has top z-index."""
        css_path = Path(__file__).resolve().parent.parent / "app" / "ui" / "styles.css"
        css_text = css_path.read_text(encoding="utf-8")
        assert 'header[data-testid="stHeader"]' in css_text
        assert '[data-testid="stToolbar"]' in css_text
        assert "display: none !important;" in css_text
        assert "padding-top: 70px !important;" in css_text
        assert "z-index: 99999;" in css_text

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
