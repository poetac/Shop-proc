"""Quotes module (HANDOFF.md §8.2).

Store-only: the owner types line items and prices; total auto-sums. Accepting a
quote creates a linked, pre-filled Job.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.deps import flash, render
from app.logic.parsing import to_float
from app.logic.quoting import quote_total
from app.models import (
    Customer,
    Job,
    JobStatus,
    Quote,
    QuoteLine,
    QuoteStatus,
)
from app.routes.helpers import next_job_number, next_quote_number

router = APIRouter(prefix="/quotes", tags=["quotes"])


@router.get("")
async def list_quotes(request: Request, session: Session = Depends(get_session)):
    quotes = session.exec(select(Quote).order_by(Quote.created_at.desc())).all()
    return render(
        "quotes/list.html",
        {"request": request, "quotes": quotes, "quote_total": quote_total},
    )


@router.get("/new")
async def new_quote(
    request: Request,
    customer_id: int | None = None,
    session: Session = Depends(get_session),
):
    customers = session.exec(select(Customer).order_by(Customer.name)).all()
    return render(
        "quotes/form.html",
        {
            "request": request,
            "customers": customers,
            "selected_customer_id": customer_id,
        },
    )


@router.post("")
async def create_quote(
    request: Request,
    customer_id: int = Form(...),
    notes: str = Form(""),
    production_notes: str = Form(""),
    description: list[str] = Form(default=[]),
    qty: list[str] = Form(default=[]),
    unit_price: list[str] = Form(default=[]),
    session: Session = Depends(get_session),
):
    quote = Quote(
        customer_id=customer_id,
        quote_number=next_quote_number(session),
        notes=notes or None,
        production_notes=production_notes or None,
    )
    _apply_lines(quote, description, qty, unit_price)
    session.add(quote)
    session.commit()
    session.refresh(quote)
    return RedirectResponse(url=f"/quotes/{quote.id}", status_code=303)


@router.get("/{quote_id}")
async def quote_detail(
    quote_id: int, request: Request, session: Session = Depends(get_session)
):
    quote = session.get(Quote, quote_id)
    if not quote:
        return RedirectResponse(url="/quotes", status_code=303)
    return render(
        "quotes/detail.html",
        {"request": request, "quote": quote, "total": quote_total(quote.lines)},
    )


@router.get("/{quote_id}/print")
async def quote_print(
    quote_id: int, request: Request, session: Session = Depends(get_session)
):
    """Print-friendly quote (browser → Save as PDF). A minimal stand-in for
    'PDF export' that needs no heavy PDF dependency."""
    quote = session.get(Quote, quote_id)
    if not quote:
        return RedirectResponse(url="/quotes", status_code=303)
    from app.routes.settings import get_settings

    return render(
        "quotes/print.html",
        {
            "request": request,
            "quote": quote,
            "total": quote_total(quote.lines),
            "settings": get_settings(session),
        },
    )


@router.get("/{quote_id}/edit")
async def edit_quote(
    quote_id: int, request: Request, session: Session = Depends(get_session)
):
    quote = session.get(Quote, quote_id)
    if not quote:
        return RedirectResponse(url="/quotes", status_code=303)
    customers = session.exec(select(Customer).order_by(Customer.name)).all()
    return render(
        "quotes/form.html",
        {
            "request": request,
            "quote": quote,
            "customers": customers,
            "selected_customer_id": quote.customer_id,
        },
    )


@router.post("/{quote_id}")
async def update_quote(
    quote_id: int,
    customer_id: int = Form(...),
    notes: str = Form(""),
    production_notes: str = Form(""),
    description: list[str] = Form(default=[]),
    qty: list[str] = Form(default=[]),
    unit_price: list[str] = Form(default=[]),
    session: Session = Depends(get_session),
):
    quote = session.get(Quote, quote_id)
    if not quote:
        return RedirectResponse(url="/quotes", status_code=303)
    quote.customer_id = customer_id
    quote.notes = notes or None
    quote.production_notes = production_notes or None
    # Replace lines wholesale (simplest correct approach for low volume).
    for line in list(quote.lines):
        session.delete(line)
    quote.lines = []
    _apply_lines(quote, description, qty, unit_price)
    session.add(quote)
    session.commit()
    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=303)


@router.post("/{quote_id}/status")
async def set_status(
    quote_id: int,
    status: str = Form(...),
    session: Session = Depends(get_session),
):
    quote = session.get(Quote, quote_id)
    if quote:
        quote.status = QuoteStatus(status)
        session.add(quote)
        session.commit()
    return RedirectResponse(url=f"/quotes/{quote_id}", status_code=303)


@router.post("/{quote_id}/accept")
async def accept_quote(
    quote_id: int, request: Request, session: Session = Depends(get_session)
):
    """Accept the quote and create a pre-filled Job at *Accepted* (§11)."""
    quote = session.get(Quote, quote_id)
    if not quote:
        return RedirectResponse(url="/quotes", status_code=303)
    quote.status = QuoteStatus.ACCEPTED
    session.add(quote)

    # Don't create a second job if one already exists for this quote.
    existing = session.exec(select(Job).where(Job.quote_id == quote_id)).first()
    if existing:
        session.commit()
        flash(request, f"Quote already accepted — job {existing.job_number}.", "info")
        return RedirectResponse(url=f"/jobs/{existing.id}", status_code=303)

    title = quote.lines[0].description if quote.lines else f"Job from {quote.quote_number}"
    job = Job(
        customer_id=quote.customer_id,
        quote_id=quote.id,
        job_number=next_job_number(session),
        title=title,
        status=JobStatus.ACCEPTED,
        notes=quote.notes,
        # Carry the shop's quoting notes through to the job floor.
        production_notes=quote.production_notes,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    flash(request, f"Quote accepted — created job {job.job_number}.")
    return RedirectResponse(url=f"/jobs/{job.id}", status_code=303)


@router.post("/{quote_id}/delete")
async def delete_quote(
    quote_id: int, session: Session = Depends(get_session)
):
    quote = session.get(Quote, quote_id)
    if quote:
        session.delete(quote)
        session.commit()
    return RedirectResponse(url="/quotes", status_code=303)


def _apply_lines(
    quote: Quote,
    descriptions: list[str],
    qtys: list[str],
    unit_prices: list[str],
) -> None:
    """Attach typed line items, skipping empty rows."""
    for i, desc in enumerate(descriptions):
        desc = (desc or "").strip()
        if not desc:
            continue
        quote.lines.append(
            QuoteLine(
                description=desc,
                qty=to_float(qtys[i] if i < len(qtys) else "1"),
                unit_price=to_float(unit_prices[i] if i < len(unit_prices) else "0"),
            )
        )

