"""Pure quote math. No pricing/costing engine — the owner types prices in;
this only sums what was typed (HANDOFF.md §8.2, §4 non-goals)."""

from __future__ import annotations

from typing import Iterable, Protocol


class _Line(Protocol):
    qty: float
    unit_price: float


def line_total(qty: float, unit_price: float) -> float:
    return round(qty * unit_price, 2)


def quote_total(lines: Iterable[_Line]) -> float:
    """Sum of qty * unit_price across all lines."""
    return round(sum(line_total(line.qty, line.unit_price) for line in lines), 2)
