#!/usr/bin/env python3
"""Send the owner's operations reminder digest (HANDOFF.md §14).

Cron entry point — computes overdue / due-soon items and emails the owner if
SMTP is configured and there is anything to report. Schedule e.g. weekday 7am:
    0 7 * * 1-5  cd /app && python scripts/send_reminders.py >> /var/log/shop-reminders.log 2>&1

Exits 0 always (a missing SMTP config or an empty digest is not an error).
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from sqlmodel import Session, select  # noqa: E402

from app import mailer  # noqa: E402
from app.db import engine, init_db  # noqa: E402
from app.logic.reminders import build_digest, format_digest_text, is_empty  # noqa: E402
from app.models import Customer, Invoice, Job  # noqa: E402


def main() -> int:
    init_db()
    with Session(engine) as session:
        invoices = session.exec(select(Invoice)).all()
        jobs = session.exec(select(Job)).all()
        names = {c.id: c.name for c in session.exec(select(Customer)).all()}
        digest = build_digest(invoices, jobs, date.today())

        if is_empty(digest):
            print("reminders: nothing to report")
            return 0
        if not mailer.is_configured():
            print("reminders: SMTP not configured — skipping send")
            return 0

        body = format_digest_text(digest, names)
        ok = mailer.send_email(
            mailer.reminder_recipient(),
            "CNC Shop Ops — operations reminder",
            body,
        )
        if ok:
            stamp = datetime.now(timezone.utc).isoformat()
            for inv in digest["overdue_invoices"] + digest["due_soon_invoices"]:
                inv.last_reminded_at = stamp
                session.add(inv)
            session.commit()
            print(f"reminders: sent digest to {mailer.reminder_recipient()}")
        else:
            print("reminders: send failed (check SMTP settings)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
