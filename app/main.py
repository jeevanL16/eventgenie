"""EventGenie — Main Streamlit Application.

Interactive multilingual event planner with structured intake form,
instant budget breakdown, backward-scheduled timeline, vendor checklist,
and creative ideas.
"""

import html
import os  # noqa: E402
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv  # noqa: E402

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app import config  # noqa: E402
from app.pipeline import GenerationResult, generate_plan_v0  # noqa: E402
from app.schemas import EventPlan, Lang, PlanInputs  # noqa: E402

# Page Configuration
st.set_page_config(
    page_title="EventGenie — GenAI Event Planner",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.2rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 12px;
    }
    .disclaimer-banner {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 0.9rem;
        margin-bottom: 16px;
        border: 1px solid #FCD34D;
    }
    .badge-tag {
        display: inline-block;
        padding: 3px 8px;
        font-size: 0.8rem;
        font-weight: 600;
        border-radius: 4px;
        background-color: #EEF2FF;
        color: #4F46E5;
        margin-right: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def format_currency(amount: float, currency: str) -> str:
    """Format currency values with standard comma separation."""
    return f"{currency} {amount:,.2f}"


def _render_header() -> None:
    """Render top application title, description, and disclaimer banner."""
    st.markdown('<div class="main-header">✨ EventGenie</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">GenAI-powered planning assistant that helps you organize '
        "weddings, birthdays, and community events with budgets, timelines, vendor checklists, "
        "and personalized ideas.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="disclaimer-banner">⚠️ <strong>Estimates Only:</strong> All budget allocations, '
        "prices, and vendor questions are benchmark estimates and do not represent contractual quotes.</div>",
        unsafe_allow_html=True,
    )


def _render_byok_sidebar() -> Any:
    """Render Bring Your Own Key controls in the sidebar and return session LLM instance."""
    with st.sidebar:
        st.markdown("### 🔑 Bring Your Own Key")
        st.caption(
            "Optional: Use your own free API keys. Keys remain strictly in session state "
            "memory and are never saved to disk or logged."
        )
        user_gemini_key = st.text_input(
            "Google Gemini API Key",
            type="password",
            placeholder="AIzaSy...",
            key="byok_gemini_key",
            help="Enter your free Gemini key from Google AI Studio.",
        )
        user_groq_key = st.text_input(
            "Groq API Key",
            type="password",
            placeholder="gsk_...",
            key="byok_groq_key",
            help="Enter your free Groq key from console.groq.com.",
        )
        st.markdown("---")
        st.markdown("### ⚙️ Engine Info")
        st.caption(f"Provider Chain: `{config.LLM_CHAIN}`")
        if user_groq_key or user_gemini_key:
            st.success("Session API key override active.")

    g_key = st.session_state.get("byok_gemini_key", "").strip() or None
    gr_key = st.session_state.get("byok_groq_key", "").strip() or None
    if g_key or gr_key:
        from app.llm.router import LLMRouter

        return LLMRouter(gemini_api_key=g_key, groq_api_key=gr_key)
    return None


def _render_intake_form(session_llm: Any) -> None:
    """Render the structured user intake form and process submission."""
    st.subheader("📋 Event Details")
    active_model = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
    st.caption(f"🤖 LLM Engine: `{active_model}`")

    with st.form("event_intake_form"):
        event_type_choice = st.selectbox(
            "Event Type",
            options=["wedding", "birthday", "community"],
            format_func=lambda x: {
                "wedding": "💍 Wedding",
                "birthday": "🎂 Birthday Party",
                "community": "🎪 Community Event",
            }.get(x, x.title()),
            key="input_event_type",
        )
        event_date = st.date_input(
            "Event Date",
            value=date.today() + timedelta(days=90),
            min_value=date.today(),
            key="input_event_date",
        )
        c_guests, c_budget = st.columns(2)
        with c_guests:
            guests = st.number_input(
                "Guest Count", min_value=1, max_value=100000, value=100, step=10, key="input_guests"
            )
        with c_budget:
            total_budget = st.number_input(
                "Total Budget",
                min_value=100.0,
                max_value=100000000.0,
                value=250000.0,
                step=5000.0,
                key="input_total_budget",
            )

        c_city, c_curr = st.columns(2)
        with c_city:
            city = st.text_input(
                "City / Location",
                value="Bengaluru",
                placeholder="e.g. Bengaluru, Mumbai, Jaipur",
                key="input_city",
            )
        with c_curr:
            currency = st.selectbox(
                "Currency",
                options=["INR", "USD", "EUR", "GBP", "AED"],
                index=0,
                key="input_currency",
            )

        lang_options: dict[Lang, str] = {
            "en": "English",
            "hi": "Hindi (हिन्दी) [Beta]",
            "kn": "Kannada (ಕನ್ನಡ) [Beta]",
            "te": "Telugu (తెలుగు) [Beta]",
            "ta": "Tamil (தமிழ்) [Beta]",
            "mr": "Marathi (मराठी) [Beta]",
        }
        selected_lang = st.selectbox(
            "Target Output Language",
            options=list(lang_options.keys()),
            format_func=lambda k: lang_options[k],
            index=0,
            key="input_lang",
        )
        vibe = st.text_input(
            "Desired Vibe / Style",
            value="Warm, elegant, and festive",
            placeholder="e.g. Elegant, high-energy, rustic picnic",
            key="input_vibe",
        )
        notes = st.text_area(
            "Special Notes / Constraints",
            value="Vegetarian catering; focus on interactive guest experiences.",
            placeholder="Dietary requirements, traditions, specific priorities...",
            key="input_notes",
        )

        submitted = st.form_submit_button(
            "✨ Generate Event Plan", use_container_width=True, type="primary"
        )
        if submitted:
            inputs = PlanInputs(
                event_type=event_type_choice,  # type: ignore
                event_date=event_date,
                guests=int(guests),
                total_budget=float(total_budget),
                currency=currency,
                city=city.strip(),
                lang=selected_lang,  # type: ignore
                vibe=vibe.strip(),
                notes=notes.strip(),
            )
            with st.spinner("Generating plan and computing deterministic allocations..."):
                result = generate_plan_v0(inputs, llm=session_llm)
                st.session_state.current_result = result


def _render_demo_scenarios(session_llm: Any) -> None:
    """Render pre-configured scenario shortcuts for instant 1-click evaluation."""
    st.info(
        "👈 **Plan your next event in seconds:** Fill out the intake form on the left to "
        "generate your complete 4-part plan (Budget Breakdown, Scheduled Timeline, Vendor Checklist, "
        "and Creative Ideas) — or click a demo scenario below!"
    )
    st.markdown("### Quick Demo Scenarios")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("💍 Sample Wedding", use_container_width=True):
            inputs = PlanInputs(
                event_type="wedding",
                event_date=date.today() + timedelta(days=180),
                guests=200,
                total_budget=1200000.0,
                city="Jaipur",
                currency="INR",
                vibe="Royal Rajasthani heritage",
                notes="Traditional ceremonies with sangeet evening",
            )
            st.session_state.current_result = generate_plan_v0(inputs, llm=session_llm)
            st.rerun()

    with c2:
        if st.button("🎂 Sample Birthday", use_container_width=True):
            inputs = PlanInputs(
                event_type="birthday",
                event_date=date.today() + timedelta(days=30),
                guests=35,
                total_budget=40000.0,
                city="Bengaluru",
                currency="INR",
                vibe="Outdoor picnic with arcade games",
                notes="Fun themes and personalized return gifts",
            )
            st.session_state.current_result = generate_plan_v0(inputs, llm=session_llm)
            st.rerun()

    with c3:
        if st.button("🎪 Sample Community Event", use_container_width=True):
            inputs = PlanInputs(
                event_type="community",
                event_date=date.today() + timedelta(days=60),
                guests=400,
                total_budget=150000.0,
                city="Pune",
                currency="INR",
                vibe="Eco-conscious cultural street festival",
                notes="Volunteer-run stalls and youth talent show",
            )
            st.session_state.current_result = generate_plan_v0(inputs, llm=session_llm)
            st.rerun()


def _render_plan_ribbon(plan: EventPlan, result: GenerationResult) -> None:
    """Render status indicators and overview metric cards for generated plan."""
    if result.is_fallback:
        st.warning(
            "⚠️ **Benchmark Plan:** AI service is busy, showing a benchmark plan. "
            "Try again later or add your own key in the sidebar."
        )
    if result.notices:
        for note in result.notices:
            st.caption(f"ℹ️ {note}")

    safe_provider = html.escape(result.provider.upper() if result.provider else "LLM")
    provider_badge = (
        '<span class="badge-tag" style="background-color: #FEF3C7; color: #92400E;">⚡ Benchmark Fallback</span>'
        if result.is_fallback
        else f'<span class="badge-tag" style="background-color: #ECFDF5; color: #065F46;">🤖 Served by: {safe_provider}</span>'
    )
    safe_event_type = html.escape(plan.event_type.upper())
    safe_city = html.escape(plan.city or "General Metro")
    safe_curr_display = html.escape(format_currency(plan.total_budget, plan.currency))

    st.markdown(
        f"""
        <div class="metric-card">
            {provider_badge}
            <span class="badge-tag">{safe_event_type}</span>
            <span class="badge-tag">📍 {safe_city}</span>
            <span class="badge-tag">👥 {plan.guests} Guests</span>
            <span class="badge-tag">📅 {plan.event_date.strftime("%B %d, %Y")}</span>
            <span class="badge-tag">💰 {safe_curr_display}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_budget_tab(plan: EventPlan) -> None:
    """Render budget distribution table and exact sum integrity check."""
    st.markdown("#### Estimated Budget Allocations")
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
            f"✅ Budget Integrity Verified: Lines sum exactly to {format_currency(plan.total_budget, plan.currency)} (100.0%)."
        )
    else:
        st.warning(
            f"⚠️ Budget mismatch detected: Sum is {computed_sum} vs expected {plan.total_budget}."
        )


def _render_timeline_tab(plan: EventPlan) -> None:
    """Render backward-scheduled timeline task milestones."""
    st.markdown("#### Backward-Scheduled Action Plan")
    st.caption(
        f"Milestones planned backward from event date: **{plan.event_date.strftime('%A, %B %d, %Y')}**"
    )
    timeline_data = [
        {
            "Due Date": t.due_date.strftime("%Y-%m-%d (%a)"),
            "Phase": t.phase,
            "Task Title": t.title,
            "Owner": t.owner,
            "Status": t.status.upper(),
        }
        for t in plan.timeline
    ]
    st.dataframe(pd.DataFrame(timeline_data), use_container_width=True, hide_index=True)


def _render_vendors_tab(plan: EventPlan) -> None:
    """Render vendor checklists with questions, documents, and red flags."""
    st.markdown("#### Vendor Due Diligence Checklists")
    if not plan.vendors:
        st.write("No specific vendor checklists generated.")
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
                st.markdown("**⚠️ Red Flags:**")
                for rf in v.red_flags:
                    safe_rf = html.escape(rf)
                    st.markdown(
                        f"- 🚩 <span style='color: #DC2626;'>{safe_rf}</span>",
                        unsafe_allow_html=True,
                    )


def _render_ideas_tab(plan: EventPlan) -> None:
    """Render personalized themes, menu ideas, decor, and activities."""
    st.markdown("#### Creative Concepts & Recommendations")
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


def _render_observability_expander(plan: EventPlan, result: GenerationResult) -> None:
    """Render plan assumptions and telemetry information."""
    with st.expander("🔍 Planning Assumptions & Observability", expanded=False):
        st.markdown("**Assumptions Made:**")
        for asm in plan.assumptions:
            st.markdown(f"- {asm}")
        st.markdown("---")
        st.markdown("**Engine & Telemetry:**")
        provider_display = (
            "Deterministic Fallback"
            if result.is_fallback
            else (result.provider.upper() if result.provider else "Standard LLM")
        )
        st.write(f"- Active Provider: `{provider_display}`")
        if result.metadata:
            st.write(f"- Model: `{result.metadata.model}`")
            st.write(f"- Latency: `{result.metadata.latency_ms:.1f} ms`")
            st.write(
                f"- Tokens: `{result.metadata.total_tokens}` total "
                f"(Prompt: {result.metadata.prompt_tokens}, Candidates: {result.metadata.completion_tokens})"
            )


def _render_plan_content(session_llm: Any) -> None:
    """Render either demo scenario buttons or complete multi-tab plan output."""
    result = st.session_state.current_result
    if not result:
        _render_demo_scenarios(session_llm)
        return

    plan = result.plan
    _render_plan_ribbon(plan, result)

    tab_budget, tab_timeline, tab_vendors, tab_ideas = st.tabs(
        [
            "💰 Budget Breakdown",
            "📅 Scheduled Timeline",
            "🤝 Vendor Checklist",
            "💡 Creative Ideas",
        ]
    )
    with tab_budget:
        _render_budget_tab(plan)
    with tab_timeline:
        _render_timeline_tab(plan)
    with tab_vendors:
        _render_vendors_tab(plan)
    with tab_ideas:
        _render_ideas_tab(plan)

    _render_observability_expander(plan, result)


def main() -> None:
    """Streamlit entry point: sets up state, sidebar, layout, and renderers."""
    load_dotenv(override=True)
    session_llm = _render_byok_sidebar()
    _render_header()

    if "current_result" not in st.session_state:
        st.session_state.current_result = None

    col_form, col_content = st.columns([1, 1.8], gap="large")
    with col_form:
        _render_intake_form(session_llm)
    with col_content:
        _render_plan_content(session_llm)


if __name__ == "__main__":
    main()
