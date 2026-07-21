"""Tests for reporting logic (HANDOFF.md §14 roadmap)."""

from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.logic.reports import quote_win_rate, revenue_by_customer, revenue_by_month


@dataclass
class Inv:
    amount: float
    status: str
    issue_date: date
    paid_date: Optional[date]
    customer_id: int


@dataclass
class Q:
    status: str


def test_revenue_by_month_only_counts_paid_and_groups():
    invoices = [
        Inv(100, "Paid", date(2026, 1, 5), date(2026, 1, 20), 1),
        Inv(50, "Paid", date(2026, 1, 10), date(2026, 1, 25), 2),
        Inv(200, "Paid", date(2026, 2, 1), date(2026, 2, 3), 1),
        Inv(999, "Sent", date(2026, 2, 1), None, 1),  # unpaid — excluded
    ]
    assert revenue_by_month(invoices) == [("2026-01", 150.0), ("2026-02", 200.0)]


def test_revenue_by_month_uses_issue_date_when_unpaid_date_missing():
    # A Paid invoice with no paid_date falls back to issue_date.
    invoices = [Inv(75, "Paid", date(2026, 3, 9), None, 1)]
    assert revenue_by_month(invoices) == [("2026-03", 75.0)]


def test_revenue_by_customer_sorted_desc():
    invoices = [
        Inv(100, "Paid", date(2026, 1, 5), date(2026, 1, 6), 1),
        Inv(300, "Paid", date(2026, 1, 5), date(2026, 1, 6), 2),
        Inv(50, "Paid", date(2026, 1, 5), date(2026, 1, 6), 1),
        Inv(500, "Draft", date(2026, 1, 5), None, 2),  # unpaid — excluded
    ]
    names = {1: "Acme", 2: "Globex"}
    assert revenue_by_customer(invoices, names) == [("Globex", 300.0), ("Acme", 150.0)]


def test_quote_win_rate_ignores_open_quotes():
    quotes = [
        Q("Accepted"), Q("Accepted"), Q("Accepted"),
        Q("Declined"),
        Q("Draft"), Q("Sent"),  # open — not counted in denominator
    ]
    result = quote_win_rate(quotes)
    assert result["accepted"] == 3
    assert result["declined"] == 1
    assert result["decided"] == 4
    assert result["win_rate"] == 0.75


def test_quote_win_rate_no_decisions_is_zero():
    assert quote_win_rate([Q("Draft"), Q("Sent")]) == {
        "accepted": 0,
        "declined": 0,
        "decided": 0,
        "win_rate": 0.0,
    }
