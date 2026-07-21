"""Reports page (HANDOFF.md §14 roadmap) — operational summaries only."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.db import get_session
from app.deps import render
from app.logic.reports import quote_win_rate, revenue_by_customer, revenue_by_month
from app.models import Customer, Invoice, Quote

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
async def reports_page(request: Request, session: Session = Depends(get_session)):
    invoices = session.exec(select(Invoice)).all()
    quotes = session.exec(select(Quote)).all()
    names = {c.id: c.name for c in session.exec(select(Customer)).all()}

    by_month = revenue_by_month(invoices)
    by_customer = revenue_by_customer(invoices, names)
    win = quote_win_rate(quotes)

    return render(
        "reports.html",
        {
            "request": request,
            "by_month": by_month,
            "by_customer": by_customer,
            "win": win,
            "month_max": max((amt for _, amt in by_month), default=0),
            "collected_total": round(sum(amt for _, amt in by_month), 2),
        },
    )
