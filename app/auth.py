"""Single-user session-based authentication (HANDOFF.md §5).

Credentials come from env vars: APP_USERNAME and APP_PASSWORD_HASH (a bcrypt
hash). The session cookie is signed with SECRET_KEY via SessionMiddleware.
"""

from __future__ import annotations

import os

from fastapi import Request
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

APP_USERNAME = os.getenv("APP_USERNAME", "owner")
APP_PASSWORD_HASH = os.getenv("APP_PASSWORD_HASH", "")

# Routes reachable without a session.
PUBLIC_PATHS = {"/login", "/logout", "/healthz"}
# Trailing slash so a future route like "/static-report" isn't treated as public.
PUBLIC_PREFIXES = ("/static/",)


def verify_password(password: str) -> bool:
    if not APP_PASSWORD_HASH:
        return False
    try:
        return pwd_context.verify(password, APP_PASSWORD_HASH)
    except ValueError:
        return False


def hash_password(password: str) -> str:
    """Helper for generating a hash for .env (see README)."""
    return pwd_context.hash(password)


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get("user"))


def login_user(request: Request, username: str) -> None:
    request.session["user"] = username


def logout_user(request: Request) -> None:
    request.session.clear()


def is_public_path(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)


async def auth_middleware(request: Request, call_next):
    """Redirect unauthenticated users to /login for all non-public paths."""
    if not is_public_path(request.url.path) and not is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return await call_next(request)
