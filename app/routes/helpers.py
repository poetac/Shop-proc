"""Small shared helpers for routes (numbering lookups)."""

from __future__ import annotations

from sqlmodel import Session, select

from app.logic.numbering import next_number
from app.models import Invoice, Job, Quote


def next_quote_number(session: Session) -> str:
    existing = session.exec(select(Quote.quote_number)).all()
    return next_number("Q", list(existing))


def next_job_number(session: Session) -> str:
    existing = session.exec(select(Job.job_number)).all()
    return next_number("J", list(existing))


def next_invoice_number(session: Session) -> str:
    existing = session.exec(select(Invoice.invoice_number)).all()
    return next_number("INV", list(existing))
