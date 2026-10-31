"""Demonstration and verification script for pipeline.generate_plan_v0.

Tests 3 sample inputs with real key if available, and demonstrates fallback
behavior with bad or missing key.
"""

import os
import sys
from datetime import date

# Ensure repo root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.pipeline import generate_plan_v0
from app.schemas import PlanInputs


def run_samples() -> int:
    sample_inputs = [
        PlanInputs(
            event_type="wedding",
            event_date=date(2027, 11, 25),
            guests=200,
            total_budget=1200000.0,
            city="Jaipur",
            vibe="Royal and traditional",
        ),
        PlanInputs(
            event_type="birthday",
            event_date=date(2027, 6, 12),
            guests=35,
            total_budget=40000.0,
            city="Bengaluru",
            vibe="Fun outdoor picnic",
        ),
        PlanInputs(
            event_type="community",
            event_date=date(2027, 8, 15),
            guests=400,
            total_budget=150000.0,
            city="Pune",
            vibe="Eco-friendly cultural fair",
        ),
    ]

    print("=" * 65)
    print("EVENTGENIE V0 GENERATION VERIFICATION")
    print("=" * 65)

    has_api_key = bool(os.getenv("GEMINI_API_KEY"))
    print(f"GEMINI_API_KEY present: {has_api_key}")

    for idx, sample in enumerate(sample_inputs, 1):
        print(f"\n[{idx}/3] Generating plan for: {sample.event_type.upper()} in {sample.city}")
        print(
            f"     Guests: {sample.guests} | Budget: {sample.currency} {sample.total_budget:,.2f}"
        )

        result = generate_plan_v0(sample)

        print(
            f"     Result status: {'FALLBACK TEMPLATE' if result.is_fallback else 'GENAI GENERATED'}"
        )
        if result.notices:
            for notice in result.notices:
                print(f"     Notice: {notice}")

        plan = result.plan
        print(
            f"     Budget lines: {len(plan.budget)} items | Total: {plan.currency} {sum(b.amount for b in plan.budget):,.2f}"
        )
        print(
            f"     Timeline tasks: {len(plan.timeline)} tasks | Earliest: {plan.timeline[0].due_date} -> Event: {plan.event_date}"
        )
        print(
            f"     Vendors: {len(plan.vendors)} categories | Ideas: {len(plan.ideas.themes)} themes"
        )

        # Verify integrity
        assert round(sum(b.amount for b in plan.budget), 2) == sample.total_budget
        assert all(t.due_date <= sample.event_date for t in plan.timeline)

    # Demonstrate missing/bad key fallback with notice
    print("\n" + "=" * 65)
    print("TESTING BAD/MISSING KEY FALLBACK BEHAVIOR")
    print("=" * 65)
    from app.llm import GeminiLLM

    bad_llm = GeminiLLM(api_key="bad-dummy-key")
    fallback_res = generate_plan_v0(sample_inputs[0], llm=bad_llm, use_cache=False)
    print(f"Fallback triggered: {fallback_res.is_fallback}")
    print(f"Notice displayed: {fallback_res.notices[0]}")
    assert fallback_res.is_fallback is True
    assert len(fallback_res.notices) > 0
    print("Fallback verification: SUCCESS")

    print("\nAll 3 sample inputs verified successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(run_samples())
