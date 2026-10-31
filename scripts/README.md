# EventGenie CLI Scripts

This directory contains standalone CLI scripts for manual smoke testing, provider verification, and pipeline evaluation.

---

## 1. `run_v0_sample.py`
Smoke test for the end-to-end plan generation pipeline (`app.pipeline.generate_plan_v0`).

- **Purpose**: Generates sample plans for each event type (Wedding, Birthday, Community Event), verifies budget balance and timeline date constraints, and asserts that fallback behavior works correctly when an invalid API key is provided.
- **Run command**:
  ```bash
  python scripts/run_v0_sample.py
  ```

---

## 2. `test_gemini_call.py`
Direct verification of structured JSON generation with Google Gemini via the unified `google-genai` SDK.

- **Purpose**: Validates schema enforcement against a minimal Pydantic model (`TinyEvent`), checks token count extraction, and logs request latency.
- **Run command**:
  ```bash
  python scripts/test_gemini_call.py
  ```

---

## 3. `test_groq_call.py`
Direct verification of Groq OpenAI-compatible structured JSON and free-text generation.

- **Purpose**: Validates schema enforcement using Groq's high-throughput models (e.g. `llama-3.3-70b-versatile` or `llama-3.1-8b-instant`), latency recording, and token metrics.
- **Run command**:
  ```bash
  python scripts/test_groq_call.py
  ```

