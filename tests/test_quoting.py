"""Tests for quote totals (HANDOFF.md §11)."""

from dataclasses import dataclass

from app.logic.quoting import line_total, quote_total


@dataclass
class Line:
    qty: float
    unit_price: float


def test_line_total():
    assert line_total(3, 10.0) == 30.0
    assert line_total(2.5, 4.0) == 10.0


def test_quote_total_sums_lines():
    lines = [Line(2, 50.0), Line(1, 125.0), Line(3, 10.0)]
    assert quote_total(lines) == 255.0


def test_quote_total_empty_is_zero():
    assert quote_total([]) == 0.0


def test_quote_total_handles_fractional_quantities():
    lines = [Line(1.5, 20.0), Line(0.25, 8.0)]
    assert quote_total(lines) == 32.0
