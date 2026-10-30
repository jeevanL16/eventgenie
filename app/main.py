"""EventGenie — Main Streamlit Application.

Interactive multilingual event planner with structured intake form,
instant budget breakdown, backward-scheduled timeline, vendor checklist,
and creative ideas.
"""

import os  # noqa: E402
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv  # noqa: E402

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app import config  # noqa: E402
from app.pipeline import generate_plan_v0  # noqa: E402
from app.schemas import Lang, PlanInputs  # noqa: E402

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


def main():
    load_dotenv(override=True)

    # Sidebar: BYOK Configuration (Session-only, never logged or stored)
    with st.sidebar:
        st.markdown("### 🔑 Bring Your Own Key")
        st.caption(
            "Optional: Use your own free API keys. Keys remain strictly in session state memory and are never saved to disk or logged."
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

    def _resolve_session_llm():
        g_key = st.session_state.get("byok_gemini_key", "").strip() or None
        gr_key = st.session_state.get("byok_groq_key", "").strip() or None
        if g_key or gr_key:
            from app.llm.router import LLMRouter

            return LLMRouter(gemini_api_key=g_key, groq_api_key=gr_key)
        return None

    # Top Application Header
    st.markdown('<div class="main-header">✨ EventGenie</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Multilingual GenAI Event Planner · $0 Free-Tier Stack</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="disclaimer-banner">⚠️ <strong>Estimates Only:</strong> All budget allocations, prices, and vendor questions are benchmark estimates and do not represent contractual quotes.</div>',
        unsafe_allow_html=True,
    )

    # Initialize session state for generated plan
    if "current_result" not in st.session_state:
        st.session_state.current_result = None

    # Two-column layout: Left = Intake Form, Right = Plan Presentation
    col_form, col_content = st.columns([1, 1.8], gap="large")

    with col_form:
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

            today = date.today()
            default_date = today + timedelta(days=90)
            event_date = st.date_input(
                "Event Date",
                value=default_date,
                min_value=today,
                key="input_event_date",
            )

            col_guests, col_budget = st.columns(2)
            with col_guests:
                guests = st.number_input(
                    "Guest Count",
                    min_value=1,
                    max_value=100000,
                    value=100,
                    step=10,
                    key="input_guests",
                )
            with col_budget:
                total_budget = st.number_input(
                    "Total Budget",
                    min_value=100.0,
                    max_value=100000000.0,
                    value=250000.0,
                    step=5000.0,
                    key="input_total_budget",
                )

            col_city, col_curr = st.columns(2)
            with col_city:
                city = st.text_input(
                    "City / Location",
                    value="Bengaluru",
                    placeholder="e.g. Bengaluru, Mumbai, Jaipur",
                    key="input_city",
                )
            with col_curr:
                currency = st.selectbox(
                    "Currency",
                    options=["INR", "USD", "EUR", "GBP", "AED"],
                    index=0,
                    key="input_currency",
                )

            # Language Selector (English UI initially per T-08)
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
                "✨ Generate Event Plan",
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
                    lang=selected_lang,  # type: ignore
                    vibe=vibe.strip(),
                    notes=notes.strip(),
                )

                with st.spinner("Generating plan and computing deterministic allocations..."):
                    result = generate_plan_v0(inputs, llm=_resolve_session_llm())
                    st.session_state.current_result = result

    # Right Column: Plan Output Presentation
    with col_content:
        result = st.session_state.current_result

        if not result:
            st.info(
                "👈 Fill out the details on the left and click **Generate Event Plan** to begin!"
            )

            st.markdown("### Quick Demo Scenarios")
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("💍 Sample Wedding", use_container_width=True):
                    demo_inputs = PlanInputs(
                        event_type="wedding",
                        event_date=date.today() + timedelta(days=180),
                        guests=200,
                        total_budget=1200000.0,
                        city="Jaipur",
                        currency="INR",
                        vibe="Royal Rajasthani heritage",
                        notes="Traditional ceremonies with sangeet evening",
                    )
                    st.session_state.current_result = generate_plan_v0(
                        demo_inputs, llm=_resolve_session_llm()
                    )
                    st.rerun()

            with c2:
                if st.button("🎂 Sample Birthday", use_container_width=True):
                    demo_inputs = PlanInputs(
                        event_type="birthday",
                        event_date=date.today() + timedelta(days=30),
                        guests=35,
                        total_budget=40000.0,
                        city="Bengaluru",
                        currency="INR",
                        vibe="Outdoor picnic with arcade games",
                        notes="Fun themes and personalized return gifts",
                    )
                    st.session_state.current_result = generate_plan_v0(
                        demo_inputs, llm=_resolve_session_llm()
                    )
                    st.rerun()

            with c3:
                if st.button("🎪 Sample Community Event", use_container_width=True):
                    demo_inputs = PlanInputs(
                        event_type="community",
                        event_date=date.today() + timedelta(days=60),
                        guests=400,
                        total_budget=150000.0,
                        city="Pune",
                        currency="INR",
                        vibe="Eco-conscious cultural street festival",
                        notes="Volunteer-run stalls and youth talent show",
                    )
                    st.session_state.current_result = generate_plan_v0(
                        demo_inputs, llm=_resolve_session_llm()
                    )
                    st.rerun()

        else:
            plan = result.plan

            # Fallback or Informational Notices
            if result.is_fallback:
                st.warning(
                    "⚠️ **Benchmark Plan:** AI service is busy, showing a benchmark plan. Try again later or add your own key in the sidebar."
                )

            if result.notices:
                for note in result.notices:
                    st.caption(f"ℹ️ {note}")

            # Provider badge indicator
            provider_badge = (
                '<span class="badge-tag" style="background-color: #FEF3C7; color: #92400E;">⚡ Benchmark Fallback</span>'
                if result.is_fallback
                else f'<span class="badge-tag" style="background-color: #ECFDF5; color: #065F46;">🤖 Served by: {result.provider.upper() if result.provider else "LLM"}</span>'
            )

            # Plan Summary Ribbon
            st.markdown(
                f"""
                <div class="metric-card">
                    {provider_badge}
                    <span class="badge-tag">{plan.event_type.upper()}</span>
                    <span class="badge-tag">📍 {plan.city or "General Metro"}</span>
                    <span class="badge-tag">👥 {plan.guests} Guests</span>
                    <span class="badge-tag">📅 {plan.event_date.strftime("%B %d, %Y")}</span>
                    <span class="badge-tag">💰 {format_currency(plan.total_budget, plan.currency)}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Four Tabs for Content Organization
            tab_budget, tab_timeline, tab_vendors, tab_ideas = st.tabs(
                [
                    "💰 Budget Breakdown",
                    "📅 Scheduled Timeline",
                    "🤝 Vendor Checklist",
                    "💡 Creative Ideas",
                ]
            )

            with tab_budget:
                st.markdown("#### Estimated Budget Allocations")

                # Budget Table
                budget_data = []
                for b in plan.budget:
                    budget_data.append(
                        {
                            "Category": b.label,
                            "Allocation (%)": f"{b.percent:.1f}%",
                            f"Amount ({plan.currency})": f"{b.amount:,.2f}",
                            "Notes": b.note or "Standard benchmark allocation",
                        }
                    )

                df_budget = pd.DataFrame(budget_data)
                st.dataframe(df_budget, use_container_width=True, hide_index=True)

                # Integrity Verification Check
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

            with tab_timeline:
                st.markdown("#### Backward-Scheduled Action Plan")
                st.caption(
                    f"Milestones planned backward from event date: **{plan.event_date.strftime('%A, %B %d, %Y')}**"
                )

                timeline_data = []
                for t in plan.timeline:
                    timeline_data.append(
                        {
                            "Due Date": t.due_date.strftime("%Y-%m-%d (%a)"),
                            "Phase": t.phase,
                            "Task Title": t.title,
                            "Owner": t.owner,
                            "Status": t.status.upper(),
                        }
                    )

                df_timeline = pd.DataFrame(timeline_data)
                st.dataframe(df_timeline, use_container_width=True, hide_index=True)

            with tab_vendors:
                st.markdown("#### Vendor Due Diligence Checklists")

                if not plan.vendors:
                    st.write("No specific vendor checklists generated.")
                else:
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
                                    st.markdown(
                                        f"- 🚩 <span style='color: #DC2626;'>{rf}</span>",
                                        unsafe_allow_html=True,
                                    )

            with tab_ideas:
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

            # Bottom Assumptions and Observability Expander
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
                        f"- Tokens: `{result.metadata.total_tokens}` total (Prompt: {result.metadata.prompt_tokens}, Candidates: {result.metadata.completion_tokens})"
                    )


if __name__ == "__main__":
    main()
