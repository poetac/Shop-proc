"""Tests for job file attachments (HANDOFF.md §8.3)."""

from app import storage


def test_is_allowed_extensions():
    assert storage.is_allowed("drawing.pdf") is True
    assert storage.is_allowed("part.STEP") is True
    assert storage.is_allowed("evil.exe") is False
    assert storage.is_allowed("noext") is False


def test_absolute_path_blocks_escape():
    import pytest

    with pytest.raises(ValueError):
        storage.absolute_path("../../etc/passwd")


def _make_job(client) -> int:
    client.post("/customers", data={"name": "Acme"})
    from app.db import engine
    from sqlmodel import Session, select
    from app.models import Customer

    with Session(engine) as s:
        customer_id = s.exec(select(Customer)).first().id
    client.post(
        "/jobs",
        data={"customer_id": customer_id, "title": "Bracket", "due_date": "", "notes": ""},
    )
    from app.models import Job

    with Session(engine) as s:
        return s.exec(select(Job)).first().id


def test_upload_attaches_file_and_download_returns_it(client):
    job_id = _make_job(client)

    resp = client.post(
        f"/jobs/{job_id}/files",
        files={"upload": ("print.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert resp.status_code == 200  # redirect followed to job detail

    from app.db import engine
    from sqlmodel import Session, select
    from app.models import JobFile

    with Session(engine) as s:
        job_file = s.exec(select(JobFile)).first()
    assert job_file is not None
    assert job_file.filename == "print.pdf"

    dl = client.get(f"/jobs/{job_id}/files/{job_file.id}")
    assert dl.status_code == 200
    assert dl.content == b"%PDF-1.4 fake"


def test_disallowed_extension_is_rejected(client):
    job_id = _make_job(client)
    client.post(
        f"/jobs/{job_id}/files",
        files={"upload": ("malware.exe", b"MZ", "application/octet-stream")},
    )
    from app.db import engine
    from sqlmodel import Session, select
    from app.models import JobFile

    with Session(engine) as s:
        assert s.exec(select(JobFile)).first() is None
