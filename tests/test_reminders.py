"""Tests for the owner reminder digest logic (HANDOFF.md §14)."""

from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.logic.reminders import build_digest, format_digest_text, is_empty


@dataclass
class Inv:
    invoice_number: str
    amount: float
    status: str
    due_date: date
    customer_id: int = 1


@dataclass
class Job:
    job_number: str
    title: str
    status: str
    due_date: Optional[date]


TODAY = date(2026, 6, 15)


def test_digest_categorizes_overdue_and_due_soon():
    invoices = [
        Inv("INV-1", 100, "Sent", date(2026, 6, 1)),    # overdue
        Inv("INV-2", 200, "Sent", date(2026, 6, 18)),   # due soon (within 7d)
        Inv("INV-3", 300, "Sent", date(2026, 7, 30)),   # far out — neither
        Inv("INV-4", 400, "Paid", date(2026, 6, 1)),    # paid — excluded
        Inv("INV-5", 500, "Draft", date(2026, 6, 1)),   # draft — excluded
    ]
    jobs = [
        Job("J-1", "Bracket", "Machining", date(2026, 6, 20)),  # due soon
        Job("J-2", "Plate", "Machining", date(2026, 8, 1)),     # far out
        Job("J-3", "Old", "Paid", date(2026, 6, 16)),           # not active
    ]
    d = build_digest(invoices, jobs, TODAY)

    assert [i.invoice_number for i in d["overdue_invoices"]] == ["INV-1"]
    assert [i.invoice_number for i in d["due_soon_invoices"]] == ["INV-2"]
    assert [j.job_number for j in d["due_soon_jobs"]] == ["J-1"]
    assert d["overdue_total"] == 100.0
    assert is_empty(d) is False


def test_digest_empty_when_all_clear():
    invoices = [Inv("INV-9", 100, "Sent", date(2026, 12, 31))]
    d = build_digest(invoices, [], TODAY)
    assert is_empty(d) is True


def test_format_digest_text_lists_items_and_disclaimer():
    invoices = [Inv("INV-1", 100, "Sent", date(2026, 6, 1))]
    d = build_digest(invoices, [], TODAY)
    text = format_digest_text(d, {1: "Acme"})
    assert "OVERDUE INVOICES (1)" in text
    assert "INV-1" in text and "Acme" in text
    assert "QuickBooks remains the source of truth" in text
