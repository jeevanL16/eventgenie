# 🎉 EventGenie

**GenAI-powered planning assistant that helps users organize weddings, birthdays, and community events with budgets, timelines, vendor checklists, and personalized ideas.**

> ⚠️ **Hackathon Submission Sprint.** Live public demo engineered on a $0 free-tier stack.

## Problem Statement Traceability

This matrix maps every verbatim requirement from the hackathon problem statement to its architectural implementation and automated test:

| Requirement Component | Feature Implementation | Source Code (File & Function) | Automated Test |
|---|---|---|---|
| **Weddings** | Multi-tier wedding planning with ceremony/sangeet/reception budget allocations, venue and catering milestones, vendor due diligence checklists | [`app/pipeline.py:fallback_plan`](file:///d:/eventgenie/app/pipeline.py), [`app/prompts/v1/plan_v0.md`](file:///d:/eventgenie/app/prompts/v1/plan_v0.md) | [`tests/test_problem_statement.py::test_all_event_types_generate_all_four_required_outputs[wedding]`](file:///d:/eventgenie/tests/test_problem_statement.py) |
| **Birthdays** | Age-appropriate birthday milestones, theme styling, cake and entertainment allocations, party activity checklists | [`app/pipeline.py:fallback_plan`](file:///d:/eventgenie/app/pipeline.py), [`app/schemas.py:PlanInputs`](file:///d:/eventgenie/app/schemas.py) | [`tests/test_problem_statement.py::test_all_event_types_generate_all_four_required_outputs[birthday]`](file:///d:/eventgenie/tests/test_problem_statement.py) |
| **Community Events** | Volunteer coordination, permits, stage/sound logistics, public crowd safety, and community dining logistics | [`app/pipeline.py:fallback_plan`](file:///d:/eventgenie/app/pipeline.py), [`app/prompts/v1/plan_v0.md`](file:///d:/eventgenie/app/prompts/v1/plan_v0.md) | [`tests/test_problem_statement.py::test_all_event_types_generate_all_four_required_outputs[community]`](file:///d:/eventgenie/tests/test_problem_statement.py) |
| **Budgets** | Proportional category percentage breakdown with deterministic penny-rounding reconciliation guaranteeing exact 100.0% sum | [`app/tools/budget.py:calculate_budget`](file:///d:/eventgenie/app/tools/budget.py) | [`tests/test_tools_budget.py::test_calculate_budget_property_exact_sum`](file:///d:/eventgenie/tests/test_tools_budget.py) (Hypothesis property test) |
| **Timelines** | Backward-scheduled milestone roadmap with calendar dates clamped to valid ranges preceding the event date | [`app/tools/scheduler.py:schedule_tasks`](file:///d:/eventgenie/app/tools/scheduler.py) | [`tests/test_tools_scheduler.py::test_schedule_tasks_property_all_on_or_before_event`](file:///d:/eventgenie/tests/test_tools_scheduler.py) (Hypothesis property test) |
| **Vendor Checklists** | Category-specific due diligence checklists: essential questions to ask, documents to request, and red flag warnings | [`app/schemas.py:VendorItem`](file:///d:/eventgenie/app/schemas.py), [`app/pipeline.py:_assemble_event_plan`](file:///d:/eventgenie/app/pipeline.py) | [`tests/test_schemas.py::test_vendor_item_valid`](file:///d:/eventgenie/tests/test_schemas.py) |
| **Personalized Ideas** | Creative themes, tailored catering menus, interactive guest activities, decor concepts, and thoughtful favors based on vibe & notes | [`app/schemas.py:IdeaSet`](file:///d:/eventgenie/app/schemas.py), [`app/pipeline.py:generate_plan_v0`](file:///d:/eventgenie/app/pipeline.py) | [`tests/test_problem_statement.py::test_genai_pipeline_end_to_end_personalization`](file:///d:/eventgenie/tests/test_problem_statement.py) |
| **GenAI-Powered** | Schema-enforced structured generation, multi-provider failover router (Groq, Gemini, Ollama), and 2-stage automated repair loop | [`app/llm/router.py:LLMRouter`](file:///d:/eventgenie/app/llm/router.py), [`app/pipeline.py:generate_plan_v0`](file:///d:/eventgenie/app/pipeline.py) | [`tests/test_llm_router.py::test_router_failover_on_rate_limit_429`](file:///d:/eventgenie/tests/test_llm_router.py) |

## Supported Languages

English · Hindi · Kannada · Telugu · Tamil · Marathi

## Quick Start

```bash
# Clone the repo
git clone https://github.com/jeevanL16/eventgenie.git
cd eventgenie

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your free API keys

# Run the app
streamlit run app/main.py
```

## Free-Tier Limits and Provider Failover

EventGenie is engineered to operate reliably on a **$0 budget** using a multi-provider resilient failover router:

- **Provider Chain:** Requests automatically cascade through `groq` → `gemini` → deterministic benchmark fallback.
- **Dynamic Quota Caution:** Provider rate limits, requests per minute (RPM), and daily free quotas change frequently without notice. Check individual provider dashboards ([Google AI Studio](https://aistudio.google.com), [Groq Console](https://console.groq.com)) for current allocation details.
- **Zero-Downtime Fallback:** If all cloud providers encounter rate limits (HTTP 429), timeouts, or service interruptions, the application instantly surfaces an expert-verified, deterministic benchmark plan without breaking or leaking raw API payloads.
- **Bring Your Own Key (BYOK):** The Streamlit UI includes a session-only key manager in the sidebar. Users can supply personal API keys that persist strictly in browser memory and are never written to disk or logs.
- **Local Dev & Offline Inference:** Local Ollama support can be enabled for offline testing and evals by configuring `OLLAMA_BASE_URL`.

## Tech Stack

- **Language:** Python 3.11+
- **UI:** Streamlit
- **LLM Routing:** Custom `LLMRouter` with Groq (`qwen/qwen3.8-27b`), Gemini (`gemini-flash-lite-latest`), and local Ollama
- **Validation:** Pydantic v2 with deterministic rounding and schedule tools
- **All free-tier services** — $0 budget

## License

MIT

---

*All prices shown by EventGenie are labelled estimates. Do not treat them as real quotes.*
