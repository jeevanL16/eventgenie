# 🎉 EventGenie

**Multilingual GenAI event-planning assistant** — turns a few answers into a complete, editable plan with budget breakdown, backward-scheduled timeline, vendor checklist, and personalized ideas.

> ⚠️ **Work in progress.** This project is under active development.

## Supported Languages

English · Hindi · Kannada · Telugu · Tamil · Marathi

## Quick Start

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/eventgenie.git
cd eventgenie

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Run the app
streamlit run app/main.py
```

## Tech Stack

- **Language:** Python 3.11+
- **UI:** Streamlit
- **LLM:** Google Gemini API (free tier)
- **Validation:** Pydantic v2
- **All free-tier services** — $0 budget

## License

MIT

---

*All prices shown by EventGenie are labelled estimates. Do not treat them as real quotes.*
