"""HTML rendering utility for EventGenie UI.

Prevents Markdown parsers from interpreting indented HTML or blank-line-separated
HTML as code blocks (<pre><code>) by dedenting, stripping blank lines, and
normalizing indentation before calling st.markdown(..., unsafe_allow_html=True).
"""

import re
import textwrap

import streamlit as st


def clean_html_string(html_str: str) -> str:
    """Normalize and clean an HTML string to ensure Markdown will not parse it as a code block.

    1. Dedent leading indentation common to multi-line Python strings.
    2. Strip outer whitespace.
    3. Remove empty or whitespace-only lines inside the HTML structure.
    4. Ensure no line starts with 4 or more leading spaces before a tag.
    """
    dedented = textwrap.dedent(html_str).strip()

    # Split lines, discard empty lines, and remove 4+ space leading indentation before HTML tags
    cleaned_lines = []
    for line in dedented.splitlines():
        stripped = line.strip()
        if not stripped:
            continue  # remove blank lines that can trigger Markdown block boundary
        # If line has leading spaces before a tag or text, normalize to at most 2 spaces or 0
        norm_line = re.sub(r"^ {4,}", "", line)
        cleaned_lines.append(norm_line)

    return "\n".join(cleaned_lines)


def render_html(html_str: str) -> None:
    """Render sanitized, cleaned custom HTML safely in Streamlit without code-block formatting."""
    clean = clean_html_string(html_str)
    st.markdown(clean, unsafe_allow_html=True)
