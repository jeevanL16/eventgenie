"""Explicit edge-case tests for EventGenie (Task S-06).

Tests extreme boundaries, negative values, past dates, malformed JSON,
and multi-provider cascading failures.
"""

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.llm import LLMRateLimitError, LLMValidationError
from app.llm.router import LLMRouter
from app.pipeline import generate_plan_v0
from app.schemas import EventPlan, PlanInputs
from app.tools.scheduler import ProposedTask, schedule_tasks


class TestEdgeCaseBoundaries:
    """Tests for extreme numerical and temporal boundary inputs."""

    def test_edge_case_negative_and_zero_budget(self):
        """Negative and zero budgets must be rejected by Pydantic validation."""
        with pytest.raises(ValidationError):
            PlanInputs(
                event_type="wedding",
                event_date=date(2027, 10, 1),
                guests=50,
                total_budget=-5000.0,
            )

        with pytest.raises(ValidationError):
            PlanInputs(
                event_type="wedding",
                event_date=date(2027, 10, 1),
                guests=50,
                total_budget=0.0,
            )

        with pytest.raises(ValidationError):
            PlanInputs(
                event_type="wedding",
                event_date=date(2027, 10, 1),
                guests=50,
                total_budget=50.0,  # Below minimum threshold of 100.0
            )

    def test_edge_case_huge_guests(self):
        """Exceeding the maximum allowed guest count (100,000) must be rejected."""
        with pytest.raises(ValidationError):
            PlanInputs(
                event_type="community",
                event_date=date(2027, 12, 1),
                guests=100001,
                total_budget=500000.0,
            )

        # Boundary maximum accepted
        valid_max = PlanInputs(
            event_type="community",
            event_date=date(2027, 12, 1),
            guests=100000,
            total_budget=500000.0,
        )
        assert valid_max.guests == 100000

    def test_edge_case_past_date_scheduling(self):
        """Past event date must have tasks clamped on or before the event date."""
        past_event = date.today() - timedelta(days=30)
        tasks = [
            ProposedTask(title="Initial Booking", phase="Past", offset_days=-60),
            ProposedTask(title="Final Check", phase="Past", offset_days=-10),
            ProposedTask(title="Day Of", phase="Past", offset_days=0),
        ]
        scheduled = schedule_tasks(tasks, event_date=past_event, today=date.today())

        # Guarantees: every task due date <= event_date
        assert all(t.due_date <= past_event for t in scheduled)
        # Clamped to min(today, event_date)
        assert all(t.due_date <= date.today() for t in scheduled)


class TestEdgeCaseLLMFailures:
    """Tests for LLM failure modes: malformed JSON, schema violation, and full router failover."""

    def test_edge_case_malformed_json_triggers_repair_and_fallback(self):
        """When an LLM returns unparseable malformed JSON repeatedly, pipeline falls back politely."""
        mock_llm = MagicMock()
        mock_llm.api_key = "test-key"
        # Simulate unrecoverable validation error from bad JSON
        mock_llm.generate_json.side_effect = LLMValidationError(
            "JSONDecodeError: Expecting value: line 1 column 1 (char 0)"
        )

        inputs = PlanInputs(
            event_type="birthday",
            event_date=date(2027, 7, 20),
            guests=25,
            total_budget=15000.0,
        )

        result = generate_plan_v0(inputs, llm=mock_llm, max_repairs=2, use_cache=False)

        assert result.is_fallback is True
        assert isinstance(result.plan, EventPlan)
        assert any("busy" in n.lower() or "error" in n.lower() for n in result.notices)
        # Verify budget sums to target despite LLM failure
        assert round(sum(b.amount for b in result.plan.budget), 2) == 15000.0

    def test_edge_case_complete_router_failure_returns_benchmark_fallback(self):
        """When all providers in the router chain encounter 429 rate limits, fallback plan is served."""
        router = LLMRouter(chain="groq,gemini", groq_api_key="gr-fake", gemini_api_key="gem-fake")

        mock_groq = MagicMock()
        mock_groq.generate_json.side_effect = LLMRateLimitError("Groq 429 rate limit exceeded")
        mock_gemini = MagicMock()
        mock_gemini.generate_json.side_effect = LLMRateLimitError("Gemini 429 quota exhausted")

        router._providers = {"groq": mock_groq, "gemini": mock_gemini}

        inputs = PlanInputs(
            event_type="community",
            event_date=date(2027, 9, 15),
            guests=300,
            total_budget=80000.0,
        )

        result = generate_plan_v0(inputs, llm=router, use_cache=False)

        assert result.is_fallback is True
        assert len(result.plan.budget) > 0
        assert len(result.plan.timeline) > 0
        assert round(sum(b.amount for b in result.plan.budget), 2) == 80000.0
