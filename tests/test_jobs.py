"""Tests for job status transitions (HANDOFF.md §11).

Pure-logic tests plus an end-to-end walk through the quote -> job -> invoice
flow via the HTTP routes.
"""

from app.logic.jobs import (
    MANUAL_STAGES,
    can_manually_set,
    next_status,
    prev_status,
    status_for_invoice,
)
from app.models import InvoiceStatus, JobStatus


# --------------------------------------------------------------------------- #
# Pure logic
# --------------------------------------------------------------------------- #
def test_manual_stages_exclude_invoice_driven():
    assert JobStatus.INVOICED not in MANUAL_STAGES
    assert JobStatus.PAID not in MANUAL_STAGES
    assert JobStatus.DONE in MANUAL_STAGES


def test_next_status_caps_at_done():
    assert next_status(JobStatus.ACCEPTED) == JobStatus.MATERIALS
    assert next_status(JobStatus.FINISHING_QC) == JobStatus.DONE
    # Done does not advance manually into invoice-driven stages.
    assert next_status(JobStatus.DONE) == JobStatus.DONE


def test_prev_status_floors_at_accepted():
    assert prev_status(JobStatus.MATERIALS) == JobStatus.ACCEPTED
    assert prev_status(JobStatus.ACCEPTED) == JobStatus.ACCEPTED


def test_can_manually_set():
    assert can_manually_set(JobStatus.MACHINING) is True
    assert can_manually_set(JobStatus.INVOICED) is False
    assert can_manually_set(JobStatus.PAID) is False


def test_status_for_invoice():
    assert status_for_invoice(InvoiceStatus.DRAFT) == JobStatus.INVOICED
    assert status_for_invoice(InvoiceStatus.SENT) == JobStatus.INVOICED
    assert status_for_invoice(InvoiceStatus.PAID) == JobStatus.PAID


# --------------------------------------------------------------------------- #
# End-to-end flow through the routes
# --------------------------------------------------------------------------- #
def _create_customer(client) -> int:
    client.post("/customers", data={"name": "Acme Co"})
    resp = client.get("/customers")
    # Grab the customer id from the follow-up detail flow instead of parsing.
    from app.db import engine
    from sqlmodel import Session, select
    from app.models import Customer

    with Session(engine) as s:
        return s.exec(select(Customer)).first().id


def _first_job_status(client_unused) -> JobStatus:
    from app.db import engine
    from sqlmodel import Session, select
    from app.models import Job

    with Session(engine) as s:
        return s.exec(select(Job)).first().status


def test_accepting_quote_creates_job_at_accepted(client):
    customer_id = _create_customer(client)
    client.post(
        "/quotes",
        data={
            "customer_id": customer_id,
            "notes": "",
            "description": ["Bracket"],
            "qty": ["4"],
            "unit_price": ["25"],
        },
    )
    from app.db import engine
    from sqlmodel import Session, select
    from app.models import Quote

    with Session(engine) as s:
        quote = s.exec(select(Quote)).first()

    client.post(f"/quotes/{quote.id}/accept")

    assert _first_job_status(client) == JobStatus.ACCEPTED


def test_production_notes_carry_from_quote_to_job(client):
    customer_id = _create_customer(client)
    client.post(
        "/quotes",
        data={
            "customer_id": customer_id,
            "notes": "Customer-facing note",
            "production_notes": "Needs a 6mm end mill with 40mm reach; soft jaws op 2.",
            "description": ["Bracket"],
            "qty": ["1"],
            "unit_price": ["100"],
        },
    )
    from app.db import engine
    from sqlmodel import Session, select
    from app.models import Job, Quote

    with Session(engine) as s:
        quote = s.exec(select(Quote)).first()
        assert quote.production_notes.startswith("Needs a 6mm")

    client.post(f"/quotes/{quote.id}/accept")

    with Session(engine) as s:
        job = s.exec(select(Job)).first()
    # Shop notes followed the quote onto the job; customer note did not leak in.
    assert job.production_notes == "Needs a 6mm end mill with 40mm reach; soft jaws op 2."


def test_invoice_flow_moves_job_to_invoiced_then_paid(client):
    customer_id = _create_customer(client)
    client.post(
        "/quotes",
        data={
            "customer_id": customer_id,
            "description": ["Bracket"],
            "qty": ["4"],
            "unit_price": ["25"],
        },
    )
    from app.db import engine
    from sqlmodel import Session, select
    from app.models import Invoice, Job, Quote

    with Session(engine) as s:
        quote = s.exec(select(Quote)).first()
    client.post(f"/quotes/{quote.id}/accept")

    with Session(engine) as s:
        job = s.exec(select(Job)).first()
    job_id = job.id

    # Advance the job to Done (Accepted -> ... -> Done is 5 forward moves).
    for _ in range(5):
        client.post(f"/jobs/{job_id}/move", data={"direction": "forward"})
    with Session(engine) as s:
        assert s.get(Job, job_id).status == JobStatus.DONE

    # Create the invoice: job -> Invoiced, amount defaults from quote total.
    client.post(
        "/invoices",
        data={
            "job_id": job_id,
            "amount": "100.00",
            "issue_date": "2026-01-01",
        },
    )
    with Session(engine) as s:
        assert s.get(Job, job_id).status == JobStatus.INVOICED
        invoice = s.exec(select(Invoice)).first()
        assert invoice.due_date.isoformat() == "2026-01-31"  # Net 30

    # Mark the invoice Paid: job -> Paid, paid_date recorded.
    client.post(
        f"/invoices/{invoice.id}/status",
        data={"status": "Paid", "payment_method": "ACH"},
    )
    with Session(engine) as s:
        assert s.get(Job, job_id).status == JobStatus.PAID
        assert s.get(Invoice, invoice.id).paid_date is not None
