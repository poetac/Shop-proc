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


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="CNC Shop Ops", lifespan=lifespan)

# Redirect unauthenticated requests to /login. Registered before
# SessionMiddleware so that SessionMiddleware ends up outermost and
# request.session is available inside the auth middleware.
app.middleware("http")(auth.auth_middleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "change-me"),
    same_site="lax",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --------------------------------------------------------------------------- #
# Auth routes (public)
# --------------------------------------------------------------------------- #
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
    if username == auth.APP_USERNAME and auth.verify_password(password):
        auth.login_user(request, username)
        return RedirectResponse(url="/", status_code=303)
    return render(
        "login.html",
        {"request": request, "error": "Invalid username or password."},
        status_code=401,
    )


@app.get("/logout")
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
