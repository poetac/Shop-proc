# CNC Shop Ops

A minimal, single-user web app for a solo CNC machine shop to run daily
operations — customers, quotes, a jobs board, and invoice **status** tracking.
It is **operations only**: QuickBooks Online owns all accounting, tax, invoice
sending, and payment collection. The invoice records here are a lightweight
mirror tied back to QuickBooks by a `qb_reference`. See [`HANDOFF.md`](HANDOFF.md)
for the full spec and [`CLAUDE.md`](CLAUDE.md) for maintenance rules.

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
3. **Persist the SQLite volume** (the image mounts `/data`; set
   `DATABASE_URL=sqlite:////data/shop.db`). A single Uvicorn worker is enough.

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
