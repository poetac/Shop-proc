"""Regression tests for the red-team fixes (data-safety, auth, uploads)."""

from sqlmodel import Session, select


def _customer_and_job_at_done(client):
    """Create a customer + accepted quote -> job, advance the job to Done."""
    client.post("/customers", data={"name": "Acme"})
    from app.db import engine
    from app.models import Customer, Job, Quote

    with Session(engine) as s:
        cid = s.exec(select(Customer)).first().id
    client.post(
        "/quotes",
        data={"customer_id": cid, "description": ["Part"], "qty": ["1"], "unit_price": ["100"]},
    )
    with Session(engine) as s:
        quote = s.exec(select(Quote)).first()
    client.post(f"/quotes/{quote.id}/accept")
    with Session(engine) as s:
        job = s.exec(select(Job)).first()
    for _ in range(5):
        client.post(f"/jobs/{job.id}/move", data={"direction": "forward"})
    return cid, job.id


# --------------------------------------------------------------------------- #
# Data safety
# --------------------------------------------------------------------------- #
def test_second_invoice_for_same_job_is_refused(client):
    _cid, job_id = _customer_and_job_at_done(client)
    client.post("/invoices", data={"job_id": job_id, "amount": "100", "issue_date": "2026-01-01"})
    client.post("/invoices", data={"job_id": job_id, "amount": "999", "issue_date": "2026-02-01"})

    from app.db import engine
    from app.models import Invoice

    with Session(engine) as s:
        invoices = s.exec(select(Invoice).where(Invoice.job_id == job_id)).all()
    assert len(invoices) == 1
    assert invoices[0].amount == 100  # the second create did not overwrite/add


def test_second_invoice_does_not_revert_paid_job(client):
    from app.db import engine
    from app.models import Invoice, Job, JobStatus

    _cid, job_id = _customer_and_job_at_done(client)
    client.post("/invoices", data={"job_id": job_id, "amount": "100", "issue_date": "2026-01-01"})
    with Session(engine) as s:
        inv = s.exec(select(Invoice)).first()
    client.post(f"/invoices/{inv.id}/status", data={"status": "Paid", "payment_method": "ACH"})
    # Attempt a duplicate invoice on the now-Paid job.
    client.post("/invoices", data={"job_id": job_id, "amount": "5", "issue_date": "2026-03-01"})
    with Session(engine) as s:
        assert s.get(Job, job_id).status == JobStatus.PAID  # still Paid, not reverted


def test_cannot_delete_customer_with_records(client):
    cid, _job_id = _customer_and_job_at_done(client)
    resp = client.post(f"/customers/{cid}/delete")
    # Redirected back with an error; customer still exists.
    assert "still has" in resp.text.lower() or "can't delete" in resp.text.lower()

    from app.db import engine
    from app.models import Customer

    with Session(engine) as s:
        assert s.get(Customer, cid) is not None


def test_cannot_delete_job_with_invoice(client):
    from app.db import engine
    from app.models import Invoice, Job

    _cid, job_id = _customer_and_job_at_done(client)
    client.post("/invoices", data={"job_id": job_id, "amount": "100", "issue_date": "2026-01-01"})
    resp = client.post(f"/jobs/{job_id}/delete")
    assert "invoice" in resp.text.lower()
    with Session(engine) as s:
        assert s.get(Job, job_id) is not None
        assert s.exec(select(Invoice)).first() is not None


# --------------------------------------------------------------------------- #
# Auth / hardening
# --------------------------------------------------------------------------- #
def test_healthz_is_public():
    # A fresh client with no login can reach /healthz.
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        r = c.get("/healthz")
        assert r.status_code == 200 and r.json()["status"] == "ok"


def test_protected_page_redirects_when_unauthenticated():
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        r = c.get("/customers", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login"


def test_security_headers_present(client):
    r = client.get("/")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"


def test_logout_is_post_only(client):
    # GET /logout should not be a valid route (405), POST works.
    assert client.get("/logout", follow_redirects=False).status_code == 405
    assert client.post("/logout", follow_redirects=False).status_code == 303


def test_move_rejects_offsite_next_redirect(client):
    _cid, job_id = _customer_and_job_at_done(client)
    r = client.post(
        f"/jobs/{job_id}/move",
        data={"direction": "back", "next": "https://evil.example/steal"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/jobs"  # not the off-site URL


def test_disallowed_upload_rejected_with_message(client):
    _cid, job_id = _customer_and_job_at_done(client)
    r = client.post(
        f"/jobs/{job_id}/files",
        files={"upload": ("malware.exe", b"MZ", "application/octet-stream")},
    )
    assert "allowed" in r.text.lower() and "file type" in r.text.lower()
