"""Customers module (HANDOFF.md §8.1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlmodel import Session, or_, select

from app.db import get_session
from app.deps import render
from app.logic.csv_import import parse_customers
from app.models import Customer

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("")
async def list_customers(
    request: Request, q: str = "", session: Session = Depends(get_session)
):
    stmt = select(Customer)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Customer.name.ilike(like),
                Customer.company.ilike(like),
                Customer.email.ilike(like),
            )
        )
    customers = session.exec(stmt.order_by(Customer.name)).all()
    template = "partials/customer_rows.html" if request.headers.get("HX-Request") else "customers/list.html"
    return render(
        template, {"request": request, "customers": customers, "q": q}
    )


@router.get("/new")
async def new_customer(request: Request):
    return render(
        "customers/form.html", {"request": request, "customer": None}
    )


@router.post("")
async def create_customer(
    request: Request,
    name: str = Form(...),
    company: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    billing_address: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
):
    customer = Customer(
        name=name,
        company=company or None,
        email=email or None,
        phone=phone or None,
        billing_address=billing_address or None,
        notes=notes or None,
    )
    session.add(customer)
    session.commit()
    session.refresh(customer)
    return RedirectResponse(url=f"/customers/{customer.id}", status_code=303)


# --------------------------------------------------------------------------- #
# CSV import (HANDOFF.md §14 roadmap). Defined before /{customer_id} so the
# "import" path segment isn't parsed as a customer id.
# --------------------------------------------------------------------------- #
@router.get("/import")
async def import_form(request: Request):
    return render(
        "customers/import.html",
        {"request": request, "created": None, "errors": None},
    )


@router.post("/import")
async def import_customers(
    request: Request,
    csv_text: str = Form(""),
    csv_file: UploadFile | None = File(None),
    session: Session = Depends(get_session),
):
    text = csv_text
    if csv_file is not None and csv_file.filename:
        text = (await csv_file.read()).decode("utf-8", errors="replace")

    rows, errors = parse_customers(text)
    created = 0
    for row in rows:
        session.add(
            Customer(
                name=row["name"],
                company=row["company"] or None,
                email=row["email"] or None,
                phone=row["phone"] or None,
                billing_address=row["billing_address"] or None,
                notes=row["notes"] or None,
            )
        )
        created += 1
    if created:
        session.commit()
    return render(
        "customers/import.html",
        {"request": request, "created": created, "errors": errors},
    )


@router.get("/{customer_id}")
async def customer_detail(
    customer_id: int, request: Request, session: Session = Depends(get_session)
):
    customer = session.get(Customer, customer_id)
    if not customer:
        return RedirectResponse(url="/customers", status_code=303)
    return render(
        "customers/detail.html", {"request": request, "customer": customer}
    )


@router.get("/{customer_id}/edit")
async def edit_customer(
    customer_id: int, request: Request, session: Session = Depends(get_session)
):
    customer = session.get(Customer, customer_id)
    if not customer:
        return RedirectResponse(url="/customers", status_code=303)
    return render(
        "customers/form.html", {"request": request, "customer": customer}
    )


@router.post("/{customer_id}")
async def update_customer(
    customer_id: int,
    name: str = Form(...),
    company: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    billing_address: str = Form(""),
    notes: str = Form(""),
    session: Session = Depends(get_session),
):
    customer = session.get(Customer, customer_id)
    if not customer:
        return RedirectResponse(url="/customers", status_code=303)
    customer.name = name
    customer.company = company or None
    customer.email = email or None
    customer.phone = phone or None
    customer.billing_address = billing_address or None
    customer.notes = notes or None
    session.add(customer)
    session.commit()
    return RedirectResponse(url=f"/customers/{customer_id}", status_code=303)


@router.post("/{customer_id}/delete")
async def delete_customer(
    customer_id: int, session: Session = Depends(get_session)
):
    customer = session.get(Customer, customer_id)
    if customer:
        session.delete(customer)
        session.commit()
    return RedirectResponse(url="/customers", status_code=303)
