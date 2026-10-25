"""Property-based and unit tests for timeline scheduler tool."""

from datetime import date, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from app.schemas import Task
from app.tools.scheduler import ProposedTask, schedule_tasks


def test_basic_scheduling():
    event_date = date(2027, 6, 1)
    today = date(2027, 1, 1)

    proposals = [
        ProposedTask(title="Book Venue", phase="6 months out", offset_days=-150),
        ProposedTask(title="Send Invites", phase="2 months out", offset_days=-60),
        ProposedTask(title="Final Checks", phase="Day of event", offset_days=0),
    ]

    tasks = schedule_tasks(proposals, event_date=event_date, today=today)

    assert len(tasks) == 3
    assert tasks[0].title == "Book Venue"
    assert tasks[0].due_date == date(2027, 6, 1) - timedelta(days=150)
    assert tasks[1].title == "Send Invites"
    assert tasks[1].due_date == date(2027, 6, 1) - timedelta(days=60)
    assert tasks[2].title == "Final Checks"
    assert tasks[2].due_date == event_date


def test_clamping_prevents_dates_after_event():
    event_date = date(2027, 5, 10)
    today = date(2027, 1, 1)

    # Offset 10 days after event should be clamped to event_date
    raw_tasks = [
        {"title": "Late Task", "phase": "After", "offset_days": 10},
    ]

    tasks = schedule_tasks(raw_tasks, event_date=event_date, today=today)
    assert len(tasks) == 1
    assert tasks[0].due_date <= event_date


def test_clamping_prevents_dates_before_today():
    event_date = date(2027, 12, 31)
    today = date(2027, 6, 1)

    # 365 days before event date would be 2026-12-31, which is before today
    # Should be clamped to today (2027-06-01)
    proposals = [
        ProposedTask(title="Overdue Planning", phase="1 year out", offset_days=-365),
    ]

    tasks = schedule_tasks(proposals, event_date=event_date, today=today)
    assert len(tasks) == 1
    assert tasks[0].due_date == today


def test_tasks_are_chronologically_sorted():
    event_date = date(2027, 8, 15)
    today = date(2027, 1, 1)

    # Tasks given in random order
    proposals = [
        ProposedTask(title="Event Day", phase="Day of", offset_days=0),
        ProposedTask(title="Early Planning", phase="6 months out", offset_days=-180),
        ProposedTask(title="Decor Setup", phase="1 week out", offset_days=-7),
        ProposedTask(title="Mid Planning", phase="3 months out", offset_days=-90),
    ]

    tasks = schedule_tasks(proposals, event_date=event_date, today=today)

    for i in range(len(tasks) - 1):
        assert tasks[i].due_date <= tasks[i + 1].due_date

    assert tasks[0].title == "Early Planning"
    assert tasks[-1].title == "Event Day"


def test_with_existing_task_objects():
    event_date = date(2027, 10, 1)
    today = date(2027, 1, 1)

    existing = [
        Task(
            title="T1",
            phase="Phase 1",
            due_date=date(2027, 8, 1),
            owner="Alice",
            status="todo",
            category_key="venue",
        ),
        Task(
            title="T2",
            phase="Phase 2",
            due_date=date(2027, 5, 1),
            owner="Bob",
            status="doing",
            category_key="catering",
        ),
    ]

    tasks = schedule_tasks(existing, event_date=event_date, today=today)
    assert len(tasks) == 2
    assert tasks[0].title == "T2"  # earlier due date comes first
    assert tasks[1].title == "T1"


# ---------------------------------------------------------------------------
# Property-based testing with Hypothesis
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(
    event_date=st.dates(min_value=date(2025, 1, 1), max_value=date(2035, 12, 31)),
    today=st.dates(min_value=date(2025, 1, 1), max_value=date(2035, 12, 31)),
    offsets=st.lists(st.integers(min_value=-1000, max_value=1000), min_size=1, max_size=25),
)
def test_property_tasks_never_after_event_and_are_sorted(
    event_date: date, today: date, offsets: list[int]
):
    """Property: No task due_date can ever be after event_date, and tasks are sorted."""
    proposals = [
        ProposedTask(
            title=f"Task {i}",
            phase=f"Phase {i}",
            offset_days=offset,
        )
        for i, offset in enumerate(offsets)
    ]

    tasks = schedule_tasks(proposals, event_date=event_date, today=today)

    # 1. No task is due after event date
    for task in tasks:
        assert task.due_date <= event_date

    # 2. If today <= event_date, no task is before today
    if today <= event_date:
        for task in tasks:
            assert task.due_date >= today

    # 3. Tasks are sorted chronologically
    for i in range(len(tasks) - 1):
        assert tasks[i].due_date <= tasks[i + 1].due_date
