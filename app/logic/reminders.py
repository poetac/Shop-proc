"""Pure logic for the owner's operations reminder digest (HANDOFF.md §14).

These reminders go to the *owner* — a heads-up about what needs attention. They
are NOT customer dunning: QuickBooks owns invoice sending and payment
collection. We only surface overdue/due-soon items so nothing slips.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Optional, Protocol

from app.logic.invoicing import is_due_soon, is_overdue


class _Invoice(Protocol):
    amount: float
    status: object
    due_date: date


class _Job(Protocol):
    title: str
    status: object
    due_date: Optional[date]


# Job statuses that are still open work (mirrors the dashboard's definition).
_ACTIVE_JOB_STATUSES = {
    "Accepted", "Materials", "In Queue", "Machining", "Finishing/QC", "Done",
}


def _status_value(obj) -> str:
    return getattr(obj.status, "value", obj.status)


def build_digest(
    invoices: Iterable[_Invoice],
    jobs: Iterable[_Job],
    today: date | None = None,
    due_soon_days: int = 7,
) -> dict:
    """Categorize what the owner should look at right now."""
    if today is None:
        today = date.today()

    overdue_invoices = []
    due_soon_invoices = []
    for inv in invoices:
        status = _status_value(inv)
        paid = status == "Paid"
        if is_overdue(status, inv.due_date, paid, today):
            overdue_invoices.append(inv)
        elif status == "Sent" and not paid and is_due_soon(inv.due_date, due_soon_days, today):
            due_soon_invoices.append(inv)

    due_soon_jobs = [
        j
        for j in jobs
        if _status_value(j) in _ACTIVE_JOB_STATUSES
        and j.due_date is not None
        and today <= j.due_date <= today + timedelta(days=due_soon_days)
    ]

    return {
        "overdue_invoices": overdue_invoices,
        "due_soon_invoices": due_soon_invoices,
        "due_soon_jobs": due_soon_jobs,
        "overdue_total": round(sum(i.amount for i in overdue_invoices), 2),
    }


def is_empty(digest: dict) -> bool:
    return not (
        digest["overdue_invoices"]
        or digest["due_soon_invoices"]
        or digest["due_soon_jobs"]
    )


def format_digest_text(digest: dict, customer_names: dict[int, str] | None = None) -> str:
    """Render the digest as a plain-text email body."""
    names = customer_names or {}

    def cust(obj) -> str:
        return names.get(getattr(obj, "customer_id", None), "")

    lines: list[str] = ["CNC Shop Ops — operations reminder", ""]

    ov = digest["overdue_invoices"]
    lines.append(f"OVERDUE INVOICES ({len(ov)}) — ${digest['overdue_total']:,.2f}")
    if ov:
        for inv in ov:
            lines.append(f"  - {inv.invoice_number} {cust(inv)}: ${inv.amount:,.2f} (due {inv.due_date})")
    else:
        lines.append("  none")
    lines.append("")

    ds = digest["due_soon_invoices"]
    lines.append(f"INVOICES DUE SOON ({len(ds)})")
    if ds:
        for inv in ds:
            lines.append(f"  - {inv.invoice_number} {cust(inv)}: ${inv.amount:,.2f} (due {inv.due_date})")
    else:
        lines.append("  none")
    lines.append("")

    dj = digest["due_soon_jobs"]
    lines.append(f"JOBS DUE WITHIN 7 DAYS ({len(dj)})")
    if dj:
        for job in dj:
            lines.append(f"  - {job.job_number} {job.title}: due {job.due_date} ({_status_value(job)})")
    else:
        lines.append("  none")
    lines.append("")
    lines.append("QuickBooks remains the source of truth for money. This is an operations heads-up.")
    return "\n".join(lines)
