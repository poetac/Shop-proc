# CNC Shop Ops

A minimal, single-user web app for a solo CNC machine shop to run daily
operations — customers, quotes, a jobs board, and invoice **status** tracking.
It is **operations only**: QuickBooks Online owns all accounting, tax, invoice
sending, and payment collection. The invoice records here are a lightweight
mirror tied back to QuickBooks by a `qb_reference`. See [`HANDOFF.md`](HANDOFF.md)
for the full spec and [`CLAUDE.md`](CLAUDE.md) for maintenance rules.

## Features
- **Customers** — CRUD, live search, CSV import, detail page with related records.
- **Quotes** — multi-line items with auto-total, status flow, one-click convert-to-job,
  print/PDF view, and **production/shop notes** that carry through to the job.
- **Jobs board** — kanban by stage, tap-to-move, file attachments (drawings/prints/CAD).
- **Invoices** — QuickBooks status mirror, Net 30 due dates, computed overdue flag, receivables.
- **Dashboard** — outstanding, overdue, active jobs, due-soon, quotes awaiting.
- **Reports** — revenue by month/customer and quote win rate (operational/indicative only).
- **Reminders** — an owner operations digest (overdue / due-soon) you can email to yourself.
- **Settings** — business info and Net 30 default; auto-numbering `Q-/J-/INV-YYYY-NNN`.

## Stack
Python 3.12 · FastAPI · Jinja2 + HTMX · Pico.css · SQLite (SQLModel) · session auth.

## Local setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# Generate a bcrypt password hash and paste it into .env as APP_PASSWORD_HASH:
python scripts/hash_password.py

uvicorn app.main:app --reload
```
Then open http://127.0.0.1:8000 and log in with `APP_USERNAME` / your password.

### Environment variables (`.env`)
| Var | Purpose |
|-----|---------|
| `SECRET_KEY` | Signs the session cookie. Use a long random string. |
| `APP_USERNAME` | Login username. |
| `APP_PASSWORD_HASH` | bcrypt hash of the login password (see above). |
| `DATABASE_URL` | SQLite URL, e.g. `sqlite:///./shop.db`. |
| `UPLOAD_DIR` | Where job file attachments are stored (default `./uploads`). |

## Tests
```bash
pytest
```
The core logic — Net 30 due dates, overdue computation, quote totals, and the
quote→job→invoice status flow — is covered under `tests/`. CI runs the same on
every push (`.github/workflows/ci.yml`).

## Deploy
1. Build the image: `docker build -t cnc-shop-ops .`
2. Deploy to Render / Fly / Railway. Set the env vars above on the host.
3. **Persist the `/data` volume** — it holds both the SQLite DB
   (`DATABASE_URL=sqlite:////data/shop.db`) and job file attachments
   (`UPLOAD_DIR=/data/uploads`). A single Uvicorn worker is enough.

## Backups
Daily backups + a tested restore are part of go-live (the data is the shop's
memory).
```bash
# Schedule daily (cron): safe hot copy, keeps 14 days, prunes older.
scripts/backup.sh

# Restore a copy (verifies integrity, saves the current DB aside first):
scripts/restore.sh /data/backups/shop-YYYYMMDD-HHMMSS.db.gz /data/shop.db
```
Verify a restore into a scratch path **before** relying on it in production.

## Email reminders (optional)
Set the `SMTP_*` vars in `.env` to enable the owner reminder digest (overdue and
due-soon items). With SMTP off, the **Reminders** page still previews everything
on screen. To email yourself on a schedule, run the cron entry point:
```bash
# Weekday mornings at 7am:
0 7 * * 1-5  cd /app && python scripts/send_reminders.py >> /var/log/shop-reminders.log 2>&1
```
These digests go to **you**, not customers — QuickBooks still owns invoice
sending and payment collection.

## Roadmap status
Built beyond the v1 brief: customer CSV import, reports, and owner email
reminders. Still deferred (see `HANDOFF.md` §14): live QuickBooks Online API
sync (needs your OAuth app credentials), multi-user, inventory/materials, and
partial-payment tracking.
