# 🎬 EventGenie — 3-Minute Video Walkthrough Script

**Project:** EventGenie — Multilingual GenAI Event Planner  
**Target Duration:** 3 minutes (180 seconds)  
**Presenter:** Engineering Lead / Hackathon Submitter  
**Target Audience:** Hackathon Evaluators, Technical Judges, Community Organizers  
**Live URL:** [https://eventgenie-ai.streamlit.app](https://eventgenie-ai.streamlit.app) *(or local preview via `streamlit run app/main.py`)*  
**Public Repository:** [https://github.com/jeevanL16/eventgenie](https://github.com/jeevanL16/eventgenie)

---

## ⏱️ Video Timeline Overview

| Timestamp | Segment | Key Demo Action | Visual Focus |
|---|---|---|---|
| **0:00 - 0:30** | **The Problem & $0 Architecture** | State the hackathon challenge; explain why pure GenAI fails at budgeting & scheduling. | Hero banner, Problem Statement Matrix, Free-tier architecture badge. |
| **0:30 - 1:15** | **Demo 1: Jaipur Royal Wedding** | Click "💍 Sample Wedding" 1-click button; inspect 4 core outputs. | Metric ribbon, Budget reconciliation (100.0%), Backward timeline, Vendor checklists, Personalized ideas. |
| **1:15 - 1:50** | **Demo 2: Custom Birthday Party** | Customize inputs: 10th Birthday, ₹75,000 budget, strict dietary constraints & superhero vibe. | Real-time generation, XML prompt delimiter sanitization, personalized cake/activity ideas. |
| **1:50 - 2:30** | **Demo 3: Multilingual Indic Invariance** | Switch language to Kannada (ಕನ್ನಡ) or Hindi (हिंदी). | Translation validation: identical budget math and dates with localized cultural ceremony terms. |
| **2:30 - 2:55** | **Demo 4: Resilient Failover & BYOK** | Explain provider cascade (Groq → Gemini → Fallback); demonstrate sidebar BYOK. | Active provider ribbon (`Served by: GROQ`), Session-only API key manager, SQLite cache badge. |
| **2:55 - 3:00** | **Conclusion & Quality Metrics** | Summarize engineering rigor: 161 tests, 89% coverage, sub-10 MB repo. | GitHub repo, CI green badge, test coverage table. |

---

## 🎙️ Step-by-Step Spoken Script & Screen Directions

### [0:00 - 0:30] Segment 1: The Problem & The $0 Stack

**[Screen Direction]**  
*Show the EventGenie application loaded in the browser. Zoom in slightly on the header disclaimer and sub-title.*

**[Spoken Script]**  
> "Hello! Event planning is notoriously stressful: budgets leak through hidden costs, milestone deadlines get missed, and vendor contracts hide major traps.
> 
> The hackathon challenged us to build a GenAI-powered assistant helping users organize weddings, birthdays, and community events with budgets, timelines, vendor checklists, and personalized ideas.
> 
> But raw LLMs frequently fail basic arithmetic and hallucinate invalid calendar dates. Furthermore, free-tier API quotas are notoriously brittle. We built **EventGenie** on a resilient **$0 free-tier stack** that pairs creative GenAI generation with strict, deterministic validation tools to guarantee 100% mathematical and chronological integrity."

---

### [0:30 - 1:15] Segment 2: Scenario 1 — Jaipur Royal Wedding

**[Screen Direction]**  
*Click the **💍 Sample Wedding** shortcut button. The form fills instantly with a Jaipur Heritage Wedding, ₹1,500,000 budget, 250 guests. Scroll down to show the generated plan and the 4 interactive tabs.*

**[Spoken Script]**  
> "Let’s start with a high-stakes scenario: a multi-day Royal Heritage Wedding in Jaipur for 250 guests. With one click on our sample scenario, EventGenie orchestrates the entire event:
> 
> 1. **Budget Breakdown:** Notice the exact penny-rounding reconciliation. Every single rupee is accounted for, summing to exactly 100.0% with a green verification indicator—no missing funds, no rounding drift.
> 2. **Scheduled Timeline:** Our scheduler calculates milestone offsets backwards from the wedding date, clamping all dates chronologically from today to the event.
> 3. **Vendor Due Diligence:** Rather than generic lists, EventGenie provides actionable red flags, contract questions, and licensing requirements for heritage palace venues and traditional catering.
> 4. **Personalized Ideas:** Bespoke concepts tailored to Jaipur’s regal vibe, from folk music entrances to curated royal dining experiences."

---

### [1:15 - 1:50] Segment 3: Scenario 2 — 10th Birthday with Constraints

**[Screen Direction]**  
*Switch the Event Type to **🎂 Birthday Party**. Set Guest Count to 35, Total Budget to ₹65,000, and enter custom notes: 'Superhero theme, strict peanut allergy among children, indoor venue due to monsoon season'. Click **Generate Event Plan**.*

**[Spoken Script]**  
> "Now let’s test personalization under real-world constraints. Here is a 10th Birthday party with a ₹65,000 budget and strict safety notes: severe peanut allergies and an indoor monsoon venue.
> 
> Notice how the GenAI adapts immediately:
> - Security sanitization strips any dangerous control characters and encloses user inputs within strict XML boundary delimiters.
> - The catering checklist explicitly mandates nut-free certified bakeries and separate prep stations.
> - The personalized ideas recommend high-energy indoor obstacle courses and themed costume activities suited for 35 children within the space constraints."

---

### [1:50 - 2:30] Segment 4: Scenario 3 — Multilingual Indic Support & Invariance

**[Screen Direction]**  
*Select **Kannada (ಕನ್ನಡ) [Beta]** from the Target Output Language dropdown. Click Generate or inspect the localized output.*

**[Spoken Script]**  
> "India’s celebrations are deeply regional. EventGenie supports 5 major Indic languages: Hindi, Kannada, Telugu, Tamil, and Marathi.
> 
> Notice what happens when we generate in Kannada:
> - **Structural Invariance:** The budget numbers, mathematical totals, and calendar dates remain strictly identical to the verified plan—preventing translation corruption.
> - **Cultural Fluency:** Ceremony terminology is localized into authentic regional phrasing like *ಕಲ್ಯಾಣ ಮಂಟಪ* for venue and *ಊಟೋಪಹಾರ* for catering.
> - **Script Verification:** Automated post-generation checks verify that over 40% of generated characters belong to the native Unicode script range before rendering."

---

### [2:30 - 2:55] Segment 5: Multi-Provider Failover & BYOK

**[Screen Direction]**  
*Point cursor to the top metric ribbon showing `🤖 Served by: GROQ` and the `⚡ Cached (<10ms)` badge. Open the sidebar and reveal the Bring Your Own Key accordion.*

**[Spoken Script]**  
> "In a real hackathon or production environment, free-tier quotas can run out. EventGenie solves this with a 3-tier defense:
> 1. **Multi-Provider Cascade:** Our router queries ultra-fast Groq Llama 3.3 first, automatically failing over to Google Gemini 2.5 Flash on 429 rate limits or timeouts.
> 2. **Deterministic Fallback:** If all cloud services are unavailable, the app instantly delivers an expert-verified benchmark plan with zero user downtime and zero raw error leaks.
> 3. **Bring Your Own Key (BYOK):** Users can enter personal API keys in the sidebar that operate strictly in session memory—never saved to disk or logs.
> 4. **SQLite Response Caching:** Identical requests are served from local SQLite cache in under 10 milliseconds, conserving precious API quota."

---

### [2:55 - 3:00] Segment 6: Quality Summary & Conclusion

**[Screen Direction]**  
*Show the GitHub repository README with green CI badges, test table, and Problem Statement Traceability Matrix.*

**[Spoken Script]**  
> "EventGenie is backed by 161 automated tests, 89% core code coverage, WCAG AA accessibility compliance, and a sub-1 MB repository footprint.
> 
> Try the live demo at the link below. Thank you!"

---

## 📋 Recording Checklist

- [ ] Clear browser cache or run in incognito to ensure clean session state.
- [ ] Display resolution set to 1080p (1920x1080) at 100% or 125% OS scaling.
- [ ] Ensure `.env` or Streamlit secrets are active with valid Groq / Gemini keys.
- [ ] Microphone audio is clear with zero background echo.
- [ ] Highlight cursor movements smoothly over the 4 tabs and the provider badge.
