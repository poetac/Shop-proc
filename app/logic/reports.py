"""Pure reporting logic (HANDOFF.md §14 roadmap).

These summaries are *operational and indicative only* — QuickBooks remains the
source of truth for money. All figures are derived from the app's invoice
mirror and quote records. No tax or accounting logic here.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable, Optional, Protocol


class _Invoice(Protocol):
    amount: float
    status: object  # has a .value of "Paid" etc.
    issue_date: date
    paid_date: Optional[date]
    customer_id: int


class _Quote(Protocol):
    status: object  # has a .value of "Accepted" / "Declined" / ...


def _is_paid(inv: _Invoice) -> bool:
    status = getattr(inv.status, "value", inv.status)
    return status == "Paid"


def _revenue_date(inv: _Invoice) -> date:
    """Recognize revenue on the paid date when known, else the issue date."""
    return inv.paid_date or inv.issue_date


def revenue_by_month(invoices: Iterable[_Invoice]) -> list[tuple[str, float]]:
    """Total of PAID invoices grouped by YYYY-MM, oldest first."""
    totals: dict[str, float] = defaultdict(float)
    for inv in invoices:
        if _is_paid(inv):
            key = _revenue_date(inv).strftime("%Y-%m")
            totals[key] += inv.amount
    return [(k, round(totals[k], 2)) for k in sorted(totals)]


def revenue_by_customer(
    invoices: Iterable[_Invoice], names: dict[int, str]
) -> list[tuple[str, float]]:
    """Total of PAID invoices grouped by customer, highest first."""
    totals: dict[int, float] = defaultdict(float)
    for inv in invoices:
        if _is_paid(inv):
            totals[inv.customer_id] += inv.amount
    rows = [
        (names.get(cid, f"Customer {cid}"), round(total, 2))
        for cid, total in totals.items()
    ]
    return sorted(rows, key=lambda r: r[1], reverse=True)


def quote_win_rate(quotes: Iterable[_Quote]) -> dict:
    """Win rate over *decided* quotes (Accepted or Declined).

    Draft/Sent quotes are still open and excluded from the denominator.
    """
    accepted = declined = 0
    for q in quotes:
        status = getattr(q.status, "value", q.status)
        if status == "Accepted":
            accepted += 1
        elif status == "Declined":
            declined += 1
    decided = accepted + declined
    rate = round(accepted / decided, 4) if decided else 0.0
    return {
        "accepted": accepted,
        "declined": declined,
        "decided": decided,
        "win_rate": rate,
    }
