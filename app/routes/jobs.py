"""Jobs board module (HANDOFF.md §8.3) — the whiteboard replacement.

Kanban board grouped by stage. Tap-to-move advances/retreats a job through the
manual stages (up to Done); the last two stages are driven by the invoice.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlmodel import Session, select

from app import storage
from app.db import get_session
from app.deps import render
from app.logic.jobs import JOB_FLOW, MANUAL_STAGES, can_manually_set, next_status, prev_status
from app.models import Customer, Job, JobFile, JobStatus, Quote

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def board(request: Request, session: Session = Depends(get_session)):
    jobs = session.exec(select(Job)).all()
    columns = {status: [] for status in JOB_FLOW}
    for job in jobs:
        columns.setdefault(job.status, []).append(job)
    return render(
        "jobs/board.html",
        {
            "request": request,
            "columns": columns,
            "flow": JOB_FLOW,
            "today": date.today(),
        },
    )


@router.get("/new")
async def new_job(
    request: Request,
    customer_id: int | None = None,
    session: Session = Depends(get_session),
):
    customers = session.exec(select(Customer).order_by(Customer.name)).all()
    return render(
        "jobs/form.html",
        {
            "request": request,
            "job": None,
            "customers": customers,
            "manual_stages": MANUAL_STAGES,
            "selected_customer_id": customer_id,
        },
    )


@router.post("")
async def create_job(
    request: Request,
    customer_id: int = Form(...),
    title: str = Form(...),
    due_date: str = Form(""),
    notes: str = Form(""),
    production_notes: str = Form(""),
    session: Session = Depends(get_session),
):
    from app.routes.helpers import next_job_number

    job = Job(
        customer_id=customer_id,
        job_number=next_job_number(session),
        title=title,
        due_date=_parse_date(due_date),
        notes=notes or None,
        production_notes=production_notes or None,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return RedirectResponse(url=f"/jobs/{job.id}", status_code=303)


@router.get("/{job_id}")
async def job_detail(
    job_id: int,
    request: Request,
    error: str = "",
    session: Session = Depends(get_session),
):
    job = session.get(Job, job_id)
    if not job:
        return RedirectResponse(url="/jobs", status_code=303)
    messages = {
        "has_invoice": "Can't delete a job that has an invoice. Delete the "
        "linked invoice first.",
        "bad_file": "That file type isn't allowed. Use PDF, image, or CAD "
        "(STEP/STL/DXF/DWG) files.",
        "too_big": f"That file is too large (max {storage.MAX_BYTES // (1024 * 1024)} MB).",
    }
    return render(
        "jobs/detail.html",
        {
            "request": request,
            "job": job,
            "manual_stages": MANUAL_STAGES,
            "today": date.today(),
            "error": messages.get(error),
        },
    )


@router.get("/{job_id}/edit")
async def edit_job(
    job_id: int, request: Request, session: Session = Depends(get_session)
):
    job = session.get(Job, job_id)
    if not job:
        return RedirectResponse(url="/jobs", status_code=303)
    customers = session.exec(select(Customer).order_by(Customer.name)).all()
    return render(
        "jobs/form.html",
        {
            "request": request,
            "job": job,
            "customers": customers,
            "manual_stages": MANUAL_STAGES,
            "selected_customer_id": job.customer_id,
        },
    )


@router.post("/{job_id}")
async def update_job(
    job_id: int,
    customer_id: int = Form(...),
    title: str = Form(...),
    due_date: str = Form(""),
    notes: str = Form(""),
    production_notes: str = Form(""),
    session: Session = Depends(get_session),
):
    job = session.get(Job, job_id)
    if not job:
        return RedirectResponse(url="/jobs", status_code=303)
    job.customer_id = customer_id
    job.title = title
    job.due_date = _parse_date(due_date)
    job.notes = notes or None
    job.production_notes = production_notes or None
    session.add(job)
    session.commit()
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)


@router.post("/{job_id}/move")
async def move_job(
    job_id: int,
    direction: str = Form(...),
    next: str = Form("/jobs"),
    session: Session = Depends(get_session),
):
    """Tap-to-move a job forward/backward through the manual stages.

    Invoice-driven stages (Invoiced/Paid) cannot be set by hand.
    """
    job = session.get(Job, job_id)
    if not job:
        return RedirectResponse(url="/jobs", status_code=303)

    if can_manually_set(job.status):
        job.status = next_status(job.status) if direction == "forward" else prev_status(job.status)
        session.add(job)
        session.commit()

    # Only allow local redirects (guard against open-redirect via `next`).
    target = next if next.startswith("/") and not next.startswith("//") else "/jobs"
    return RedirectResponse(url=target, status_code=303)


@router.post("/{job_id}/delete")
async def delete_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        return RedirectResponse(url="/jobs", status_code=303)
    # Block deletion while an invoice is linked (its job_id is NOT NULL, so the
    # delete would fail at the DB). Delete the invoice first if truly intended.
    if job.invoice:
        return RedirectResponse(
            url=f"/jobs/{job_id}?error=has_invoice", status_code=303
        )
    # Remove attachment bytes from disk before the file rows cascade-delete.
    for f in job.files:
        storage.delete_file(f.stored_path)
    session.delete(job)
    session.commit()
    return RedirectResponse(url="/jobs", status_code=303)


# --------------------------------------------------------------------------- #
# File attachments (drawings/prints/CAD) — HANDOFF.md §8.3
# --------------------------------------------------------------------------- #
@router.post("/{job_id}/files")
async def upload_file(
    job_id: int,
    upload: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    job = session.get(Job, job_id)
    if not job:
        return RedirectResponse(url="/jobs", status_code=303)

    filename = upload.filename or "file"
    if not storage.is_allowed(filename):
        return RedirectResponse(url=f"/jobs/{job_id}?error=bad_file", status_code=303)

    # Read in bounded chunks so an oversized upload can't exhaust memory: stop
    # as soon as we exceed the cap (read one byte past to detect the overflow).
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > storage.MAX_BYTES:
            return RedirectResponse(url=f"/jobs/{job_id}?error=too_big", status_code=303)
        chunks.append(chunk)

    data = b"".join(chunks)
    if data:
        stored = storage.save_upload(job_id, filename, data)
        session.add(JobFile(job_id=job_id, filename=filename, stored_path=stored))
        session.commit()
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)


@router.get("/{job_id}/files/{file_id}")
async def download_file(
    job_id: int, file_id: int, session: Session = Depends(get_session)
):
    job_file = session.get(JobFile, file_id)
    if not job_file or job_file.job_id != job_id:
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)
    try:
        path = storage.absolute_path(job_file.stored_path)
    except ValueError:
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)
    return FileResponse(path, filename=job_file.filename)


@router.post("/{job_id}/files/{file_id}/delete")
async def delete_file(
    job_id: int, file_id: int, session: Session = Depends(get_session)
):
    job_file = session.get(JobFile, file_id)
    if job_file and job_file.job_id == job_id:
        storage.delete_file(job_file.stored_path)
        session.delete(job_file)
        session.commit()
    return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
