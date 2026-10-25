"""Tests for app.schemas — Section 6 schema validation."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas import BudgetLine, EventPlan, IdeaSet, Task, VendorItem

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_budget_lines(total: float, splits: dict[str, float]) -> list[BudgetLine]:
    """Create budget lines from a {key: percent} dict."""
    lines = []
    for key, pct in splits.items():
        lines.append(
            BudgetLine(
                key=key,
                label=key.title(),
                percent=pct,
                amount=round(total * pct / 100, 2),
            )
        )
    # Fix rounding: adjust the last line so sums are exact
    current_sum = sum(line.amount for line in lines)
    if lines:
        lines[-1].amount += round(total - current_sum, 2)
    return lines


def _make_ideas() -> IdeaSet:
    return IdeaSet(
        themes=["Classic"],
        menu=["Buffet"],
        activities=["Dance"],
        decor=["Flowers"],
        extras=["Photo booth"],
    )


def _make_vendor() -> VendorItem:
    return VendorItem(
        category_key="venue",
        label="Venue",
        questions_to_ask=["Capacity?"],
        documents_to_request=["License"],
        red_flags=["No contract"],
    )


def _make_valid_plan(**overrides) -> dict:
    """Return a dict that produces a valid EventPlan. Override any field."""
    total = overrides.pop("total_budget", 100000.0)
    defaults = {
        "event_type": "wedding",
        "event_date": date(2025, 12, 31),
        "guests": 100,
        "total_budget": total,
        "currency": "INR",
        "city": "Bangalore",
        "budget": _make_budget_lines(total, {"venue": 30, "catering": 40, "decor": 30}),
        "timeline": [
            Task(
                title="Book venue",
                phase="3 months out",
                due_date=date(2025, 9, 30),
            )
        ],
        "vendors": [_make_vendor()],
        "ideas": _make_ideas(),
        "assumptions": ["Prices are estimates."],
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Valid plan tests
# ---------------------------------------------------------------------------


class TestValidPlan:
    """A correctly formed plan should pass validation."""

    def test_minimal_valid_plan(self):
        plan = EventPlan(**_make_valid_plan())
        assert plan.event_type == "wedding"
        assert plan.guests == 100
        assert plan.lang == "en"

    @pytest.mark.parametrize("event_type", ["wedding", "birthday", "community"])
    def test_all_event_types(self, event_type: str):
        plan = EventPlan(**_make_valid_plan(event_type=event_type))
        assert plan.event_type == event_type

    @pytest.mark.parametrize("lang", ["en", "hi", "kn", "te", "ta", "mr"])
    def test_all_languages(self, lang: str):
        plan = EventPlan(**_make_valid_plan(lang=lang))
        assert plan.lang == lang

    def test_budget_sums_match(self):
        plan = EventPlan(**_make_valid_plan(total_budget=500000.0))
        assert abs(sum(b.amount for b in plan.budget) - plan.total_budget) <= 1

    def test_timeline_dates_before_event(self):
        plan = EventPlan(**_make_valid_plan())
        for task in plan.timeline:
            assert task.due_date <= plan.event_date

    def test_empty_sources(self):
        plan = EventPlan(**_make_valid_plan())
        assert plan.sources_used == []

    def test_with_sources(self):
        plan = EventPlan(**_make_valid_plan(sources_used=["budget_guide.md"]))
        assert plan.sources_used == ["budget_guide.md"]


# ---------------------------------------------------------------------------
# Invalid plan tests — budget sum mismatch
# ---------------------------------------------------------------------------


class TestBudgetIntegrity:
    """Budget lines must sum to total_budget within ±1."""

    def test_budget_sum_too_high(self):
        lines = [
            BudgetLine(key="venue", label="Venue", percent=100, amount=60000),
            BudgetLine(key="catering", label="Catering", percent=100, amount=50000),
        ]
        with pytest.raises(ValidationError, match="Budget lines must sum to total_budget"):
            EventPlan(**_make_valid_plan(total_budget=100000.0, budget=lines))

    def test_budget_sum_too_low(self):
        lines = [
            BudgetLine(key="venue", label="Venue", percent=50, amount=40000),
        ]
        with pytest.raises(ValidationError, match="Budget lines must sum to total_budget"):
            EventPlan(**_make_valid_plan(total_budget=100000.0, budget=lines))

    def test_budget_sum_within_tolerance(self):
        """±1 tolerance should be accepted."""
        lines = [
            BudgetLine(key="venue", label="Venue", percent=50, amount=50000.50),
            BudgetLine(key="catering", label="Catering", percent=50, amount=49999.80),
        ]
        # Sum = 100000.30, total = 100000.0, diff = 0.30 — within ±1
        plan = EventPlan(**_make_valid_plan(total_budget=100000.0, budget=lines))
        assert len(plan.budget) == 2


# ---------------------------------------------------------------------------
# Invalid plan tests — late tasks
# ---------------------------------------------------------------------------


class TestTimelineIntegrity:
    """No task can be due after the event date."""

    def test_task_after_event_date(self):
        late_task = Task(
            title="Late task",
            phase="After event",
            due_date=date(2026, 1, 15),  # after event_date 2025-12-31
        )
        with pytest.raises(ValidationError, match="Tasks cannot be due after the event date"):
            EventPlan(**_make_valid_plan(timeline=[late_task]))

    def test_task_on_event_date(self):
        """Task on the event date itself should be OK."""
        same_day_task = Task(
            title="Day-of coordination",
            phase="Event day",
            due_date=date(2025, 12, 31),  # same as event_date
        )
        plan = EventPlan(**_make_valid_plan(timeline=[same_day_task]))
        assert len(plan.timeline) == 1


# ---------------------------------------------------------------------------
# Field-level validation
# ---------------------------------------------------------------------------


class TestFieldValidation:
    """Individual field constraints."""

    def test_negative_guests(self):
        with pytest.raises(ValidationError):
            EventPlan(**_make_valid_plan(guests=-1))

    def test_zero_guests(self):
        with pytest.raises(ValidationError):
            EventPlan(**_make_valid_plan(guests=0))

    def test_negative_budget(self):
        with pytest.raises(ValidationError):
            EventPlan(**_make_valid_plan(total_budget=-1000))

    def test_zero_budget(self):
        with pytest.raises(ValidationError):
            EventPlan(**_make_valid_plan(total_budget=0))

    def test_invalid_event_type(self):
        with pytest.raises(ValidationError):
            EventPlan(**_make_valid_plan(event_type="concert"))

    def test_invalid_language(self):
        with pytest.raises(ValidationError):
            EventPlan(**_make_valid_plan(lang="fr"))

    def test_budget_line_negative_percent(self):
        with pytest.raises(ValidationError):
            BudgetLine(key="x", label="X", percent=-5, amount=100)

    def test_budget_line_over_100_percent(self):
        with pytest.raises(ValidationError):
            BudgetLine(key="x", label="X", percent=101, amount=100)

    def test_budget_line_negative_amount(self):
        with pytest.raises(ValidationError):
            BudgetLine(key="x", label="X", percent=10, amount=-100)

    def test_invalid_task_status(self):
        with pytest.raises(ValidationError):
            Task(
                title="Test",
                phase="Test",
                due_date=date(2025, 6, 1),
                status="cancelled",
            )
