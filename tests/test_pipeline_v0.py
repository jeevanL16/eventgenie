"""Unit and integration tests for pipeline.generate_plan_v0."""

from datetime import date
from unittest.mock import MagicMock, patch

from app.llm import LLMAuthError, LLMMetadata, LLMValidationError
from app.pipeline import (
    GenerationResult,
    PlanProposalV0,
    generate_plan_v0,
)
from app.schemas import EventPlan, IdeaSet, PlanInputs, VendorItem


def _make_sample_proposal() -> PlanProposalV0:
    return PlanProposalV0(
        budget=[
            {"key": "venue", "label": "Venue", "percent": 50.0, "note": "Main hall"},
            {"key": "catering", "label": "Catering", "percent": 40.0, "note": "Buffet"},
            {"key": "contingency", "label": "Contingency", "percent": 10.0, "note": "Buffer"},
        ],
        timeline=[
            {
                "title": "Book Venue",
                "phase": "3 months out",
                "offset_days": -90,
                "owner": "Host",
                "status": "todo",
                "category_key": "venue",
            },
            {
                "title": "Event Setup",
                "phase": "Day of",
                "offset_days": 0,
                "owner": "Host",
                "status": "todo",
                "category_key": "general",
            },
        ],
        vendors=[
            VendorItem(
                category_key="venue",
                label="Venue Manager",
                questions_to_ask=["Capacity?"],
                documents_to_request=["Contract"],
                red_flags=["No contract"],
            )
        ],
        ideas=IdeaSet(
            themes=["Theme A"],
            menu=["Dish A"],
            activities=["Activity A"],
            decor=["Decor A"],
            extras=["Extra A"],
        ),
        assumptions=["Budget is flexible"],
    )


def test_generate_plan_v0_missing_api_key_returns_fallback_with_notice():
    inputs = PlanInputs(
        event_type="birthday",
        event_date=date(2027, 5, 20),
        guests=25,
        total_budget=30000.0,
    )

    with patch("app.config.GEMINI_API_KEY", ""):
        result = generate_plan_v0(inputs, llm=None)

        assert isinstance(result, GenerationResult)
        assert result.is_fallback is True
        assert len(result.notices) > 0
        assert "NOTICE:" in result.notices[0]
        assert isinstance(result.plan, EventPlan)
        assert result.plan.total_budget == 30000.0
        assert round(sum(b.amount for b in result.plan.budget), 2) == 30000.0


def test_generate_plan_v0_bad_api_key_returns_fallback_with_notice():
    inputs = PlanInputs(
        event_type="wedding",
        event_date=date(2027, 12, 15),
        guests=100,
        total_budget=500000.0,
    )

    mock_llm = MagicMock()
    mock_llm.api_key = "invalid-key"
    mock_llm.generate_json.side_effect = LLMAuthError("Invalid API key")

    result = generate_plan_v0(inputs, llm=mock_llm)

    assert result.is_fallback is True
    assert len(result.notices) > 0
    assert "Invalid API key" in result.notices[0]
    assert isinstance(result.plan, EventPlan)
    assert result.plan.event_type == "wedding"


def test_generate_plan_v0_success_for_three_sample_inputs():
    samples = [
        PlanInputs(
            event_type="wedding",
            event_date=date(2027, 11, 10),
            guests=250,
            total_budget=1500000.0,
            city="Jaipur",
        ),
        PlanInputs(
            event_type="birthday",
            event_date=date(2027, 4, 1),
            guests=40,
            total_budget=45000.0,
            city="Pune",
        ),
        PlanInputs(
            event_type="community",
            event_date=date(2027, 8, 15),
            guests=500,
            total_budget=100000.0,
            city="Hyderabad",
        ),
    ]

    mock_llm = MagicMock()
    mock_llm.api_key = "valid-key"
    mock_llm.last_metadata = LLMMetadata(
        model="gemini-1.5-flash",
        latency_ms=450.0,
        prompt_tokens=200,
        completion_tokens=400,
        total_tokens=600,
    )
    mock_llm.generate_json.return_value = _make_sample_proposal()

    for sample in samples:
        result = generate_plan_v0(sample, llm=mock_llm)
        assert result.is_fallback is False
        assert len(result.notices) == 0
        assert isinstance(result.plan, EventPlan)
        assert result.plan.event_type == sample.event_type
        assert round(sum(b.amount for b in result.plan.budget), 2) == sample.total_budget
        for task in result.plan.timeline:
            assert task.due_date <= sample.event_date


def test_generate_plan_v0_repair_loop_succeeds_on_second_attempt():
    inputs = PlanInputs(
        event_type="birthday",
        event_date=date(2027, 6, 1),
        guests=20,
        total_budget=20000.0,
    )

    mock_llm = MagicMock()
    mock_llm.api_key = "valid-key"
    mock_llm.last_metadata = LLMMetadata(
        model="gemini-1.5-flash", latency_ms=300.0, total_tokens=400
    )

    # First attempt fails with validation error; second attempt returns valid proposal
    mock_llm.generate_json.side_effect = [
        LLMValidationError("Missing required field: vendors"),
        _make_sample_proposal(),
    ]

    result = generate_plan_v0(inputs, llm=mock_llm, max_repairs=2)

    assert result.is_fallback is False
    assert mock_llm.generate_json.call_count == 2
    # Second call should include repair instruction in prompt
    second_call_prompt = mock_llm.generate_json.call_args_list[1][1]["prompt"]
    assert "REPAIR INSTRUCTION" in second_call_prompt
    assert "Missing required field: vendors" in second_call_prompt


def test_generate_plan_v0_repairs_exhausted_falls_back():
    inputs = PlanInputs(
        event_type="community",
        event_date=date(2027, 7, 10),
        guests=100,
        total_budget=50000.0,
    )

    mock_llm = MagicMock()
    mock_llm.api_key = "valid-key"
    mock_llm.generate_json.side_effect = LLMValidationError("Persistent bad JSON")

    result = generate_plan_v0(inputs, llm=mock_llm, max_repairs=2)

    assert result.is_fallback is True
    assert mock_llm.generate_json.call_count == 3  # initial + 2 repairs
    assert len(result.notices) > 0
    assert "AI service is busy" in result.notices[0]
    assert isinstance(result.plan, EventPlan)


def test_generate_plan_v0_accepts_dict():
    raw_dict = {
        "event_type": "birthday",
        "event_date": "2027-09-09",
        "guests": 15,
        "total_budget": 15000.0,
        "city": "Chennai",
    }

    mock_llm = MagicMock()
    mock_llm.api_key = "valid-key"
    mock_llm.generate_json.return_value = _make_sample_proposal()

    result = generate_plan_v0(raw_dict, llm=mock_llm)
    assert result.is_fallback is False
    assert result.plan.city == "Chennai"
