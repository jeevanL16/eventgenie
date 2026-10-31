# 🚀 EventGenie — Streamlit Community Cloud Deployment Guide

Follow this 5-minute checklist to deploy EventGenie live to the web.

---

### Prerequisites
- A free [GitHub](https://github.com) account with repository access: `https://github.com/jeevanL16/eventgenie`
- A free [Streamlit Community Cloud](https://share.streamlit.io) account (login using GitHub)
- Your free API keys:
  - **Groq API key:** [console.groq.com/keys](https://console.groq.com/keys)
  - **Google Gemini API key:** [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

---

### Step-by-Step Deployment Instructions

#### 1. Connect Repo to Streamlit Cloud
1. Navigate to **[share.streamlit.io](https://share.streamlit.io)** and log in.
2. Click **Create app** (or **New app**).
3. Select **"Yup, I have an app"**.
4. Fill in the repository details:
   - **Repository:** `jeevanL16/eventgenie`
   - **Branch:** `main`
   - **Main file path:** `app/main.py`
   - **App URL:** (Optional: customize subdomain, e.g. `eventgenie-ai.streamlit.app`)
5. Under **Advanced settings...**:
   - Set **Python version** to **3.11** (matches `.python-version` and pre-built wheels).

#### 2. Configure Environment Secrets
In the same **Advanced settings...** modal, paste the following into the **Secrets** editor:

```toml
# Provider chain: Cloud-safe failover across Groq and Gemini
LLM_PROVIDER = "router"
LLM_CHAIN = "groq,gemini"

# Groq API configuration (fast free inference)
GROQ_API_KEY = "gsk_your_actual_groq_api_key_here"
GROQ_MODEL = "qwen/qwen3.8-27b"

# Google Gemini API configuration (fallback free provider)
GEMINI_API_KEY = "AIzaSy_your_actual_gemini_api_key_here"
GEMINI_MODEL = "gemini-flash-lite-latest"
```

> **Security Note:** Never commit `secrets.toml` or API keys to GitHub. Streamlit Cloud encrypts secrets at rest and injects them securely via `st.secrets`.

#### 3. Launch App
1. Click **Deploy!**
2. Watch the build logs while Streamlit installs dependencies from `requirements.txt`.
3. Once the build finishes (~1-2 minutes), the app will load with the initial form.

---

### Post-Deployment Verification Checklist
- [ ] App loads at your public URL without any errors or Python tracebacks.
- [ ] Top disclaimer displays: *"⚠️ Estimates Only: All budget allocations, prices, and vendor questions are benchmark estimates and do not represent contractual quotes."*
- [ ] Click **💍 Sample Wedding**:
  - Plan generates successfully.
  - Active provider badge displays in the header ribbon (e.g. `🤖 Served by: GROQ`).
  - Budget breakdown lines sum exactly to 100% with green verification check.
  - Scheduled timeline displays milestones backward from event date.
  - Vendor checklist and creative ideas tabs populate.
- [ ] Open sidebar **🔑 Bring Your Own Key (BYOK)** to test personal session keys.
- [ ] Share the live URL with the developer or record it in `EVENTGENIE_MASTER_PROMPT.md` and `README.md`.

