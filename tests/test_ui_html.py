"""Tests for HTML rendering utility and code-block prevention (Task B-01).

Validates that custom HTML is normalized, dedented, stripped of blank lines,
and contains no 4+ space indentations that Markdown could treat as code blocks.
"""

from pathlib import Path

from streamlit.testing.v1 import AppTest

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
from app.ui.html import clean_html_string

MAIN_APP_PATH = str(Path(__file__).resolve().parent.parent / "app" / "main.py")


def test_clean_html_string_removes_four_plus_indent_and_blank_lines():
    raw = (
        '        <div class="test">\n'
        "            \n"
        "            <p>Hello world</p>\n"
        "            \n"
        "        </div>\n"
    )
    cleaned = clean_html_string(raw)
    for line in cleaned.splitlines():
        assert not line.startswith("    <"), f"Line starts with 4 spaces: {line}"
        assert len(line.strip()) > 0, "Empty line found in cleaned HTML"


def test_components_produce_no_code_block_indentation(monkeypatch):
    rendered_strings = []

    def mock_render(html_str):
        cleaned = clean_html_string(html_str)
        rendered_strings.append(cleaned)

    monkeypatch.setattr("app.ui.components.render_html", mock_render)

    nav_bar("en")
    hero("en")
    how_it_works("en")
    sample_preview("en")
    cta_banner("en")
    footer("en")
    disclaimer_banner("en")
    result_ribbon("groq", False, True, "wedding", "Jaipur", 200, "Dec 15, 2027", "INR 12,00,000")

    assert len(rendered_strings) == 8
    for html_doc in rendered_strings:
        for line in html_doc.splitlines():
            assert not line.startswith("    <"), f"Found 4+ space indent before tag: {line}"
            assert len(line.strip()) > 0, f"Found empty line: {html_doc}"


def test_app_test_contains_no_raw_code_blocks_in_sample_preview():
    at = AppTest.from_file(MAIN_APP_PATH, default_timeout=20)
    at.run(timeout=20)
    assert not at.exception
    # Ensure no st.code widget was rendered
    assert len(at.code) == 0, f"Unexpected st.code elements: {at.code}"
    # Ensure no markdown element contains a raw <pre><code> block
    for md in at.markdown:
        assert "<pre>" not in md.value, f"Raw <pre> found in markdown: {md.value}"
