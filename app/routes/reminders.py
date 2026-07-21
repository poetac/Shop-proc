"""Owner reminder digest (HANDOFF.md §14 roadmap).

Previews what needs attention (overdue / due-soon) and, when SMTP is configured,
emails the owner a digest. This is an operations heads-up for the owner — not
customer dunning (QuickBooks owns invoice sending and collection).
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app import mailer
from app.db import get_session
from app.deps import render
from app.logic.reminders import build_digest, format_digest_text, is_empty
from app.models import Customer, Invoice, Job

router = APIRouter(prefix="/reminders", tags=["reminders"])


def _digest_and_names(session: Session):
    invoices = session.exec(select(Invoice)).all()
    jobs = session.exec(select(Job)).all()
    names = {c.id: c.name for c in session.exec(select(Customer)).all()}
    return build_digest(invoices, jobs, date.today()), names


@router.get("")
async def reminders_page(
    request: Request, sent: str = "", session: Session = Depends(get_session)
):
    digest, _ = _digest_and_names(session)
    return render(
        "reminders.html",
        {
            "request": request,
            "digest": digest,
            "empty": is_empty(digest),
            "configured": mailer.is_configured(),
            "recipient": mailer.reminder_recipient(),
            "today": date.today(),
            "sent": sent,
        },
    )


@router.post("/send")
async def send_reminders(session: Session = Depends(get_session)):
    digest, names = _digest_and_names(session)
    if is_empty(digest) or not mailer.is_configured():
        return RedirectResponse(url="/reminders?sent=skipped", status_code=303)

    body = format_digest_text(digest, names)
    ok = mailer.send_email(
        mailer.reminder_recipient(),
        "CNC Shop Ops — operations reminder",
        body,
    )
    if ok:
        # Record that these invoices were included in a sent reminder.
        stamp = datetime.now(timezone.utc).isoformat()
        for inv in digest["overdue_invoices"] + digest["due_soon_invoices"]:
            inv.last_reminded_at = stamp
            session.add(inv)
        session.commit()
    return RedirectResponse(
        url=f"/reminders?sent={'ok' if ok else 'error'}", status_code=303
    )
