"""Budget calculation and rounding adjustment tools for EventGenie.

Ensures deterministic arithmetic and exact penny matching according to
the architecture principle: LLM proposes percentages, deterministic code verifies.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.schemas import BudgetLine


@dataclass
class ProposedBudgetLine:
    """Raw budget line proposed by an LLM or template before exact calculation."""

    key: str
    label: str
    percent: float
    note: str = ""


def _normalize_budget_items(
    lines: Sequence[BudgetLine | ProposedBudgetLine | dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize polymorphic input items into standard dictionary representations."""
    raw_items: list[dict[str, Any]] = []
    for item in lines:
        if isinstance(item, dict):
            raw_items.append(
                {
                    "key": str(item.get("key", "misc")),
                    "label": str(item.get("label", item.get("key", "Miscellaneous"))),
                    "percent": float(item.get("percent", 0.0)),
                    "note": str(item.get("note", "")),
                }
            )
        elif hasattr(item, "key") and hasattr(item, "percent"):
            raw_items.append(
                {
                    "key": str(item.key),
                    "label": str(getattr(item, "label", item.key)),
                    "percent": float(item.percent),
                    "note": str(getattr(item, "note", "")),
                }
            )
        else:
            raise TypeError(f"Unsupported budget item type: {type(item)}")
    return raw_items


def _scale_percentages(raw_items: list[dict[str, Any]]) -> None:
    """Scale raw proposed percentages in-place so their sum equals exactly 100.0%."""
    sum_percents = sum(max(0.0, item["percent"]) for item in raw_items)
    if sum_percents <= 0.0:
        equal_pct = 100.0 / len(raw_items)
        for item in raw_items:
            item["percent"] = equal_pct
    else:
        for item in raw_items:
            item["percent"] = (max(0.0, item["percent"]) / sum_percents) * 100.0


def _reconcile_rounding(
    amounts: list[float], raw_items: list[dict[str, Any]], target_total: float
) -> None:
    """Absorb rounding discrepancy into contingency category or the largest category."""
    diff = round(target_total - round(sum(amounts), 2), 2)
    if diff == 0.0:
        return

    absorb_idx = -1
    for idx, item in enumerate(raw_items):
        if item["key"].strip().lower() in ("contingency", "emergency", "buffer"):
            absorb_idx = idx
            break

    if absorb_idx == -1:
        absorb_idx = max(range(len(amounts)), key=lambda i: amounts[i])

    new_amount = round(amounts[absorb_idx] + diff, 2)
    if new_amount >= 0.0:
        amounts[absorb_idx] = new_amount
    else:
        amounts[absorb_idx] = 0.0
        remaining_diff = round(target_total - sum(amounts), 2)
        other_idx = max(range(len(amounts)), key=lambda i: amounts[i])
        amounts[other_idx] = round(amounts[other_idx] + remaining_diff, 2)


def calculate_budget(
    lines: Sequence[BudgetLine | ProposedBudgetLine | dict[str, Any]],
    total_budget: float,
) -> list[BudgetLine]:
    """Calculate exact currency amounts from percentages with rounding reconciliation.

    Guarantees:
    - sum(line.amount for line in result) == round(total_budget, 2)
    - Every line.amount >= 0.0 and line.percent in [0.0, 100.0]
    - Rounding discrepancies absorbed deterministically into contingency or largest line.
    """
    if total_budget <= 0:
        raise ValueError(f"total_budget must be positive, got {total_budget}")
    if not lines:
        raise ValueError("Cannot calculate budget for empty lines sequence")

    target_total = round(float(total_budget), 2)
    raw_items = _normalize_budget_items(lines)
    _scale_percentages(raw_items)

    amounts = [round(target_total * (item["percent"] / 100.0), 2) for item in raw_items]
    _reconcile_rounding(amounts, raw_items, target_total)

    results: list[BudgetLine] = []
    for item, amount in zip(raw_items, amounts, strict=True):
        reconciled_pct = round((amount / target_total) * 100.0, 2)
        results.append(
            BudgetLine(
                key=item["key"],
                label=item["label"],
                percent=reconciled_pct,
                amount=amount,
                note=item["note"],
            )
        )
    return results
