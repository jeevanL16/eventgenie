"""EventGenie — main Streamlit application."""

import streamlit as st

st.set_page_config(
    page_title="EventGenie — AI Event Planner",
    page_icon="🎉",
    layout="wide",
)

st.title("🎉 EventGenie")
st.subheader("Your AI-powered multilingual event planner")

st.info(
    "⚠️ **All prices shown are labelled estimates, not real quotes.**\n\n"
    "EventGenie is under active development. "
    "Full planning features coming soon!"
)

st.markdown("---")

st.markdown(
    """
    ### What EventGenie will do

    - 💰 **Budget breakdown** — percent + amount per category
    - 📅 **Backward-scheduled timeline** — real dates working back from the event
    - 📋 **Vendor checklist** — questions, documents, red flags
    - 💡 **Personalized ideas** — themes, menu, activities, decor, extras
    - 📄 **Exports** — PDF and `.ics` calendar
    - 🌐 **6 languages** — English, Hindi, Kannada, Telugu, Tamil, Marathi

    **Supported event types (v1):** Wedding · Birthday · Community Event
    """
)

st.markdown("---")
st.caption("Built with Streamlit · Powered by Google Gemini · $0 budget")
