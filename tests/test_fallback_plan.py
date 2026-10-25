"""Unit tests for fallback_plan template generation."""

from datetime import date

import pytest

from app.pipeline import fallback_plan
from app.schemas import EventPlan, PlanInputs


@pytest.mark.parametrize("event_type", ["wedding", "birthday", "community"])
def test_fallback_plan_returns_valid_event_plan_for_all_types(event_type):
    inputs = PlanInputs(
        event_type=event_type,
        event_date=date(2027, 11, 20),
        guests=150,
        total_budget=500000.0,
        currency="INR",
        city="Bengaluru",
        lang="en",
    )

    plan = fallback_plan(inputs)

    assert isinstance(plan, EventPlan)
    assert plan.event_type == event_type
    assert plan.total_budget == 500000.0
    assert plan.currency == "INR"
    assert plan.city == "Bengaluru"
    assert len(plan.budget) > 0
    assert len(plan.timeline) > 0
    assert len(plan.vendors) > 0
    assert len(plan.ideas.themes) > 0
    assert len(plan.ideas.menu) > 0

    # Verify budget sum integrity
    computed_sum = round(sum(line.amount for line in plan.budget), 2)
    assert computed_sum == 500000.0

    # Verify timeline date integrity
    for task in plan.timeline:
        assert task.due_date <= plan.event_date

    # Verify timeline is sorted chronologically
    for i in range(len(plan.timeline) - 1):
        assert plan.timeline[i].due_date <= plan.timeline[i + 1].due_date


def test_fallback_plan_accepts_dict_input():
    raw_dict = {
        "event_type": "birthday",
        "event_date": "2027-04-15",
        "guests": 30,
        "total_budget": 25000.0,
        "currency": "INR",
        "city": "Mumbai",
        "lang": "hi",
    }

    plan = fallback_plan(raw_dict)
    assert isinstance(plan, EventPlan)
    assert plan.event_type == "birthday"
    assert plan.lang == "hi"
    assert round(sum(b.amount for b in plan.budget), 2) == 25000.0


def test_wedding_budget_categories():
    inputs = PlanInputs(
        event_type="wedding",
        event_date=date(2027, 12, 1),
        guests=200,
        total_budget=1000000.0,
    )
    plan = fallback_plan(inputs)

    keys = [b.key for b in plan.budget]
    expected_keys = [
        "venue",
        "catering",
        "decor",
        "photo_video",
        "attire_jewellery",
        "entertainment",
        "invitations_gifts",
        "contingency",
    ]
    assert keys == expected_keys
    assert round(sum(b.amount for b in plan.budget), 2) == 1000000.0


def test_birthday_budget_categories():
    inputs = PlanInputs(
        event_type="birthday",
        event_date=date(2027, 8, 10),
        guests=50,
        total_budget=50000.0,
    )
    plan = fallback_plan(inputs)

    keys = [b.key for b in plan.budget]
    expected_keys = [
        "venue",
        "food",
        "decor",
        "cake",
        "entertainment_games",
        "return_gifts",
        "contingency",
    ]
    assert keys == expected_keys
    assert round(sum(b.amount for b in plan.budget), 2) == 50000.0


def test_community_budget_categories():
    inputs = PlanInputs(
        event_type="community",
        event_date=date(2027, 9, 5),
        guests=300,
        total_budget=75000.0,
    )
    plan = fallback_plan(inputs)

    keys = [b.key for b in plan.budget]
    expected_keys = [
        "venue_permits",
        "logistics_sound_stage",
        "food_refreshments",
        "publicity",
        "volunteers_safety",
        "supplies",
        "contingency",
    ]
    assert keys == expected_keys
    assert round(sum(b.amount for b in plan.budget), 2) == 75000.0


def test_fallback_plan_with_fractional_budget():
    inputs = PlanInputs(
        event_type="wedding",
        event_date=date(2027, 10, 10),
        guests=100,
        total_budget=123456.78,
    )
    plan = fallback_plan(inputs)
    assert round(sum(b.amount for b in plan.budget), 2) == 123456.78
