"""Pure CSV parsing for customer import (HANDOFF.md §14 roadmap).

Accepts a header row and maps friendly column names to Customer fields. Returns
cleaned row dicts plus per-row errors — the route does the DB inserts. Uses the
stdlib csv module; no third-party dependency.
"""

from __future__ import annotations

import csv
import io

# Map accepted header spellings -> Customer field name.
_FIELD_ALIASES = {
    "name": "name",
    "customer": "name",
    "customer name": "name",
    "company": "company",
    "email": "email",
    "e-mail": "email",
    "phone": "phone",
    "telephone": "phone",
    "billing address": "billing_address",
    "billing_address": "billing_address",
    "address": "billing_address",
    "notes": "notes",
}

FIELDS = ("name", "company", "email", "phone", "billing_address", "notes")


def parse_customers(text: str) -> tuple[list[dict], list[str]]:
    """Parse CSV text into customer dicts.

    Returns (rows, errors). Each row has all FIELDS (missing ones as ""). A row
    with no name is skipped and reported. Unknown columns are ignored.
    """
    errors: list[str] = []
    text = (text or "").strip()
    if not text:
        return [], ["No CSV content provided."]

    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return [], ["No CSV content provided."]

    # Resolve each column index to a field name (or None to ignore).
    col_fields: list[str | None] = [
        _FIELD_ALIASES.get(col.strip().lower()) for col in header
    ]
    if "name" not in [f for f in col_fields if f]:
        return [], ["CSV must have a 'name' column."]

    rows: list[dict] = []
    for i, raw in enumerate(reader, start=2):  # line 2 = first data row
        if not any(cell.strip() for cell in raw):
            continue  # blank line
        record = {f: "" for f in FIELDS}
        for idx, value in enumerate(raw):
            if idx < len(col_fields) and col_fields[idx]:
                record[col_fields[idx]] = value.strip()
        if not record["name"]:
            errors.append(f"Line {i}: skipped (no name).")
            continue
        rows.append(record)

    return rows, errors
