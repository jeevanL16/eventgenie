"""Theme loader — injects CSS and page configuration once per session."""

from pathlib import Path

import streamlit as st

_CSS_PATH = Path(__file__).resolve().parent / "styles.css"


def apply_theme() -> None:
    """Load styles.css and inject into Streamlit via markdown."""
    css_text = _CSS_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{css_text}</style>", unsafe_allow_html=True)
