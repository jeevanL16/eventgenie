"""Verification script to test Gemini LLM JSON-mode structured output.

Uses the official google-genai unified SDK.
"""

import os
import sys

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import config
from app.llm import GeminiLLM, LLMAuthError


class TinyEvent(BaseModel):
    title: str = Field(description="Name or title of the event")
    guest_count: int = Field(gt=0, description="Number of expected guests")
    city: str = Field(description="City where the event will take place")
    estimated_budget: float = Field(gt=0, description="Estimated total budget in local currency")


def main() -> int:
    load_dotenv()
    api_key = config.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")

    if not api_key:
        print("=" * 60)
        print("NOTICE: GEMINI_API_KEY is not set.")
        print("To run a live test with Google AI Studio:")
        print("  1. Add GEMINI_API_KEY=your_key to your .env file")
        print("  2. Re-run: python scripts/test_gemini_call.py")
        print(
            "Unit tests with mocked client pass independently via: pytest tests/test_llm_gemini.py"
        )
        print("=" * 60)
        return 0

    print("Running real Gemini LLM call with structured schema validation...")
    print(f"SDK: google-genai (unified) | Model: {config.GEMINI_MODEL}")
    llm = GeminiLLM(api_key=api_key)

    system_prompt = (
        "You are EventGenie, an expert event planning assistant. "
        "Generate a structured plan matching the exact JSON schema provided."
    )
    user_prompt = "Plan a friendly birthday dinner for 15 guests in Bengaluru with an estimated budget of 30000 INR."

    try:
        validated_obj = llm.generate_json(
            system=system_prompt,
            prompt=user_prompt,
            schema=TinyEvent,
            temperature=0.2,
        )

        print("\n--- Real Call Successful! ---")
        print(f"Validated Schema Object: {validated_obj}")
        print(f"Type: {type(validated_obj)}")
        print(f"Title: {validated_obj.title}")
        print(f"Guests: {validated_obj.guest_count}")
        print(f"City: {validated_obj.city}")
        print(f"Budget: {validated_obj.estimated_budget}")

        if llm.last_metadata:
            print("\n--- Execution Metadata ---")
            print(f"Model: {llm.last_metadata.model}")
            print(f"Latency: {llm.last_metadata.latency_ms:.1f} ms")
            print(f"Prompt Tokens: {llm.last_metadata.prompt_tokens}")
            print(f"Completion Tokens: {llm.last_metadata.completion_tokens}")
            print(f"Total Tokens: {llm.last_metadata.total_tokens}")

        return 0

    except LLMAuthError as e:
        print(f"\nAuthentication Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\nCall failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
