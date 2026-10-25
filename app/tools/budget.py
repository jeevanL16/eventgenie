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


def calculate_budget(
    lines: Sequence[BudgetLine | ProposedBudgetLine | dict[str, Any]],
    total_budget: float,
) -> list[BudgetLine]:
    """Calculate exact currency amounts from percentages with rounding reconciliation.

    Guarantees:
    - sum(line.amount for line in result) == round(total_budget, 2)
    - Every line.amount >= 0.0
    - Every line.percent >= 0.0 and <= 100.0
    - Discrepancies from rounding are absorbed into 'contingency' if present,
      otherwise into the largest category.

    Args:
        lines: Sequence of budget proposals (BudgetLine, ProposedBudgetLine, or dict).
        total_budget: Total event budget (> 0).

    Returns:
        List of validated BudgetLine objects with exact sums.

    Raises:
        ValueError: If total_budget <= 0 or lines sequence is empty.
    """
    if total_budget <= 0:
        raise ValueError(f"total_budget must be positive, got {total_budget}")

    if not lines:
        raise ValueError("Cannot calculate budget for empty lines sequence")

    target_total = round(float(total_budget), 2)

    # Normalize input into dictionaries
    raw_items: list[dict[str, Any]] = []
    for item in lines:
        if isinstance(item, BudgetLine):
            raw_items.append(
                {
                    "key": item.key,
                    "label": item.label,
                    "percent": float(item.percent),
                    "note": item.note,
                }
            )
        elif isinstance(item, ProposedBudgetLine):
            raw_items.append(
                {
                    "key": item.key,
                    "label": item.label,
                    "percent": float(item.percent),
                    "note": item.note,
                }
            )
        elif isinstance(item, dict):
            raw_items.append(
                {
                    "key": str(item.get("key", "misc")),
                    "label": str(item.get("label", item.get("key", "Miscellaneous"))),
                    "percent": float(item.get("percent", 0.0)),
                    "note": str(item.get("note", "")),
                }
            )
        else:
            raise TypeError(f"Unsupported budget item type: {type(item)}")

    # Handle percentage distribution
    sum_percents = sum(max(0.0, item["percent"]) for item in raw_items)
    if sum_percents <= 0.0:
        # Distribute equally if all percentages are zero or negative
        equal_pct = 100.0 / len(raw_items)
        for item in raw_items:
            item["percent"] = equal_pct
    else:
        # Scale percentages so they sum to exactly 100%
        for item in raw_items:
            item["percent"] = (max(0.0, item["percent"]) / sum_percents) * 100.0

    # Calculate initial rounded amounts (2 decimal places)
    amounts: list[float] = [
        round(target_total * (item["percent"] / 100.0), 2) for item in raw_items
    ]

    # Calculate rounding discrepancy
    current_sum = round(sum(amounts), 2)
    diff = round(target_total - current_sum, 2)

    if diff != 0.0:
        # Find index to absorb the difference: prefer 'contingency', else largest amount
        absorb_idx = -1
        for idx, item in enumerate(raw_items):
            if item["key"].strip().lower() in ("contingency", "emergency", "buffer"):
                absorb_idx = idx
                break

        if absorb_idx == -1:
            # Pick the category with the largest amount
            absorb_idx = max(range(len(amounts)), key=lambda i: amounts[i])

        # Adjust the chosen amount
        new_amount = round(amounts[absorb_idx] + diff, 2)
        if new_amount >= 0.0:
            amounts[absorb_idx] = new_amount
        else:
            # Fallback if subtracting diff would make amount negative
            amounts[absorb_idx] = 0.0
            remaining_diff = round(target_total - sum(amounts), 2)
            # Find largest non-negative item
            other_idx = max(range(len(amounts)), key=lambda i: amounts[i])
            amounts[other_idx] = round(amounts[other_idx] + remaining_diff, 2)

    # Build final BudgetLine objects and reconcile final percentages
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
