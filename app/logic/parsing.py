"""Shared form-value parsing helpers (pure).

Centralized so routes don't each re-implement lenient date/number parsing.
"""

from __future__ import annotations

from datetime import date


def parse_date(value: str | None) -> date | None:
    """Parse an ISO date string; return None on empty/invalid input."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def to_float(value: str | None, default: float = 0.0) -> float:
    """Parse a float; return `default` on empty/invalid input."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
