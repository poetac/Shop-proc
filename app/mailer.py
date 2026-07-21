"""Minimal SMTP email sender for owner reminder digests (HANDOFF.md §14).

Configured entirely via env vars. If SMTP isn't configured, sending is disabled
and the reminders page falls back to on-screen preview only — nothing crashes.
No third-party dependency; uses the stdlib smtplib.

Env:
  SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD,
  SMTP_FROM (default SMTP_USER), SMTP_TLS ("1"/"0", default "1"),
  REMINDER_EMAIL (where digests go; default SMTP_FROM/SMTP_USER)
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def is_configured() -> bool:
    return bool(_env("SMTP_HOST") and reminder_recipient())


def reminder_recipient() -> str:
    return _env("REMINDER_EMAIL") or _env("SMTP_FROM") or _env("SMTP_USER")


def send_email(to: str, subject: str, body: str) -> bool:
    """Send a plaintext email. Returns True on success, False if unconfigured
    or on any SMTP error (callers should surface the False)."""
    host = _env("SMTP_HOST")
    if not host or not to:
        return False

    msg = EmailMessage()
    msg["From"] = _env("SMTP_FROM") or _env("SMTP_USER") or to
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    port = int(_env("SMTP_PORT", "587"))
    user = _env("SMTP_USER")
    password = _env("SMTP_PASSWORD")
    use_tls = _env("SMTP_TLS", "1") != "0"

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            if use_tls:
                server.starttls()
            if user:
                server.login(user, password)
            server.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError):
        return False
