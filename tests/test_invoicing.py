"""Tests for Net 30 due dates and the computed overdue flag (HANDOFF.md §11)."""

from datetime import date

from app.logic.invoicing import due_date, is_due_soon, is_overdue


def test_due_date_is_issue_plus_30():
    assert due_date(date(2026, 1, 1)) == date(2026, 1, 31)
    assert due_date(date(2026, 2, 1)) == date(2026, 3, 3)  # crosses month


def test_due_date_custom_terms():
    assert due_date(date(2026, 1, 1), terms_days=15) == date(2026, 1, 16)


def test_overdue_only_when_sent_past_due_and_unpaid():
    due = date(2026, 1, 31)
    after = date(2026, 2, 15)
    before = date(2026, 1, 20)

    # Sent + past due + unpaid -> overdue.
    assert is_overdue("Sent", due, paid=False, today=after) is True
    # Not yet past due.
    assert is_overdue("Sent", due, paid=False, today=before) is False
    # Paid is never overdue.
    assert is_overdue("Sent", due, paid=True, today=after) is False
    # Draft is never overdue.
    assert is_overdue("Draft", due, paid=False, today=after) is False


def test_overdue_boundary_on_due_date():
    due = date(2026, 1, 31)
    # On the due date it is not yet overdue (today must be strictly past).
    assert is_overdue("Sent", due, paid=False, today=due) is False
    # One day later it is.
    assert is_overdue("Sent", due, paid=False, today=date(2026, 2, 1)) is True


def test_due_soon_within_seven_days():
    today = date(2026, 1, 1)
    assert is_due_soon(date(2026, 1, 5), days=7, today=today) is True
    assert is_due_soon(date(2026, 1, 8), days=7, today=today) is True
    assert is_due_soon(date(2026, 1, 9), days=7, today=today) is False
    # Already past due is not "due soon".
    assert is_due_soon(date(2025, 12, 31), days=7, today=today) is False
