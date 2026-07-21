"""Auto-numbering for quotes, jobs, and invoices (HANDOFF.md §12).

Format: Q-YYYY-NNN, J-YYYY-NNN, INV-YYYY-NNN. Counters reset each calendar year.
Pure string logic here; the DB lookup of the last number lives in the routes.
"""

from __future__ import annotations

import re
from datetime import date


def next_number(prefix: str, existing: list[str], year: int | None = None) -> str:
    """Return the next number for `prefix` given all `existing` numbers.

    Only numbers from the current year count toward the sequence; the counter
    resets to 001 each January.
    """
    if year is None:
        year = date.today().year
    pattern = re.compile(rf"^{re.escape(prefix)}-{year}-(\d+)$")
    highest = 0
    for value in existing:
        m = pattern.match(value or "")
        if m:
            highest = max(highest, int(m.group(1)))
    return f"{prefix}-{year}-{highest + 1:03d}"
