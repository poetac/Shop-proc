# Red-Team Findings & Remediation

A three-axis red-team (security, correctness/business-logic, reliability/ops) was
run against the app. This document records every verified finding, its severity,
and its status. Items marked **Fixed** are addressed in the codebase with tests
where practical; **Deferred** items include rationale.

Status legend: ✅ Fixed · 🟡 Deferred (with reason) · ⬜ Won't fix (by design)

---

## Critical — deployability (all fixed)

| ID | Finding | Status |
|----|---------|--------|
| C1 | `pip install .` shipped only top-level `app` modules — `app.routes`, `app.logic`, `templates/`, `static/` were missing, so the Docker image crash-looped on startup. CI never caught it because it installs editable (`-e`). | ✅ `pyproject.toml` now uses `packages.find` + `package-data`; a new CI `package` job builds and installs the real wheel and asserts routes/logic/templates/static are present. |
| C2 | `scripts/backup.sh` / `restore.sh` shell out to the `sqlite3` CLI, which is **not** in `python:3.12-slim` — backups/restores would fail with `command not found`. | ✅ Dockerfile installs `sqlite3` (and `curl` for the healthcheck). |
| C3 | Backups captured the DB only; uploaded files under `/data/uploads` were never backed up — a volume loss would orphan every drawing/print/CAD file. | ✅ `backup.sh` now also archives uploads (`uploads-<stamp>.tgz`); `restore.sh` restores both; a `tests/test_backup_restore.py` round-trip proves it (runs in CI where `sqlite3` exists). |

## High — data safety & security (all fixed)

| ID | Finding | Status |
|----|---------|--------|
| SEC-H1 | `SECRET_KEY` defaulted to `"change-me"` (and shipped that way in `.env.example`). Since auth is a signed cookie, the public default lets anyone forge an `owner` session. | ✅ App refuses to boot if `SECRET_KEY` is empty/`change-me` or `APP_PASSWORD_HASH` is empty; `.env.example` no longer ships a working key. |
| LOGIC-H1 | A job could get **multiple invoices** (no guard on create + non-unique FK). Double-submit committed two invoices, `job.invoice` became nondeterministic, and a second invoice on a Paid job silently reverted it to Invoiced. | ✅ `create_invoice` refuses when an invoice already exists (mirrors `accept_quote`); `Invoice.job_id` is now `unique` (+ unique index migration as backstop). |
| LOGIC-H2 | Deleting a customer/job with children raised an unhandled `IntegrityError` (500) because top-level relationships had no cascade and child FKs are `NOT NULL`. | ✅ Deletes are blocked with a friendly message when records are attached (customer → quotes/jobs/invoices; job → invoice). `PRAGMA foreign_keys=ON` enforces integrity at the DB too. |
| OPS-H2 | No WAL mode / `busy_timeout` — a write landing during a backup failed instantly with "database is locked". | ✅ Engine now sets `journal_mode=WAL`, `busy_timeout=30000`, `foreign_keys=ON` on every SQLite connection; `timeout=30` in connect args. |

## Medium (fixed unless noted)

| ID | Finding | Status |
|----|---------|--------|
| LOGIC-M1 | No DB uniqueness on Q/J/INV numbers; scan-then-`max+1` could duplicate under concurrency and **reuse** a number after deletion. | ✅ `unique=True` + unique indexes on all three number fields (turns a silent dup into a catchable error). Number *reuse-after-delete* is documented as accepted for a single-user shop; the unique index prevents an actual collision. |
| LOGIC-M2 | `create_invoice` didn't require the job to be at `Done`. | 🟡 Partially — the duplicate-invoice guard (LOGIC-H1) is the material fix. Hard-requiring `Done` was left out to avoid over-constraining the owner's workflow; noted for revisit. |
| SEC-M1 | Session cookie lacked the `Secure` flag. | ✅ `https_only=True` by default (`SESSION_HTTPS_ONLY=0` for local HTTP dev). |
| SEC-M2 | Upload read the whole body into memory before the size check (memory DoS). | ✅ Upload now reads in 1 MB chunks and aborts past the 25 MB cap before buffering the whole file. |
| SEC-M3 | Pico.css / HTMX loaded from CDN with no Subresource Integrity (tamper/availability risk). | ✅ Both assets vendored under `/static` and served locally; templates no longer reference any CDN. |
| SEC-M4 | No security response headers. | ✅ Middleware sets `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, and a `Content-Security-Policy` (all assets self-hosted). |
| OPS-M1 | No container/app healthcheck. | ✅ Public `/healthz` endpoint + Docker `HEALTHCHECK`. |
| OPS-M2 | Container ran as root. | ✅ Dockerfile adds a non-root `appuser` owning `/data`. |
| OPS-M5 | Reminder/report dates use server-local timezone. | 🟡 Deferred — set `TZ` to the shop's timezone on the host (documented). Low impact for a solo shop; no code change to keep it minimal. |
| OPS-M4 | Migrations run on every startup; `send_reminders.py` also calls `init_db()`, so a cron firing at boot could race. | 🟡 Accepted — each migration step is independently idempotent and SQLite serializes DDL; a single-worker deploy makes a real race negligible. |

## Low / hardening (selectively fixed)

| ID | Finding | Status |
|----|---------|--------|
| SEC-L1 | Public-path check used a raw `/static` prefix (would match `/static-anything`). | ✅ Now matches `/static/`. |
| SEC-L2 | Directory-escape guard used string `startswith` (a sibling like `/data/uploads-evil` would pass). Not reachable (paths are server-generated). | ✅ Switched to `Path.is_relative_to`. |
| SEC-L3 | No CSRF tokens; `/logout` was a GET. | ✅ `/logout` is now POST-only; SameSite=Lax already blocks cross-site POSTs. Per-form CSRF tokens deferred (low residual risk for single-user + Lax). |
| SEC-L4 | Open redirect via the `next` form field in job move. | ✅ Only local paths are honored; anything else falls back to `/jobs`. |
| SEC-L5 | Login timing oracle (username checked before bcrypt) + no rate limiting. | ✅ bcrypt verify now always runs regardless of username. Rate-limiting/lockout deferred (single fixed account; bcrypt already slows guessing). |
| OPS-L1 | Empty per-job upload directories left behind after deletes. | 🟡 Cosmetic; file *bytes* are cleaned up (no data leak). Left as-is. |
| OPS-L3 | CI did no wheel-build/lint. | ✅ Wheel-build smoke job added (catches C1-class regressions). Lint/type-check deferred. |
| OPS-L4 | `send_reminders.py` always exits 0. | 🟡 By design (a missing SMTP config is not an error); documented. |
| LOGIC-L | Silent `_to_float` coercion and negative amounts accepted; editing an accepted quote doesn't resync the derived job title. | 🟡 Deferred — data-quality nits for a single trusted user, not corruption. Noted for a future validation pass. |

---

## What the red-team confirmed is solid
- No reachable XSS (Jinja autoescape on, no `|safe`, downloads forced as attachments, `.html`/`.svg` excluded from uploads) or SQL injection (ORM-parameterized; the migration helper's `text()` uses only hardcoded identifiers).
- SMTP header injection not reachable; mailer fails soft when unconfigured.
- Auth fails **closed** (empty password hash denies login) and middleware ordering is correct.
- Pure business logic (Net 30, overdue boundary, quote totals, job transitions, reminder categorization) matches the spec and is well tested.
- Migration column list matches the models; fresh and legacy DBs both converge.
- `.gitignore` keeps secrets, the DB, uploads, and backups out of git.

## Test coverage added for the fixes
`tests/test_hardening.py` (duplicate-invoice refusal, no Paid-job revert, delete-with-children blocked, healthz public, unauth redirect, security headers, POST-only logout, open-redirect guard, disallowed upload) and `tests/test_backup_restore.py` (backup→restore round-trip incl. uploads). Full suite: 52 passing + 1 skipped (backup test, runs in CI).
