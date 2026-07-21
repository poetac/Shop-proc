"""Dashboard / Home (HANDOFF.md §8.5)."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.db import get_session
from app.deps import render
from app.logic.invoicing import is_overdue
from app.models import Invoice, InvoiceStatus, Job, JobStatus, Quote, QuoteStatus

router = APIRouter(tags=["dashboard"])

# Jobs that are still "active" work (not finished/invoiced/paid).
ACTIVE_JOB_STATUSES = {
    JobStatus.ACCEPTED,
    JobStatus.MATERIALS,
    JobStatus.IN_QUEUE,
    JobStatus.MACHINING,
    JobStatus.FINISHING_QC,
    JobStatus.DONE,
}


@router.get("/")
async def dashboard(request: Request, session: Session = Depends(get_session)):
    today = date.today()
    soon = today + timedelta(days=7)

    invoices = session.exec(select(Invoice)).all()
    outstanding = sum(
        inv.amount for inv in invoices if inv.status != InvoiceStatus.PAID
    )
    overdue_invoices = [
        inv
        for inv in invoices
        if is_overdue(inv.status.value, inv.due_date, inv.status == InvoiceStatus.PAID, today)
    ]

    jobs = session.exec(select(Job)).all()
    active_jobs = [j for j in jobs if j.status in ACTIVE_JOB_STATUSES]
    due_soon_jobs = [
        j
        for j in active_jobs
        if j.due_date is not None and today <= j.due_date <= soon
    ]

    sent_quotes = session.exec(
        select(Quote).where(Quote.status == QuoteStatus.SENT)
    ).all()

    return render(
        "dashboard.html",
        {
            "request": request,
            "outstanding": outstanding,
            "overdue_invoices": overdue_invoices,
            "overdue_total": sum(i.amount for i in overdue_invoices),
            "active_jobs": active_jobs,
            "due_soon_jobs": due_soon_jobs,
            "sent_quotes": sent_quotes,
            "today": today,
        },
    )
