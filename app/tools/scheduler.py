"""Timeline scheduling and date calculation tools for EventGenie.

Ensures deterministic date math and chronological sorting according to
the architecture principle: LLM proposes day offsets, deterministic code computes dates.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

from app.schemas import Task


@dataclass
class ProposedTask:
    """Raw task proposed by an LLM or template using day offsets before the event."""

    title: str
    phase: str
    offset_days: int  # e.g. -90 for 90 days before event date
    owner: str = "Organizer"
    status: Literal["todo", "doing", "done"] = "todo"
    category_key: str = "general"


def _resolve_task_fields(
    item: Task | ProposedTask | dict[str, Any],
    event_date: date,
) -> tuple[str, str, str, str, str, date]:
    """Extract standard task attributes and un-clamped target date from polymorphic item."""
    if isinstance(item, dict):
        title = str(item.get("title", "Untitled Task"))
        phase = str(item.get("phase", "Planning"))
        owner = str(item.get("owner", "Organizer"))
        raw_status = str(item.get("status", "todo")).lower()
        status = raw_status if raw_status in ("todo", "doing", "done") else "todo"
        category_key = str(item.get("category_key", "general"))

        if "due_date" in item and isinstance(item["due_date"], date):
            target_date = item["due_date"]
        elif "due_date" in item and isinstance(item["due_date"], str):
            target_date = date.fromisoformat(item["due_date"])
        else:
            raw_offset = int(item.get("offset_days", 0))
            offset = -abs(raw_offset) if raw_offset != 0 else 0
            target_date = event_date + timedelta(days=offset)
        return title, phase, owner, status, category_key, target_date

    if hasattr(item, "due_date") and isinstance(item.due_date, date):
        return (
            getattr(item, "title", "Untitled Task"),
            getattr(item, "phase", "Planning"),
            getattr(item, "owner", "Organizer"),
            getattr(item, "status", "todo"),
            getattr(item, "category_key", "general"),
            item.due_date,
        )

    if hasattr(item, "offset_days"):
        offset_val = int(getattr(item, "offset_days", 0))
        offset = -abs(offset_val) if offset_val != 0 else 0
        target_date = event_date + timedelta(days=offset)
        return (
            getattr(item, "title", "Untitled Task"),
            getattr(item, "phase", "Planning"),
            getattr(item, "owner", "Organizer"),
            getattr(item, "status", "todo"),
            getattr(item, "category_key", "general"),
            target_date,
        )

    raise TypeError(f"Unsupported task item type: {type(item)}")


def schedule_tasks(
    tasks: Sequence[Task | ProposedTask | dict[str, Any]],
    event_date: date,
    today: date | None = None,
) -> list[Task]:
    """Convert offset-based task proposals to calendar dates, clamp to bounds, and sort.

    Guarantees:
    - task.due_date <= event_date for every task
    - If today <= event_date, task.due_date >= today
    - Tasks are sorted chronologically in ascending order (earliest first)

    Args:
        tasks: Sequence of task definitions (Task, ProposedTask, or dict).
        event_date: Date of the event.
        today: Reference current date for clamping (defaults to date.today()).

    Returns:
        List of validated, clamped, and chronologically sorted Task objects.
    """
    ref_today = today or date.today()
    min_date = min(ref_today, event_date)

    scheduled: list[Task] = []

    for item in tasks:
        title, phase, owner, status, category_key, target_date = _resolve_task_fields(
            item, event_date
        )
        clamped_date = max(min_date, min(target_date, event_date))
        scheduled.append(
            Task(
                title=title,
                phase=phase,
                due_date=clamped_date,
                owner=owner,
                status=status,
                category_key=category_key,
            )
        )

    # Sort chronologically by due date ascending, preserving stability
    scheduled.sort(key=lambda t: t.due_date)

    return scheduled
