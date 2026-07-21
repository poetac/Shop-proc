"""FastAPI application entry point.

Wires up session auth, static files, and the per-module routers. Tables are
created at startup (HANDOFF.md §5). Operations only — no accounting logic.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()

from app import auth  # noqa: E402
from app.db import init_db  # noqa: E402
from app.deps import render  # noqa: E402
from app.routes import (  # noqa: E402
    customers,
    dashboard,
    invoices,
    jobs,
    quotes,
    reminders,
    reports,
    settings,
)

STATIC_DIR = Path(__file__).parent / "static"

SECRET_KEY = os.getenv("SECRET_KEY", "")
# Session cookie gets the Secure flag unless explicitly disabled for local HTTP.
SESSION_HTTPS_ONLY = os.getenv("SESSION_HTTPS_ONLY", "1") != "0"


def _check_config() -> None:
    """Fail fast on insecure/missing config rather than booting a foot-gun."""
    if not SECRET_KEY or SECRET_KEY == "change-me":
        raise RuntimeError(
            "SECRET_KEY is unset or the placeholder 'change-me'. Set a random "
            "secret (e.g. `python -c \"import secrets; print(secrets.token_hex(32))\"`)."
        )
    if not auth.APP_PASSWORD_HASH:
        raise RuntimeError(
            "APP_PASSWORD_HASH is empty — no one can log in. Generate one with "
            "`python scripts/hash_password.py`."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_config()
    init_db()
    yield


app = FastAPI(title="CNC Shop Ops", lifespan=lifespan)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    # All assets are self-hosted (Pico/HTMX vendored under /static). Inline
    # styles/handlers still need 'unsafe-inline'; everything external is blocked.
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
    )
    return response


# Redirect unauthenticated requests to /login. Registered before
# SessionMiddleware so that SessionMiddleware ends up outermost and
# request.session is available inside the auth middleware.
app.middleware("http")(auth.auth_middleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY or "insecure-dev-only",
    same_site="lax",
    https_only=SESSION_HTTPS_ONLY,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --------------------------------------------------------------------------- #
# Auth routes (public)
# --------------------------------------------------------------------------- #
@app.get("/healthz")
async def healthz():
    """Unauthenticated liveness probe for container/platform healthchecks."""
    return {"status": "ok"}


@app.get("/login")
async def login_form(request: Request):
    if auth.is_authenticated(request):
        return RedirectResponse(url="/", status_code=303)
    return render("login.html", {"request": request, "error": None})


@app.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    # Run the (slow) bcrypt check first and unconditionally so a wrong username
    # can't be distinguished from a wrong password by response timing.
    password_ok = auth.verify_password(password)
    if password_ok and username == auth.APP_USERNAME:
        auth.login_user(request, username)
        return RedirectResponse(url="/", status_code=303)
    return render(
        "login.html",
        {"request": request, "error": "Invalid username or password."},
        status_code=401,
    )


@app.post("/logout")
async def logout(request: Request):
    auth.logout_user(request)
    return RedirectResponse(url="/login", status_code=303)


# --------------------------------------------------------------------------- #
# Module routers
# --------------------------------------------------------------------------- #
app.include_router(dashboard.router)
app.include_router(customers.router)
app.include_router(quotes.router)
app.include_router(jobs.router)
app.include_router(invoices.router)
app.include_router(reports.router)
app.include_router(reminders.router)
app.include_router(settings.router)
