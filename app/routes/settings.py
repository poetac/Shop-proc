"""Settings module (HANDOFF.md §8.6) — minimal business info & preferences."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.db import get_session
from app.deps import render
from app.models import Setting

router = APIRouter(prefix="/settings", tags=["settings"])

# Keys the settings page manages, with defaults.
DEFAULTS = {
    "business_name": "",
    "business_address": "",
    "net_terms_days": "30",
}


def get_settings(session: Session) -> dict[str, str]:
    stored = {s.key: s.value for s in session.exec(select(Setting)).all()}
    return {**DEFAULTS, **stored}


@router.get("")
async def settings_page(request: Request, session: Session = Depends(get_session)):
    return render(
        "settings.html", {"request": request, "settings": get_settings(session)}
    )


@router.post("")
async def save_settings(
    request: Request,
    business_name: str = Form(""),
    business_address: str = Form(""),
    net_terms_days: str = Form("30"),
    session: Session = Depends(get_session),
):
    values = {
        "business_name": business_name,
        "business_address": business_address,
        "net_terms_days": net_terms_days,
    }
    for key, value in values.items():
        setting = session.get(Setting, key)
        if setting:
            setting.value = value
        else:
            setting = Setting(key=key, value=value)
        session.add(setting)
    session.commit()
    return RedirectResponse(url="/settings", status_code=303)
