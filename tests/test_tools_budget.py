"""Property-based and unit tests for budget calculation tool."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.schemas import BudgetLine
from app.tools.budget import ProposedBudgetLine, calculate_budget


def test_basic_budget_calculation():
    proposals = [
        ProposedBudgetLine(key="venue", label="Venue", percent=50.0),
        ProposedBudgetLine(key="catering", label="Catering", percent=30.0),
        ProposedBudgetLine(key="contingency", label="Contingency", percent=20.0),
    ]
    lines = calculate_budget(proposals, total_budget=100000.0)

    assert len(lines) == 3
    assert lines[0].amount == 50000.0
    assert lines[1].amount == 30000.0
    assert lines[2].amount == 20000.0
    assert sum(line.amount for line in lines) == 100000.0


def test_rounding_discrepancy_absorbed_by_contingency():
    # 3 lines of equal percentage (33.33%) with total 100.0
    # Raw amounts: 33.33, 33.33, 33.33 -> sum: 99.99
    # Contingency absorbs the 0.01 discrepancy -> 33.34
    proposals = [
        ProposedBudgetLine(key="venue", label="Venue", percent=33.33),
        ProposedBudgetLine(key="catering", label="Catering", percent=33.33),
        ProposedBudgetLine(key="contingency", label="Contingency", percent=33.33),
    ]
    lines = calculate_budget(proposals, total_budget=100.0)

    total_amount = round(sum(line.amount for line in lines), 2)
    assert total_amount == 100.0
    contingency = next(line for line in lines if line.key == "contingency")
    assert contingency.amount == 33.34


def test_rounding_absorbed_by_largest_when_no_contingency():
    proposals = [
        {"key": "venue", "label": "Venue", "percent": 70.0},
        {"key": "decor", "label": "Decor", "percent": 15.0},
        {"key": "photo", "label": "Photography", "percent": 15.0},
    ]
    lines = calculate_budget(proposals, total_budget=100.07)

    total_amount = round(sum(line.amount for line in lines), 2)
    assert total_amount == 100.07


def test_zero_percentages_distributed_equally():
    proposals = [
        {"key": "item1", "percent": 0.0},
        {"key": "item2", "percent": 0.0},
        {"key": "item3", "percent": 0.0},
        {"key": "item4", "percent": 0.0},
    ]
    lines = calculate_budget(proposals, total_budget=1000.0)

    assert len(lines) == 4
    for line in lines:
        assert line.amount == 250.0
    assert sum(line.amount for line in lines) == 1000.0


def test_invalid_total_budget_raises_error():
    with pytest.raises(ValueError, match="total_budget must be positive"):
        calculate_budget([{"key": "venue", "percent": 100.0}], total_budget=0.0)

    with pytest.raises(ValueError, match="total_budget must be positive"):
        calculate_budget([{"key": "venue", "percent": 100.0}], total_budget=-500.0)


def test_empty_lines_raises_error():
    with pytest.raises(ValueError, match="Cannot calculate budget for empty lines sequence"):
        calculate_budget([], total_budget=5000.0)


def test_with_existing_budget_lines():
    existing = [
        BudgetLine(key="venue", label="Venue", percent=60.0, amount=600.0),
        BudgetLine(key="food", label="Food", percent=40.0, amount=400.0),
    ]
    lines = calculate_budget(existing, total_budget=2000.0)
    assert len(lines) == 2
    assert lines[0].amount == 1200.0
    assert lines[1].amount == 800.0
    assert sum(line.amount for line in lines) == 2000.0


# ---------------------------------------------------------------------------
# Property-based testing with Hypothesis
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    total_budget=st.floats(min_value=1.0, max_value=10_000_000.0).map(lambda x: round(x, 2)),
    percentages=st.lists(st.floats(min_value=0.0, max_value=100.0), min_size=1, max_size=20),
)
def test_property_budget_sum_is_always_exact(total_budget: float, percentages: list[float]):
    """Property: The sum of line amounts MUST always equal total_budget exactly."""
    proposals = [
        ProposedBudgetLine(
            key=f"cat_{i}",
            label=f"Category {i}",
            percent=pct,
        )
        for i, pct in enumerate(percentages)
    ]

    lines = calculate_budget(proposals, total_budget=total_budget)

    # 1. Total sum exact to 2 decimal places
    computed_sum = round(sum(line.amount for line in lines), 2)
    assert computed_sum == total_budget

    # 2. Every amount is non-negative
    for line in lines:
        assert line.amount >= 0.0

    # 3. Every percent is within [0, 100]
    for line in lines:
        assert 0.0 <= line.percent <= 100.0
