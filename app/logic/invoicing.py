"""Pure invoicing logic: Net 30 due dates and the computed overdue flag.

Overdue is *never stored* — it is derived on display (HANDOFF.md §8.4, §11).
No tax or accounting logic lives here; QuickBooks owns the money.
"""

from __future__ import annotations

from datetime import date, timedelta

NET_TERMS_DAYS = 30


def due_date(issue_date: date, terms_days: int = NET_TERMS_DAYS) -> date:
    """due_date = issue_date + terms_days (Net 30 by default)."""
    return issue_date + timedelta(days=terms_days)


def is_overdue(status: str, due: date, paid: bool, today: date | None = None) -> bool:
    """Overdue == Sent + today past due_date + still unpaid.

    Draft and Paid invoices are never overdue.
    """
    if today is None:
        today = date.today()
    if paid:
        return False
    if status != "Sent":
        return False
    return today > due


def is_due_soon(due: date, days: int = 7, today: date | None = None) -> bool:
    """True when the due date is within `days` days from today (and not past)."""
    if today is None:
        today = date.today()
    return today <= due <= today + timedelta(days=days)
