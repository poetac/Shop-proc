"""Jobs board module (HANDOFF.md §8.3) — the whiteboard replacement.

Kanban board grouped by stage. Tap-to-move advances/retreats a job through the
manual stages (up to Done); the last two stages are driven by the invoice.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.deps import render
from app.logic.jobs import JOB_FLOW, MANUAL_STAGES, can_manually_set, next_status, prev_status
from app.models import Customer, Job, JobStatus, Quote

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
    session: Session = Depends(get_session),
):
    from app.routes.helpers import next_job_number

    job = Job(
        customer_id=customer_id,
        job_number=next_job_number(session),
        title=title,
        due_date=_parse_date(due_date),
        notes=notes or None,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return RedirectResponse(url=f"/jobs/{job.id}", status_code=303)


@router.get("/{job_id}")
async def job_detail(
    job_id: int, request: Request, session: Session = Depends(get_session)
):
    job = session.get(Job, job_id)
    if not job:
        return RedirectResponse(url="/jobs", status_code=303)
    return render(
        "jobs/detail.html",
        {"request": request, "job": job, "manual_stages": MANUAL_STAGES, "today": date.today()},
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
    session: Session = Depends(get_session),
):
    job = session.get(Job, job_id)
    if not job:
        return RedirectResponse(url="/jobs", status_code=303)
    job.customer_id = customer_id
    job.title = title
    job.due_date = _parse_date(due_date)
    job.notes = notes or None
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

    return RedirectResponse(url=next, status_code=303)


@router.post("/{job_id}/delete")
async def delete_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if job:
        session.delete(job)
        session.commit()
    return RedirectResponse(url="/jobs", status_code=303)


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
