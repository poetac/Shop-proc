"""SQLModel entities for the CNC Shop Ops tool.

Operations only. The Invoice model is a *status mirror* of QuickBooks — it is
never the source of truth for money. See HANDOFF.md §10 for the data model and
§11 for the state machines these statuses belong to.
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Status enums (see HANDOFF.md §11)
# --------------------------------------------------------------------------- #
class QuoteStatus(str, Enum):
    DRAFT = "Draft"
    SENT = "Sent"
    ACCEPTED = "Accepted"
    DECLINED = "Declined"


class JobStatus(str, Enum):
    ACCEPTED = "Accepted"
    MATERIALS = "Materials"
    IN_QUEUE = "In Queue"
    MACHINING = "Machining"
    FINISHING_QC = "Finishing/QC"
    DONE = "Done"
    INVOICED = "Invoiced"
    PAID = "Paid"


class InvoiceStatus(str, Enum):
    DRAFT = "Draft"
    SENT = "Sent"
    PAID = "Paid"


class PaymentMethod(str, Enum):
    CARD = "card"
    ACH = "ACH"


# --------------------------------------------------------------------------- #
# Entities
# --------------------------------------------------------------------------- #
class Customer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    billing_address: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)

    quotes: list["Quote"] = Relationship(back_populates="customer")
    jobs: list["Job"] = Relationship(back_populates="customer")
    invoices: list["Invoice"] = Relationship(back_populates="customer")


class Quote(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id")
    quote_number: str = Field(index=True)
    status: QuoteStatus = Field(default=QuoteStatus.DRAFT)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)

    customer: Optional[Customer] = Relationship(back_populates="quotes")
    lines: list["QuoteLine"] = Relationship(
        back_populates="quote",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    job: Optional["Job"] = Relationship(back_populates="quote")


class QuoteLine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    quote_id: int = Field(foreign_key="quote.id")
    description: str
    qty: float = 1.0
    unit_price: float = 0.0

    quote: Optional[Quote] = Relationship(back_populates="lines")


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customer.id")
    quote_id: Optional[int] = Field(default=None, foreign_key="quote.id")
    job_number: str = Field(index=True)
    title: str
    due_date: Optional[date] = None
    status: JobStatus = Field(default=JobStatus.ACCEPTED)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)

    customer: Optional[Customer] = Relationship(back_populates="jobs")
    quote: Optional[Quote] = Relationship(back_populates="job")
    invoice: Optional["Invoice"] = Relationship(back_populates="job")


class Invoice(SQLModel, table=True):
    """A lightweight status mirror of a QuickBooks invoice.

    QuickBooks generates, sends, and collects. This record only tracks status
    so the shop's operations view stays in sync. `qb_reference` ties it back to
    the real QuickBooks invoice number.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id")
    customer_id: int = Field(foreign_key="customer.id")
    invoice_number: str = Field(index=True)
    amount: float = 0.0
    issue_date: date = Field(default_factory=date.today)
    due_date: date = Field(default_factory=date.today)
    status: InvoiceStatus = Field(default=InvoiceStatus.DRAFT)
    payment_method: Optional[PaymentMethod] = None
    paid_date: Optional[date] = None
    qb_reference: Optional[str] = None
    notes: Optional[str] = None

    job: Optional[Job] = Relationship(back_populates="invoice")
    customer: Optional[Customer] = Relationship(back_populates="invoices")


class Setting(SQLModel, table=True):
    """Simple key/value store for business info & numbering preferences (§8.6)."""

    key: str = Field(primary_key=True)
    value: str = ""
