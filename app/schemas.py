"""EventGenie data schemas — Pydantic v2 models for event plans.

Implements the schema from EVENTGENIE_MASTER_PROMPT.md Section 6.
"""

import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Lang = Literal["en", "hi", "kn", "te", "ta", "mr"]
EventType = Literal["wedding", "birthday", "community"]

CONTROL_CHAR_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(v: Any, max_len: int) -> str:
    """Strip control characters and truncate to max length for security."""
    if v is None:
        return ""
    text = str(v)
    cleaned = CONTROL_CHAR_REGEX.sub("", text).strip()
    return cleaned[:max_len]


class PlanInputs(BaseModel):
    """User intake form inputs for generating or planning an event."""

    event_type: EventType
    event_date: date
    guests: int = Field(gt=0, le=100000, description="Expected guest count (1 to 100,000)")
    total_budget: float = Field(ge=100.0, le=100000000.0, description="Total budget amount")
    currency: str = Field(default="INR", max_length=10)
    city: str = Field(default="", max_length=100)
    lang: Lang = "en"
    vibe: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=1000)

    @field_validator("city", mode="before")
    @classmethod
    def sanitize_city(cls, v: Any) -> str:
        return sanitize_text(v, 100)

    @field_validator("vibe", mode="before")
    @classmethod
    def sanitize_vibe(cls, v: Any) -> str:
        return sanitize_text(v, 500)

    @field_validator("notes", mode="before")
    @classmethod
    def sanitize_notes(cls, v: Any) -> str:
        return sanitize_text(v, 1000)

    @field_validator("currency", mode="before")
    @classmethod
    def sanitize_currency(cls, v: Any) -> str:
        clean = sanitize_text(v, 10).upper()
        return clean if clean else "INR"


class BudgetLine(BaseModel):
    """A single budget category line item."""

    key: str  # stable English id, e.g. "venue"
    label: str  # localized display label
    percent: float = Field(ge=0, le=100)
    amount: float = Field(ge=0)
    note: str = ""  # localized


class Task(BaseModel):
    """A single timeline task."""

    title: str  # localized
    phase: str  # localized, e.g. "3 months out"
    due_date: date
    owner: str = "Organizer"
    status: Literal["todo", "doing", "done"] = "todo"
    category_key: str = "general"


class VendorItem(BaseModel):
    """A vendor category with due diligence guidance."""

    category_key: str
    label: str  # localized
    questions_to_ask: list[str]
    documents_to_request: list[str]
    red_flags: list[str]


class IdeaSet(BaseModel):
    """Creative ideas for the event."""

    themes: list[str]
    menu: list[str]
    activities: list[str]
    decor: list[str]
    extras: list[str]


class EventPlan(BaseModel):
    """Complete event plan — the main output of the pipeline."""

    lang: Lang = "en"
    event_type: EventType
    event_date: date
    guests: int = Field(gt=0)
    total_budget: float = Field(gt=0)
    currency: str
    city: str = ""
    budget: list[BudgetLine]
    timeline: list[Task]
    vendors: list[VendorItem]
    ideas: IdeaSet
    assumptions: list[str]  # localized, shown to the user
    sources_used: list[str] = []  # RAG document names

    @model_validator(mode="after")
    def check_integrity(self):
        """Validate budget sums and timeline dates."""
        budget_sum = sum(b.amount for b in self.budget)
        if abs(budget_sum - self.total_budget) > 1:
            raise ValueError(
                f"Budget lines must sum to total_budget "
                f"(got {budget_sum}, expected {self.total_budget})"
            )
        late_tasks = [t.title for t in self.timeline if t.due_date > self.event_date]
        if late_tasks:
            raise ValueError(f"Tasks cannot be due after the event date: {late_tasks}")
        return self
