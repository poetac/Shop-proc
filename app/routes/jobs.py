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
from app.deps import flash, render
from app.logic.jobs import JOB_FLOW, MANUAL_STAGES, can_manually_set, next_status, prev_status
from app.logic.parsing import parse_date
from app.models import Customer, Job, JobFile
from app.routes.helpers import next_job_number

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def board(request: Request, session: Session = Depends(get_session)):
    jobs = session.exec(select(Job)).all()
    columns = {status: [] for status in JOB_FLOW}
    for job in jobs:
        columns.setdefault(job.status, []).append(job)
    customers = session.exec(select(Customer).order_by(Customer.name)).all()
    return render(
        "jobs/board.html",
        {
            "request": request,
            "columns": columns,
            "flow": JOB_FLOW,
            "today": date.today(),
            # Needed by the job-card partial so tap-to-move buttons render.
            "manual_stages": MANUAL_STAGES,
            "customers": customers,
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
    title: str = Form(...),
    customer_id: int | None = Form(None),
    new_customer: str = Form(""),
    due_date: str = Form(""),
    notes: str = Form(""),
    production_notes: str = Form(""),
    redirect: str = Form("detail"),
    session: Session = Depends(get_session),
):
    customer = _resolve_customer(session, customer_id, new_customer)
    if customer is None:
        flash(request, "Pick a customer or type a new customer name.", "error")
        return RedirectResponse(url="/jobs/new", status_code=303)

    job = Job(
        customer_id=customer.id,
        job_number=next_job_number(session),
        title=title,
        due_date=parse_date(due_date),
        notes=notes or None,
        production_notes=production_notes or None,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    flash(request, f"Job {job.job_number} created for {customer.name}.")
    if redirect == "board":
        return RedirectResponse(url="/jobs", status_code=303)
    return RedirectResponse(url=f"/jobs/{job.id}", status_code=303)


def _resolve_customer(
    session: Session, customer_id: int | None, new_name: str
) -> Customer | None:
    """Find the selected customer, or create one from a typed name (reusing an
    existing customer with the same name). Returns None if neither is given."""
    new_name = (new_name or "").strip()
    if new_name:
        existing = session.exec(
            select(Customer).where(Customer.name == new_name)
        ).first()
        if existing:
            return existing
        customer = Customer(name=new_name)
        session.add(customer)
        session.commit()
        session.refresh(customer)
        return customer
    if customer_id:
        return session.get(Customer, customer_id)
    return None


@router.get("/{job_id}")
async def job_detail(
    job_id: int, request: Request, session: Session = Depends(get_session)
):
    job = session.get(Job, job_id)
    if not job:
        return RedirectResponse(url="/jobs", status_code=303)
    return render(
        "jobs/detail.html",
        {
            "request": request,
            "job": job,
            "manual_stages": MANUAL_STAGES,
            "today": date.today(),
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
    request: Request,
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
    job.due_date = parse_date(due_date)
    job.notes = notes or None
    job.production_notes = production_notes or None
    session.add(job)
    session.commit()
    flash(request, f"Job {job.job_number} updated.")
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
async def delete_job(
    job_id: int, request: Request, session: Session = Depends(get_session)
):
    job = session.get(Job, job_id)
    if not job:
        return RedirectResponse(url="/jobs", status_code=303)
    # Block deletion while an invoice is linked (its job_id is NOT NULL, so the
    # delete would fail at the DB). Delete the invoice first if truly intended.
    if job.invoice:
        flash(request, "Can't delete a job that has an invoice. Delete the linked invoice first.", "error")
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)
    # Remove attachment bytes from disk before the file rows cascade-delete.
    for f in job.files:
        storage.delete_file(f.stored_path)
    number = job.job_number
    session.delete(job)
    session.commit()
    flash(request, f"Deleted job {number}.")
    return RedirectResponse(url="/jobs", status_code=303)


# --------------------------------------------------------------------------- #
# File attachments (drawings/prints/CAD) — HANDOFF.md §8.3
# --------------------------------------------------------------------------- #
@router.post("/{job_id}/files")
async def upload_file(
    job_id: int,
    request: Request,
    upload: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    job = session.get(Job, job_id)
    if not job:
        return RedirectResponse(url="/jobs", status_code=303)

    filename = upload.filename or "file"
    if not storage.is_allowed(filename):
        flash(request, "That file type isn't allowed. Use PDF, image, or CAD (STEP/STL/DXF/DWG) files.", "error")
        return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)

    # Read in bounded chunks so an oversized upload can't exhaust memory: stop
    # as soon as we exceed the cap.
    max_mb = storage.MAX_BYTES // (1024 * 1024)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > storage.MAX_BYTES:
            flash(request, f"That file is too large (max {max_mb} MB).", "error")
            return RedirectResponse(url=f"/jobs/{job_id}", status_code=303)
        chunks.append(chunk)

    data = b"".join(chunks)
    if data:
        stored = storage.save_upload(job_id, filename, data)
        session.add(JobFile(job_id=job_id, filename=filename, stored_path=stored))
        session.commit()
        flash(request, f"Attached {filename}.")
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
