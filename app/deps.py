"""Shared dependencies: the Jinja2 templates instance and common helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.logic.invoicing import is_due_soon, is_overdue

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Expose helpers and constants to every template.
templates.env.globals.update(
    today=date.today,
    is_overdue=is_overdue,
    is_due_soon=is_due_soon,
)


def money(value: float | None) -> str:
    """Format a number as USD for display."""
    return f"${(value or 0):,.2f}"


templates.env.filters["money"] = money


def render(name: str, context: dict, **kwargs):
    """Render a template. Thin wrapper over Starlette's TemplateResponse that
    keeps the (name, context) call order while satisfying the current API,
    which requires the request as the first argument."""
    request = context["request"]
    return templates.TemplateResponse(request, name, context, **kwargs)
