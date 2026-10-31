"""Reusable UI components for the EventGenie landing page and planner.

Each function renders one self-contained section via render_html with
static trusted HTML. Dynamic or user-supplied text is always escaped
with html.escape or rendered via native Streamlit widgets.
"""

import html as html_mod

import streamlit as st

from app.i18n import t
from app.ui.html import render_html


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
def nav_bar(lang: str = "en") -> None:
    """Render a sticky top navigation bar with logo, links, and CTA."""
    html_code = f"""
    <a class="skip-link" href="#planner-section" aria-label="Skip to planner">Skip to planner</a>
    <nav class="eg-nav" role="navigation" aria-label="Main navigation">
        <a class="eg-nav-logo eg-brand" href="#home" aria-label="EventGenie Home">✨ {html_mod.escape(t("app_title", lang))}</a>
        <ul class="eg-nav-links">
            <li><a href="#home">{html_mod.escape(t("nav_home", lang))}</a></li>
            <li><a href="#how-it-works">{html_mod.escape(t("nav_how", lang))}</a></li>
            <li><a href="#planner-section">{html_mod.escape(t("nav_plan", lang))}</a></li>
            <li><a href="#about">{html_mod.escape(t("nav_about", lang))}</a></li>
        </ul>
        <a class="eg-nav-cta eg-btn" href="#planner-section" aria-label="{html_mod.escape(t("nav_plan", lang))}">{html_mod.escape(t("nav_plan", lang))}</a>
    </nav>
    """
    render_html(html_code)


# ---------------------------------------------------------------------------
# Hero Section
# ---------------------------------------------------------------------------
def hero(lang: str = "en") -> None:
    """Render hero banner with headline, subline, CTA buttons, and stat badges."""
    headline = html_mod.escape(t("hero_headline", lang))
    subline = html_mod.escape(t("hero_subline", lang))
    cta_text = html_mod.escape(t("hero_cta", lang))
    sample_text = html_mod.escape(t("hero_sample_link", lang))
    stat1 = html_mod.escape(t("stat_languages", lang))
    stat2 = html_mod.escape(t("stat_events", lang))
    stat3 = html_mod.escape(t("stat_outputs", lang))

    html_code = f"""
    <div class="eg-hero" id="home">
        <h1>{headline}</h1>
        <p class="subline">{subline}</p>
        <div class="eg-hero-actions">
            <a class="eg-btn-primary eg-btn" href="#planner-section" aria-label="{cta_text}">✨ {cta_text}</a>
            <a class="eg-btn-secondary eg-btn" href="#sample-preview" aria-label="{sample_text}">📋 {sample_text}</a>
        </div>
        <div class="eg-stats">
            <div class="eg-stat">
                <span class="number">6</span>
                <span class="label">{stat1}</span>
            </div>
            <div class="eg-stat">
                <span class="number">3</span>
                <span class="label">{stat2}</span>
            </div>
            <div class="eg-stat">
                <span class="number">4</span>
                <span class="label">{stat3}</span>
            </div>
        </div>
    </div>
    """
    render_html(html_code)


# ---------------------------------------------------------------------------
# Event Type Cards
# ---------------------------------------------------------------------------
_EVENT_ICONS = {"wedding": "💍", "birthday": "🎂", "community": "🎪"}


def event_cards(lang: str = "en") -> str | None:
    """Render 3 event-type cards. Returns the chosen event type or None."""
    cards = [
        ("wedding", "card_wedding_title", "card_wedding_desc"),
        ("birthday", "card_birthday_title", "card_birthday_desc"),
        ("community", "card_community_title", "card_community_desc"),
    ]
    features = [
        t("card_feature_budget", lang),
        t("card_feature_timeline", lang),
        t("card_feature_vendors", lang),
        t("card_feature_ideas", lang),
    ]
    feature_tags = "".join(
        f'<span class="feature-tag">{html_mod.escape(f)}</span>' for f in features
    )

    cards_html = ""
    for etype, title_key, desc_key in cards:
        icon = _EVENT_ICONS.get(etype, "🎉")
        title = html_mod.escape(t(title_key, lang))
        desc = html_mod.escape(t(desc_key, lang))
        cards_html += f"""
        <div class="eg-card">
            <span class="icon">{icon}</span>
            <h3>{title}</h3>
            <p>{desc}</p>
            <div class="features">{feature_tags}</div>
        </div>
        """

    section_title = html_mod.escape(t("event_type", lang))
    wrapper_html = f"""
    <div class="eg-section" id="event-types">
        <h2 class="eg-section-title">{section_title}</h2>
        <div class="eg-cards">{cards_html}</div>
    </div>
    """
    render_html(wrapper_html)

    # Use Streamlit buttons for interactivity
    cols = st.columns(3)
    chosen = None
    start_label = t("card_start_planning", lang)
    for i, (etype, title_key, _) in enumerate(cards):
        icon = _EVENT_ICONS.get(etype, "🎉")
        with cols[i]:
            if st.button(
                f"{icon} {start_label}: {t(title_key, lang)}",
                key=f"card_btn_{etype}",
                use_container_width=True,
                help=f"Plan a {t(title_key, lang)}",
            ):
                chosen = etype
    return chosen


# ---------------------------------------------------------------------------
# How It Works
# ---------------------------------------------------------------------------
def how_it_works(lang: str = "en") -> None:
    """Render the 3-step explanation section."""
    steps = [
        ("1", "step1_title", "step1_desc"),
        ("2", "step2_title", "step2_desc"),
        ("3", "step3_title", "step3_desc"),
    ]

    steps_html = ""
    for num, title_key, desc_key in steps:
        title = html_mod.escape(t(title_key, lang))
        desc = html_mod.escape(t(desc_key, lang))
        steps_html += f"""
        <div class="eg-step">
            <span class="step-number">{num}</span>
            <h3>{title}</h3>
            <p>{desc}</p>
        </div>
        """

    section_title = html_mod.escape(t("how_title", lang))
    section_sub = html_mod.escape(t("how_subtitle", lang))

    wrapper_html = f"""
    <div class="eg-section" id="how-it-works">
        <h2 class="eg-section-title">{section_title}</h2>
        <p class="eg-section-sub">{section_sub}</p>
        <div class="eg-steps">{steps_html}</div>
    </div>
    """
    render_html(wrapper_html)


# ---------------------------------------------------------------------------
# Sample Preview
# ---------------------------------------------------------------------------
def sample_preview(lang: str = "en") -> None:
    """Render a small static sample plan preview, clearly labelled as example."""
    label = html_mod.escape(t("sample_label", lang))
    title = html_mod.escape(t("sample_title", lang))
    event_desc = html_mod.escape(t("sample_event", lang))
    budget_hdr = html_mod.escape(t("budget_breakdown", lang))
    timeline_hdr = html_mod.escape(t("timeline", lang))
    vendor_hdr = html_mod.escape(t("vendor_checklist", lang))

    html_code = f"""
    <div class="eg-section" id="sample-preview">
        <div class="eg-preview">
            <span class="eg-preview-label">{label}</span>
            <h3>{title}: {event_desc}</h3>
            <h4>💰 {budget_hdr}</h4>
            <table aria-label="Sample budget breakdown">
                <thead>
                    <tr><th>Category</th><th>Allocation</th><th>Amount</th></tr>
                </thead>
                <tbody>
                    <tr><td>Venue &amp; Rental</td><td>30%</td><td>₹3,60,000</td></tr>
                    <tr><td>Catering</td><td>25%</td><td>₹3,00,000</td></tr>
                    <tr><td>Photography</td><td>15%</td><td>₹1,80,000</td></tr>
                    <tr><td>Decor &amp; Flowers</td><td>15%</td><td>₹1,80,000</td></tr>
                    <tr><td>Entertainment</td><td>10%</td><td>₹1,20,000</td></tr>
                    <tr><td>Contingency</td><td>5%</td><td>₹60,000</td></tr>
                </tbody>
            </table>
            <h4>📅 {timeline_hdr} (4 of 7 milestones)</h4>
            <table aria-label="Sample timeline milestones">
                <thead>
                    <tr><th>Due Date</th><th>Phase</th><th>Task</th></tr>
                </thead>
                <tbody>
                    <tr><td>6 months out</td><td>Planning</td><td>Book venue and finalize date</td></tr>
                    <tr><td>4 months out</td><td>Booking</td><td>Confirm catering and menu tasting</td></tr>
                    <tr><td>2 months out</td><td>Coordination</td><td>Finalize photographer and schedule</td></tr>
                    <tr><td>2 weeks out</td><td>Final</td><td>Confirm all vendors and seating</td></tr>
                </tbody>
            </table>
            <h4>🤝 {vendor_hdr} (3 sample questions)</h4>
            <ul style="color: var(--text-body); font-size: 0.9rem; padding-left: var(--sp-5);">
                <li>Does the venue have backup power and covered outdoor areas?</li>
                <li>Can the caterer accommodate 200+ guests with live counters?</li>
                <li>What is the photographer's cancellation and refund policy?</li>
            </ul>
        </div>
    </div>
    """
    render_html(html_code)


# ---------------------------------------------------------------------------
# CTA Banner
# ---------------------------------------------------------------------------
def cta_banner(lang: str = "en") -> None:
    """Render gradient closing CTA banner."""
    title = html_mod.escape(t("cta_title", lang))
    subtitle = html_mod.escape(t("cta_subtitle", lang))
    btn = html_mod.escape(t("cta_button", lang))

    html_code = f"""
    <div class="eg-cta-banner" id="cta-section">
        <h2>{title}</h2>
        <p>{subtitle}</p>
        <a class="eg-btn-primary eg-btn" href="#planner-section" aria-label="{btn}">✨ {btn}</a>
    </div>
    """
    render_html(html_code)


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
def footer(lang: str = "en") -> None:
    """Render multi-column footer with product, languages, project links."""
    product = html_mod.escape(t("footer_product", lang))
    features = html_mod.escape(t("footer_features", lang))
    pricing = html_mod.escape(t("footer_pricing", lang))
    demo = html_mod.escape(t("footer_demo", lang))
    langs = html_mod.escape(t("footer_languages", lang))
    project = html_mod.escape(t("footer_project", lang))
    github = html_mod.escape(t("footer_github", lang))
    docs = html_mod.escape(t("footer_docs", lang))
    security = html_mod.escape(t("footer_security", lang))
    legal = html_mod.escape(t("footer_legal", lang))
    disclaimer = html_mod.escape(t("footer_disclaimer", lang))
    copyright_text = html_mod.escape(t("footer_copyright", lang))

    html_code = f"""
    <div class="eg-footer" id="about">
        <div class="eg-footer-grid">
            <div class="eg-footer-col">
                <h4>{product}</h4>
                <ul>
                    <li>{features}</li>
                    <li>{pricing}</li>
                    <li>{demo}</li>
                </ul>
            </div>
            <div class="eg-footer-col">
                <h4>{langs}</h4>
                <ul>
                    <li>English</li>
                    <li>हिन्दी (Hindi)</li>
                    <li>ಕನ್ನಡ (Kannada)</li>
                    <li>తెలుగు (Telugu)</li>
                    <li>தமிழ் (Tamil)</li>
                    <li>मराठी (Marathi)</li>
                </ul>
            </div>
            <div class="eg-footer-col">
                <h4>{project}</h4>
                <ul>
                    <li><a href="https://github.com/jeevanL16/eventgenie" target="_blank" rel="noopener">{github}</a></li>
                    <li>{docs}</li>
                    <li>{security}</li>
                </ul>
            </div>
            <div class="eg-footer-col">
                <h4>{legal}</h4>
                <ul>
                    <li style="line-height:1.5;">{disclaimer}</li>
                </ul>
            </div>
        </div>
        <div class="eg-footer-bottom">
            {copyright_text}
        </div>
    </div>
    """
    render_html(html_code)


# ---------------------------------------------------------------------------
# Result ribbon for planner output
# ---------------------------------------------------------------------------
def result_ribbon(
    provider: str | None,
    is_fallback: bool,
    is_cached: bool,
    event_type: str,
    city: str,
    guests: int,
    event_date_str: str,
    currency_display: str,
) -> None:
    """Render a status ribbon with provider, event, and status badges."""
    safe_provider = html_mod.escape((provider or "LLM").upper())
    safe_event = html_mod.escape(event_type.upper())
    safe_city = html_mod.escape(city or "General Metro")
    safe_currency = html_mod.escape(currency_display)
    safe_date = html_mod.escape(event_date_str)

    if is_fallback:
        provider_badge = (
            '<span class="eg-result-badge eg-badge-fallback">⚡ Benchmark Fallback</span>'
        )
    else:
        provider_badge = (
            f'<span class="eg-result-badge eg-badge-provider">🤖 Served by: {safe_provider}</span>'
        )

    cache_badge = (
        '<span class="eg-result-badge eg-badge-cached">⚡ Cached (&lt;10ms)</span>'
        if is_cached
        else ""
    )

    html_code = f"""
    <div class="eg-ribbon">
        {provider_badge}
        {cache_badge}
        <span class="eg-result-badge eg-badge-info">{safe_event}</span>
        <span class="eg-result-badge eg-badge-info">📍 {safe_city}</span>
        <span class="eg-result-badge eg-badge-info">👥 {guests}</span>
        <span class="eg-result-badge eg-badge-info">📅 {safe_date}</span>
        <span class="eg-result-badge eg-badge-info">💰 {safe_currency}</span>
    </div>
    """
    render_html(html_code)


# ---------------------------------------------------------------------------
# Disclaimer banner
# ---------------------------------------------------------------------------
def disclaimer_banner(lang: str = "en") -> None:
    """Render the estimates-only warning banner."""
    text = html_mod.escape(t("estimates_disclaimer", lang))
    html_code = f'<div class="eg-disclaimer">⚠️ <strong>{text}</strong></div>'
    render_html(html_code)
