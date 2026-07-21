"""Pure job status-transition rules (HANDOFF.md §11).

Job flow: Accepted → Materials → In Queue → Machining → Finishing/QC → Done
          → Invoiced → Paid

Manual advancement is allowed up to *Done*. The last two stages are driven by
the linked invoice: creating an invoice moves a job to *Invoiced*; marking that
invoice Paid moves the job to *Paid*.
"""

from __future__ import annotations

from app.models import InvoiceStatus, JobStatus

# Ordered production flow.
JOB_FLOW: list[JobStatus] = [
    JobStatus.ACCEPTED,
    JobStatus.MATERIALS,
    JobStatus.IN_QUEUE,
    JobStatus.MACHINING,
    JobStatus.FINISHING_QC,
    JobStatus.DONE,
    JobStatus.INVOICED,
    JobStatus.PAID,
]

# The two stages the owner cannot set by hand — they follow the invoice.
INVOICE_DRIVEN: set[JobStatus] = {JobStatus.INVOICED, JobStatus.PAID}

# Stages a job can be manually moved to (everything up to and including Done).
MANUAL_STAGES: list[JobStatus] = [s for s in JOB_FLOW if s not in INVOICE_DRIVEN]


def can_manually_set(status: JobStatus) -> bool:
    """Manual moves are only allowed for non-invoice-driven stages."""
    return status not in INVOICE_DRIVEN


def next_status(current: JobStatus) -> JobStatus:
    """The next manual stage, capped at Done (invoice drives the rest)."""
    idx = JOB_FLOW.index(current)
    nxt = JOB_FLOW[min(idx + 1, len(JOB_FLOW) - 1)]
    if nxt in INVOICE_DRIVEN:
        return JobStatus.DONE
    return nxt


def prev_status(current: JobStatus) -> JobStatus:
    """The previous manual stage, floored at Accepted."""
    idx = JOB_FLOW.index(current)
    prev = JOB_FLOW[max(idx - 1, 0)]
    if prev in INVOICE_DRIVEN:
        return JobStatus.DONE
    return prev


def status_for_invoice(invoice_status: InvoiceStatus) -> JobStatus:
    """Map an invoice's status onto the job status it should drive.

    Sent/Draft invoice -> job Invoiced; Paid invoice -> job Paid.
    """
    if invoice_status == InvoiceStatus.PAID:
        return JobStatus.PAID
    return JobStatus.INVOICED
