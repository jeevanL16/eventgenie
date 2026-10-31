"""EventGenie — Main Streamlit Application.

Professional event-planning landing page with multilingual planner.
All CSS lives in app/ui/styles.css; components in app/ui/components.py.
Dynamic user text is always escaped; static trusted HTML only via unsafe_allow_html.
"""

import html
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app import config  # noqa: E402
from app.i18n import t  # noqa: E402
from app.pipeline import GenerationResult, generate_plan_v0  # noqa: E402
from app.schemas import EventPlan, Lang, PlanInputs  # noqa: E402
from app.ui.components import (  # noqa: E402
    cta_banner,
    disclaimer_banner,
    event_cards,
    footer,
    hero,
    how_it_works,
    nav_bar,
    result_ribbon,
    sample_preview,
)
from app.ui.html import render_html  # noqa: E402
from app.ui.theme import apply_theme  # noqa: E402

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="EventGenie — AI Event Planner",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def format_currency(amount: float, currency: str) -> str:
    """Format currency values with standard comma separation."""
    return f"{currency} {amount:,.2f}"


def _get_lang() -> str:
    """Return the current language from session state."""
    return st.session_state.get("app_lang", "en")


# ---------------------------------------------------------------------------
# Sidebar: Language + BYOK
# ---------------------------------------------------------------------------
def _render_sidebar() -> Any:
    """Render language selector and BYOK controls in the sidebar."""
    lang = _get_lang()
    with st.sidebar:
        st.markdown(f"### 🌐 {t('language', lang)}")
        lang_options: dict[Lang, str] = {
            "en": "English",
            "hi": "Hindi (हिन्दी)",
            "kn": "Kannada (ಕನ್ನಡ)",
            "te": "Telugu (తెలుగు)",
            "ta": "Tamil (தமிழ்)",
            "mr": "Marathi (मराठी)",
        }
        selected_lang = st.selectbox(
            t("language", lang),
            options=list(lang_options.keys()),
            format_func=lambda k: lang_options[k],
            index=list(lang_options.keys()).index(st.session_state.get("app_lang", "en")),
            key="sidebar_lang",
            label_visibility="collapsed",
            help=t("planner_help_language", lang),
        )
        if selected_lang != st.session_state.get("app_lang", "en"):
            st.session_state.app_lang = selected_lang
            st.rerun()

        st.markdown("---")
        st.markdown(f"### 🔑 {t('byok_title', lang)}")
        st.caption(t("byok_caption", lang))
        user_gemini_key = st.text_input(
            t("byok_gemini", lang),
            type="password",
            placeholder="AIzaSy...",
            key="byok_gemini_key",
            help="Enter your free Gemini key from Google AI Studio.",
        )
        user_groq_key = st.text_input(
            t("byok_groq", lang),
            type="password",
            placeholder="gsk_...",
            key="byok_groq_key",
            help="Enter your free Groq key from console.groq.com.",
        )
        st.markdown("---")
        st.markdown(f"### ⚙️ {t('engine_info', lang)}")
        st.caption(f"Provider Chain: `{config.LLM_CHAIN}`")
        if user_groq_key or user_gemini_key:
            st.success("Session API key override active.")

    g_key = st.session_state.get("byok_gemini_key", "").strip() or None
    gr_key = st.session_state.get("byok_groq_key", "").strip() or None
    if g_key or gr_key:
        from app.llm.router import LLMRouter

        return LLMRouter(gemini_api_key=g_key, groq_api_key=gr_key)
    return None


# ---------------------------------------------------------------------------
# Planner Form
# ---------------------------------------------------------------------------
def _render_planner_form(session_llm: Any, lang: str) -> None:
    """Render the structured intake form inside a styled card."""
    heading_html = (
        f'<h2 style="font-family: var(--font-heading); '
        f'color: var(--text-heading);">'
        f"📋 {html.escape(t('planner_title', lang))}</h2>"
    )
    render_html(heading_html)

    selected_type = st.session_state.get("selected_event_type")
    type_options = ["wedding", "birthday", "community"]
    type_index = type_options.index(selected_type) if selected_type in type_options else 0

    with st.form("event_intake_form"):
        event_type_choice = st.selectbox(
            t("event_type", lang),
            options=type_options,
            index=type_index,
            format_func=lambda x: {
                "wedding": f"💍 {t('wedding', lang)}",
                "birthday": f"🎂 {t('birthday', lang)}",
                "community": f"🎪 {t('community', lang)}",
            }.get(x, x.title()),
            key="input_event_type",
            help=t("planner_help_event_type", lang),
        )
        event_date = st.date_input(
            t("event_date", lang),
            value=date.today() + timedelta(days=90),
            min_value=date.today(),
            key="input_event_date",
            help=t("planner_help_date", lang),
        )
        c_guests, c_budget = st.columns(2)
        with c_guests:
            guests = st.number_input(
                t("guests", lang),
                min_value=1,
                max_value=100000,
                value=100,
                step=10,
                key="input_guests",
                help=t("planner_help_guests", lang),
            )
        with c_budget:
            total_budget = st.number_input(
                t("budget", lang),
                min_value=100.0,
                max_value=100000000.0,
                value=250000.0,
                step=5000.0,
                key="input_total_budget",
                help=t("planner_help_budget", lang),
            )

        c_city, c_curr = st.columns(2)
        with c_city:
            city = st.text_input(
                t("city", lang),
                value="Bengaluru",
                placeholder="e.g. Bengaluru, Mumbai, Jaipur",
                key="input_city",
                help=t("planner_help_city", lang),
            )
        with c_curr:
            currency = st.selectbox(
                t("currency", lang),
                options=["INR", "USD", "EUR", "GBP", "AED"],
                index=0,
                key="input_currency",
                help=t("planner_help_currency", lang),
            )

        vibe = st.text_input(
            t("vibe", lang),
            value="Warm, elegant, and festive",
            placeholder="e.g. Elegant, high-energy, rustic",
            key="input_vibe",
            help=t("planner_help_vibe", lang),
        )
        notes = st.text_area(
            t("notes", lang),
            value="Vegetarian catering; focus on interactive guest experiences.",
            placeholder="Dietary requirements, traditions, specific priorities...",
            key="input_notes",
            help=t("planner_help_notes", lang),
        )

        submitted = st.form_submit_button(
            f"✨ {t('generate', lang)}",
            use_container_width=True,
            type="primary",
        )
        if submitted:
            inputs = PlanInputs(
                event_type=event_type_choice,  # type: ignore
                event_date=event_date,
                guests=int(guests),
                total_budget=float(total_budget),
                currency=currency,
                city=city.strip(),
                lang=lang,  # type: ignore
                vibe=vibe.strip(),
                notes=notes.strip(),
            )
            with st.spinner(t("generating", lang)):
                result = generate_plan_v0(inputs, llm=session_llm)
                st.session_state.current_result = result


# ---------------------------------------------------------------------------
# Result Tabs
# ---------------------------------------------------------------------------
def _render_budget_tab(plan: EventPlan, lang: str) -> None:
    """Render budget table with integrity check."""
    st.markdown(f"#### 💰 {t('budget_breakdown', lang)}")
    budget_data = [
        {
            "Category": b.label,
            "Allocation (%)": f"{b.percent:.1f}%",
            f"Amount ({plan.currency})": f"{b.amount:,.2f}",
            "Notes": b.note or "Standard benchmark allocation",
        }
        for b in plan.budget
    ]
    st.dataframe(pd.DataFrame(budget_data), use_container_width=True, hide_index=True)

    computed_sum = round(sum(b.amount for b in plan.budget), 2)
    diff = round(computed_sum - plan.total_budget, 2)
    if abs(diff) <= 0.01:
        st.success(
            f"✅ {t('result_budget_verified', lang)}: "
            f"{format_currency(plan.total_budget, plan.currency)}"
        )
    else:
        st.warning(
            f"⚠️ {t('result_budget_mismatch', lang)}: "
            f"Sum is {computed_sum} vs expected {plan.total_budget}."
        )


def _render_timeline_tab(plan: EventPlan, lang: str) -> None:
    """Render backward-scheduled timeline milestones."""
    st.markdown(f"#### 📅 {t('timeline', lang)}")
    st.caption(f"Milestones planned backward from: **{plan.event_date.strftime('%A, %B %d, %Y')}**")
    timeline_data = [
        {
            "Due Date": t_item.due_date.strftime("%Y-%m-%d (%a)"),
            "Phase": t_item.phase,
            "Task": t_item.title,
            "Owner": t_item.owner,
            "Status": t_item.status.upper(),
        }
        for t_item in plan.timeline
    ]
    st.dataframe(pd.DataFrame(timeline_data), use_container_width=True, hide_index=True)


def _render_vendors_tab(plan: EventPlan, lang: str) -> None:
    """Render vendor checklists with questions, documents, and red flags."""
    st.markdown(f"#### 🤝 {t('vendor_checklist', lang)}")
    if not plan.vendors:
        st.write(t("result_vendors_empty", lang))
        return
    for v in plan.vendors:
        with st.expander(f"📌 {v.label} ({v.category_key.title()})", expanded=True):
            v_col1, v_col2 = st.columns(2)
            with v_col1:
                st.markdown("**Questions to Ask:**")
                for q in v.questions_to_ask:
                    st.markdown(f"- {q}")
                st.markdown("**Documents to Request:**")
                for doc in v.documents_to_request:
                    st.markdown(f"- 📄 {doc}")
            with v_col2:
                st.markdown("**⚠️ Warning Signals (Red Flags):**")
                for rf in v.red_flags:
                    safe_rf = html.escape(rf)
                    st.markdown(
                        f"- 🚩 **Caution:** <span style='color: var(--error); "
                        f"font-weight: 500;'>{safe_rf}</span>",
                        unsafe_allow_html=True,
                    )


def _render_ideas_tab(plan: EventPlan, lang: str) -> None:
    """Render personalized themes, menu, decor, activities, and extras."""
    st.markdown(f"#### 💡 {t('ideas', lang)}")
    st.markdown("##### 🎨 Recommended Themes")
    for th in plan.ideas.themes:
        st.markdown(f"- **{th}**")
    st.markdown("---")
    col_i1, col_i2 = st.columns(2)
    with col_i1:
        st.markdown("##### 🍽️ Food & Beverage Ideas")
        for item in plan.ideas.menu:
            st.markdown(f"- {item}")
        st.markdown("##### 🎯 Interactive Activities")
        for act in plan.ideas.activities:
            st.markdown(f"- {act}")
    with col_i2:
        st.markdown("##### 🌸 Decor Concepts")
        for dec in plan.ideas.decor:
            st.markdown(f"- {dec}")
        st.markdown("##### ✨ Thoughtful Extras & Favors")
        for ext in plan.ideas.extras:
            st.markdown(f"- {ext}")


def _render_observability(plan: EventPlan, result: GenerationResult, lang: str) -> None:
    """Render assumptions and telemetry expander."""
    with st.expander(f"🔍 {t('result_assumptions', lang)}", expanded=False):
        st.markdown(f"**{t('assumptions', lang)}:**")
        for asm in plan.assumptions:
            st.markdown(f"- {asm}")
        st.markdown("---")
        st.markdown(f"**{t('engine_info', lang)}:**")
        provider_display = (
            "Deterministic Fallback"
            if result.is_fallback
            else (result.provider.upper() if result.provider else "Standard LLM")
        )
        st.write(f"- {t('result_provider_label', lang)}: `{provider_display}`")
        if result.metadata:
            st.write(f"- Model: `{result.metadata.model}`")
            st.write(f"- Latency: `{result.metadata.latency_ms:.1f} ms`")
            st.write(
                f"- Tokens: `{result.metadata.total_tokens}` total "
                f"(Prompt: {result.metadata.prompt_tokens}, "
                f"Candidates: {result.metadata.completion_tokens})"
            )

    # Sources placeholder for RAG
    with st.expander(f"📚 {t('sources_placeholder', lang)}", expanded=False):
        st.caption("Knowledge base retrieval will appear here once RAG is enabled.")


# ---------------------------------------------------------------------------
# Plan Results
# ---------------------------------------------------------------------------
def _render_plan_results(result: GenerationResult, lang: str) -> None:
    """Render full plan output with ribbon, disclaimer, and 4 tabs."""
    plan = result.plan

    if result.is_fallback:
        st.warning(f"⚠️ {t('result_benchmark', lang)}")
    if result.notices:
        for note in result.notices:
            st.caption(f"ℹ️ {note}")

    result_ribbon(
        provider=result.provider,
        is_fallback=result.is_fallback,
        is_cached=getattr(result, "cached", False),
        event_type=plan.event_type,
        city=plan.city or "General Metro",
        guests=plan.guests,
        event_date_str=plan.event_date.strftime("%B %d, %Y"),
        currency_display=format_currency(plan.total_budget, plan.currency),
    )

    disclaimer_banner(lang)

    tab_budget, tab_timeline, tab_vendors, tab_ideas = st.tabs(
        [
            f"💰 {t('budget_breakdown', lang)}",
            f"📅 {t('timeline', lang)}",
            f"🤝 {t('vendor_checklist', lang)}",
            f"💡 {t('ideas', lang)}",
        ]
    )
    with tab_budget:
        _render_budget_tab(plan, lang)
    with tab_timeline:
        _render_timeline_tab(plan, lang)
    with tab_vendors:
        _render_vendors_tab(plan, lang)
    with tab_ideas:
        _render_ideas_tab(plan, lang)

    _render_observability(plan, result, lang)


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------
def main() -> None:
    """Streamlit entry point: composes landing page sections and planner."""
    load_dotenv(override=True)

    # Initialize session state
    if "current_result" not in st.session_state:
        st.session_state.current_result = None
    if "app_lang" not in st.session_state:
        st.session_state.app_lang = "en"
    if "selected_event_type" not in st.session_state:
        st.session_state.selected_event_type = None

    # Apply theme and render sidebar
    apply_theme()
    session_llm = _render_sidebar()
    lang = _get_lang()

    # --- Landing Page Sections ---
    nav_bar(lang)
    hero(lang)

    # Event type cards
    chosen_type = event_cards(lang)
    if chosen_type and chosen_type != st.session_state.get("selected_event_type"):
        st.session_state.selected_event_type = chosen_type
        st.rerun()

    how_it_works(lang)
    sample_preview(lang)

    # --- Planner Section ---
    render_html('<div id="planner-section" class="eg-anchor-target"></div>')
    st.markdown("---")
    disclaimer_banner(lang)

    col_form, col_results = st.columns([1, 1.8], gap="large")

    with col_form:
        _render_planner_form(session_llm, lang)

    with col_results:
        result = st.session_state.current_result
        if result:
            _render_plan_results(result, lang)
        else:
            # Empty state with demo scenarios
            st.info(
                f"👈 {t('planner_title', lang)}: Fill out the form to generate your "
                f"complete 4-part plan — or click an event card above!"
            )
            # Quick demo buttons
            st.markdown("### 🚀 Quick Demo")
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button(
                    "💍 Sample Wedding",
                    key="demo_wedding",
                    use_container_width=True,
                    help="Load a sample royal wedding plan in Jaipur",
                ):
                    inputs = PlanInputs(
                        event_type="wedding",
                        event_date=date.today() + timedelta(days=180),
                        guests=200,
                        total_budget=1200000.0,
                        city="Jaipur",
                        currency="INR",
                        lang=lang,  # type: ignore
                        vibe="Royal heritage",
                        notes="Traditional ceremonies with sangeet evening",
                    )
                    st.session_state.current_result = generate_plan_v0(inputs, llm=session_llm)
                    st.rerun()
            with c2:
                if st.button(
                    "🎂 Sample Birthday",
                    key="demo_birthday",
                    use_container_width=True,
                    help="Load a sample outdoor birthday party in Bengaluru",
                ):
                    inputs = PlanInputs(
                        event_type="birthday",
                        event_date=date.today() + timedelta(days=30),
                        guests=35,
                        total_budget=40000.0,
                        city="Bengaluru",
                        currency="INR",
                        lang=lang,  # type: ignore
                        vibe="Outdoor picnic with arcade games",
                        notes="Fun themes and personalized return gifts",
                    )
                    st.session_state.current_result = generate_plan_v0(inputs, llm=session_llm)
                    st.rerun()
            with c3:
                if st.button(
                    "🎪 Sample Community Event",
                    key="demo_community",
                    use_container_width=True,
                    help="Load a sample cultural street festival in Pune",
                ):
                    inputs = PlanInputs(
                        event_type="community",
                        event_date=date.today() + timedelta(days=60),
                        guests=400,
                        total_budget=150000.0,
                        city="Pune",
                        currency="INR",
                        lang=lang,  # type: ignore
                        vibe="Eco-conscious cultural street festival",
                        notes="Volunteer-run stalls and youth talent show",
                    )
                    st.session_state.current_result = generate_plan_v0(inputs, llm=session_llm)
                    st.rerun()

    # --- Closing sections ---
    cta_banner(lang)
    footer(lang)


if __name__ == "__main__":
    main()
