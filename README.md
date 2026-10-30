# 🎉 EventGenie

**Multilingual GenAI event-planning assistant** — turns a few answers into a complete, editable plan with budget breakdown, backward-scheduled timeline, vendor checklist, and personalized ideas.

> ⚠️ **Work in progress.** This project is under active development.

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
