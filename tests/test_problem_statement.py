"""Problem Statement Traceability Verification.

Verifies the verbatim Hackathon Problem Statement:
"Create a GenAI-powered planning assistant that helps users organize
weddings, birthdays, and community events with budgets, timelines,
vendor checklists, and personalized ideas."
"""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from app.pipeline import (
    GenerationResult,
    PlanProposalV0,
    fallback_plan,
    generate_plan_v0,
)
from app.schemas import EventPlan, IdeaSet, PlanInputs, VendorItem


@pytest.mark.parametrize("event_type", ["wedding", "birthday", "community"])
def test_all_event_types_generate_all_four_required_outputs(event_type: str):
    """Verify that every supported event type produces the 4 required outputs."""
    inputs = PlanInputs(
        event_type=event_type,
        event_date=date.today() + timedelta(days=90),
        guests=75,
        total_budget=350000.0,
        currency="INR",
        city="Bengaluru",
        vibe="Warm, memorable, and vibrant",
        notes="Locally-sourced catering with interactive workshops.",
    )

    plan = fallback_plan(inputs)

    # 1. Budget Verification
    assert len(plan.budget) >= 5, f"{event_type} must have complete budget breakdown"
    total_allocated = round(sum(b.amount for b in plan.budget), 2)
    assert total_allocated == inputs.total_budget, f"Budget sum must equal {inputs.total_budget}"
    assert all(b.percent > 0 for b in plan.budget), "Each budget line must have positive allocation"

    # 2. Timeline Verification
    assert len(plan.timeline) >= 4, f"{event_type} must have backward-scheduled milestones"
    assert all(t.due_date <= inputs.event_date for t in plan.timeline), "Tasks must precede event"
    for i in range(len(plan.timeline) - 1):
        assert plan.timeline[i].due_date <= plan.timeline[i + 1].due_date, "Timeline must be sorted"

    # 3. Vendor Checklist Verification
    assert len(plan.vendors) >= 1, f"{event_type} must have vendor due-diligence checklists"
    for v in plan.vendors:
        assert len(v.questions_to_ask) >= 1, "Vendor must contain vetting questions"
        assert len(v.documents_to_request) >= 1, "Vendor must specify required documents"
        assert len(v.red_flags) >= 1, "Vendor must flag warnings"

    # 4. Personalized Ideas Verification
    assert len(plan.ideas.themes) >= 1, f"{event_type} must have themes"
    assert len(plan.ideas.menu) >= 1, f"{event_type} must have menu ideas"
    assert len(plan.ideas.activities) >= 1, f"{event_type} must have interactive activities"
    assert len(plan.ideas.decor) >= 1, f"{event_type} must have decor concepts"
    assert len(plan.ideas.extras) >= 1, f"{event_type} must have thoughtful extras"


def test_genai_pipeline_end_to_end_personalization():
    """Verify that the GenAI pipeline injects user personalization and produces all 4 outputs."""
    inputs = PlanInputs(
        event_type="wedding",
        event_date=date(2027, 4, 18),
        guests=150,
        total_budget=1200000.0,
        currency="INR",
        city="Jaipur",
        vibe="Royal Rajasthani heritage",
        notes="Sadhya luncheon and evening acoustic sangeet",
    )

    mock_llm = MagicMock()
    mock_llm.api_key = "valid-test-key"
    mock_llm.generate_json.return_value = PlanProposalV0(
        budget=[
            {"key": "venue", "label": "Heritage Haveli", "percent": 40.0, "note": "Jaipur palace"},
            {
                "key": "catering",
                "label": "Royal Sadhya Feast",
                "percent": 35.0,
                "note": "Traditional lunch",
            },
            {
                "key": "decor",
                "label": "Marigold & Mirror Styling",
                "percent": 15.0,
                "note": "Rajasthani theme",
            },
            {
                "key": "contingency",
                "label": "Emergency Reserve",
                "percent": 10.0,
                "note": "Safety buffer",
            },
        ],
        timeline=[
            {
                "title": "Book Heritage Haveli Venue",
                "phase": "6 months out",
                "offset_days": -180,
                "owner": "Couple",
                "status": "todo",
                "category_key": "venue",
            },
            {
                "title": "Finalize Traditional Sadhya Caterer",
                "phase": "3 months out",
                "offset_days": -90,
                "owner": "Couple",
                "status": "todo",
                "category_key": "catering",
            },
            {
                "title": "Welcome Sangeet Guests",
                "phase": "Day of",
                "offset_days": 0,
                "owner": "Coordinator",
                "status": "todo",
                "category_key": "entertainment",
            },
        ],
        vendors=[
            VendorItem(
                category_key="venue",
                label="Palace Heritage Manager",
                questions_to_ask=["Heritage acoustic limits?", "Power backup load?"],
                documents_to_request=["Archaeological clearance permit", "Safety certificate"],
                red_flags=["Refusal to put fire clearances in writing"],
            )
        ],
        ideas=IdeaSet(
            themes=["Royal Rajasthani Heritage Sangeet"],
            menu=["Authentic Dal Baati Churma", "Ker Sangri", "Sadhya Feast"],
            activities=["Live folk dance troupe", "Folk puppet storytelling"],
            decor=["Brass lamps", "Hand-painted umbrella photobooth"],
            extras=["Handcrafted miniature puppet favors"],
        ),
        assumptions=["Assumed Jaipur April weather permits evening open-air celebration."],
    )

    result = generate_plan_v0(inputs, llm=mock_llm)

    assert isinstance(result, GenerationResult)
    assert not result.is_fallback
    assert isinstance(result.plan, EventPlan)

    # Confirm all 4 outputs are populated with personalized content
    assert result.plan.total_budget == 1200000.0
    assert len(result.plan.budget) == 4
    assert len(result.plan.timeline) == 3
    assert len(result.plan.vendors) == 1
    assert "Rajasthani" in result.plan.ideas.themes[0]
