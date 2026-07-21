"""Tests for the fast job-setup UX and shared helpers."""

from datetime import date

from sqlmodel import Session, select

from app.logic.parsing import parse_date, to_float


# --------------------------------------------------------------------------- #
# Shared parsing helpers
# --------------------------------------------------------------------------- #
def test_parse_date():
    assert parse_date("2026-07-21") == date(2026, 7, 21)
    assert parse_date("") is None
    assert parse_date("nonsense") is None


def test_to_float():
    assert to_float("3.5") == 3.5
    assert to_float("") == 0.0
    assert to_float("1o", default=1.0) == 1.0


# --------------------------------------------------------------------------- #
# Fast job setup
# --------------------------------------------------------------------------- #
def test_quick_add_job_with_new_customer(client):
    from app.models import Customer, Job

    resp = client.post(
        "/jobs",
        data={"title": "Sensor housing", "new_customer": "Fresh Co", "redirect": "board"},
    )
    assert resp.status_code == 200
    # Landed back on the board with a success flash.
    assert "created" in resp.text.lower()

    from app.db import engine

    with Session(engine) as s:
        cust = s.exec(select(Customer).where(Customer.name == "Fresh Co")).first()
        job = s.exec(select(Job)).first()
    assert cust is not None
    assert job.title == "Sensor housing" and job.customer_id == cust.id


def test_new_customer_reuses_existing_by_name(client):
    from app.db import engine
    from app.models import Customer

    client.post("/customers", data={"name": "Acme"})
    client.post("/jobs", data={"title": "Part A", "new_customer": "Acme"})
    with Session(engine) as s:
        acmes = s.exec(select(Customer).where(Customer.name == "Acme")).all()
    assert len(acmes) == 1  # did not create a duplicate customer


def test_job_requires_a_customer(client):
    from app.db import engine
    from app.models import Job

    resp = client.post("/jobs", data={"title": "Orphan"})
    assert "customer" in resp.text.lower()  # error flash shown on /jobs/new
    with Session(engine) as s:
        assert s.exec(select(Job)).first() is None


def test_board_renders_tap_to_move_controls(client):
    # Create a job at Accepted (a manual stage) and confirm the board shows the
    # move form (regression: manual_stages wasn't passed, so buttons vanished).
    client.post("/jobs", data={"title": "Bracket", "new_customer": "Acme"})
    from app.db import engine
    from app.models import Job

    with Session(engine) as s:
        job_id = s.exec(select(Job)).first().id
    board = client.get("/jobs")
    assert f"/jobs/{job_id}/move" in board.text
    # Quick-add form is present too.
    assert 'name="new_customer"' in board.text


def test_flash_is_one_time(client):
    client.post("/customers", data={"name": "Acme"})
    client.post("/jobs", data={"title": "Part", "new_customer": "Acme", "redirect": "board"})
    # First board load after redirect shows the flash...
    first = client.get("/jobs")
    # ...but the redirect already consumed it, so a fresh GET has no flash.
    assert "created" not in first.text.lower()
