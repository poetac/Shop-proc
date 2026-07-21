"""Invoices module (HANDOFF.md §8.4) — a status mirror, NOT a generator.

QuickBooks generates, sends, and collects. This tracks status only. Creating an
invoice moves the linked job to *Invoiced*; marking it Paid moves the job to
*Paid* and records paid_date. Overdue is computed on display, never stored.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.deps import render
from app.logic.invoicing import due_date as compute_due_date
from app.logic.invoicing import is_overdue
from app.logic.quoting import quote_total
from app.models import (
    Invoice,
    InvoiceStatus,
    Job,
    JobStatus,
    PaymentMethod,
)
from app.routes.helpers import next_invoice_number

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("")
async def list_invoices(request: Request, session: Session = Depends(get_session)):
    invoices = session.exec(select(Invoice).order_by(Invoice.issue_date.desc())).all()
    today = date.today()
    outstanding = sum(
        inv.amount for inv in invoices if inv.status != InvoiceStatus.PAID
    )
    overdue_total = sum(
        inv.amount
        for inv in invoices
        if is_overdue(inv.status.value, inv.due_date, inv.status == InvoiceStatus.PAID, today)
    )
    return render(
        "invoices/list.html",
        {
            "request": request,
            "invoices": invoices,
            "outstanding": outstanding,
            "overdue_total": overdue_total,
            "today": today,
        },
    )


@router.get("/new")
async def new_invoice(
    request: Request,
    job_id: int | None = None,
    session: Session = Depends(get_session),
):
    """Create-from-job form. Amount defaults from the job's quote total."""
    job = session.get(Job, job_id) if job_id else None
    default_amount = 0.0
    if job and job.quote:
        default_amount = quote_total(job.quote.lines)
    issue = date.today()
    return render(
        "invoices/form.html",
        {
            "request": request,
            "job": job,
            "default_amount": default_amount,
            "issue_date": issue,
            "due_date": compute_due_date(issue),
        },
    )


@router.post("")
async def create_invoice(
    request: Request,
    job_id: int = Form(...),
    amount: float = Form(...),
    issue_date: str = Form(...),
    due_date: str = Form(""),
    qb_reference: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
):
    job = session.get(Job, job_id)
    if not job:
        return RedirectResponse(url="/jobs", status_code=303)

    # A job has at most one invoice (HANDOFF.md §10). Don't create a second —
    # it would corrupt the 1-1 link and could revert a Paid job to Invoiced.
    existing = session.exec(select(Invoice).where(Invoice.job_id == job.id)).first()
    if existing:
        return RedirectResponse(url=f"/invoices/{existing.id}", status_code=303)

    issue = _parse_date(issue_date) or date.today()
    due = _parse_date(due_date) or compute_due_date(issue)
    invoice = Invoice(
        job_id=job.id,
        customer_id=job.customer_id,
        invoice_number=next_invoice_number(session),
        amount=amount,
        issue_date=issue,
        due_date=due,
        status=InvoiceStatus.DRAFT,
        qb_reference=qb_reference or None,
        notes=notes or None,
    )
    session.add(invoice)

    # Creating an invoice drives the job to Invoiced (§11).
    job.status = JobStatus.INVOICED
    session.add(job)
    session.commit()
    session.refresh(invoice)
    return RedirectResponse(url=f"/invoices/{invoice.id}", status_code=303)


@router.get("/{invoice_id}")
async def invoice_detail(
    invoice_id: int, request: Request, session: Session = Depends(get_session)
):
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        return RedirectResponse(url="/invoices", status_code=303)
    return render(
        "invoices/detail.html",
        {"request": request, "invoice": invoice, "today": date.today()},
    )


@router.post("/{invoice_id}")
async def update_invoice(
    invoice_id: int,
    amount: float = Form(...),
    issue_date: str = Form(...),
    due_date: str = Form(""),
    payment_method: str = Form(""),
    qb_reference: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
):
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        return RedirectResponse(url="/invoices", status_code=303)
    issue = _parse_date(issue_date) or invoice.issue_date
    invoice.amount = amount
    invoice.issue_date = issue
    invoice.due_date = _parse_date(due_date) or compute_due_date(issue)
    invoice.payment_method = PaymentMethod(payment_method) if payment_method else None
    invoice.qb_reference = qb_reference or None
    invoice.notes = notes or None
    session.add(invoice)
    session.commit()
    return RedirectResponse(url=f"/invoices/{invoice_id}", status_code=303)


@router.post("/{invoice_id}/status")
async def set_status(
    invoice_id: int,
    status: str = Form(...),
    payment_method: str = Form(""),
    session: Session = Depends(get_session),
):
    """Advance the invoice status. Marking Paid records paid_date and drives
    the linked job to *Paid* (§11)."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        return RedirectResponse(url="/invoices", status_code=303)

    new_status = InvoiceStatus(status)
    invoice.status = new_status
    if new_status == InvoiceStatus.PAID:
        invoice.paid_date = date.today()
        if payment_method:
            invoice.payment_method = PaymentMethod(payment_method)
        job = session.get(Job, invoice.job_id)
        if job:
            job.status = JobStatus.PAID
            session.add(job)
    else:
        invoice.paid_date = None
        # Re-opening an invoice pulls the job back to Invoiced.
        job = session.get(Job, invoice.job_id)
        if job and job.status == JobStatus.PAID:
            job.status = JobStatus.INVOICED
            session.add(job)
    session.add(invoice)
    session.commit()
    return RedirectResponse(url=f"/invoices/{invoice_id}", status_code=303)


@router.post("/{invoice_id}/delete")
async def delete_invoice(
    invoice_id: int, session: Session = Depends(get_session)
):
    invoice = session.get(Invoice, invoice_id)
    if invoice:
        # Return the job to Done so it can be re-invoiced.
        job = session.get(Job, invoice.job_id)
        if job and job.status in (JobStatus.INVOICED, JobStatus.PAID):
            job.status = JobStatus.DONE
            session.add(job)
        session.delete(invoice)
        session.commit()
    return RedirectResponse(url="/invoices", status_code=303)


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
