# CNC Shop Ops Tool — Build-Ready Handoff

*A complete scoping + build brief for a future development session working from a GitHub repository. Owner: a solo CNC machine shop. Goal: a minimal, tailored operations tool — not a full ERP. Maintained by future AI (Claude) sessions.*

---

## 0. How to Use This Document

Self-contained brief. A future session should read it top to bottom and start building with little to no back-and-forth. Every scoping decision is already made (§2). Where a choice was open, a sensible default is stated and marked adjustable. This file should live in the repo as `HANDOFF.md`.

**Ready-to-paste kickoff prompt for the build session:**

> This repository is v1 of a solo CNC machine shop operations tool. Read `HANDOFF.md` and `CLAUDE.md` in full before writing any code. Hard constraints: single-user web app; **operations-only** — QuickBooks owns all accounting, tax, invoice sending, and payment collection, so never build accounting/tax logic or an invoice generator; start **fresh** (no data import); use the locked stack and data model exactly as written. First, scaffold the project per the repo structure in §7 and confirm it runs. Then create GitHub issues from the list in §13 and work them in order, writing the tests named in §11 as you go and keeping CI green. Pause at the end of each module to check it against that module's acceptance criteria (§8).

---

## 1. Context & Guiding Principles

Solo CNC machine shop, early-stage with a small but **growing** client base. Today the business runs on spreadsheets, paper/whiteboard, and a barely-configured QuickBooks account. The owner has limited business/accounting background and wants a lightweight tool to stay organized as the shop scales, without the cost and bloat of a real ERP.

**Guiding principles for every decision:**
- **Minimal over complete.** Smallest change that removes real friction. Fewer features, done cleanly.
- **Operations, not accounting.** The app tracks the work; QuickBooks tracks the money. Never blur that line.
- **Single user, low volume.** ~1–5 concurrent jobs, one operator. Optimize for clarity and speed.
- **The data is the shop's memory.** Reliability and backups beat features.
- **Built for AI maintenance.** Future Claude sessions extend this. Favor clear structure, plain code, and tests as a safety net over cleverness.
- **Leave room to grow** (§14) without building for it now.

---

## 2. Decision Log — Confirmed

Settled. Do not re-open without the owner's say-so.

| # | Decision | Confirmed choice |
|---|---|---|
| 1 | Overall approach | Minimal custom tool, not a full ERP |
| 2 | Accounting / tax / books | **QuickBooks owns it.** App does no accounting or tax logic |
| 3 | QuickBooks edition | **QuickBooks Online** (owner to finalize with a bookkeeper) |
| 4 | Quoting | **Store-only** — owner types line items & prices; no costing engine |
| 5 | Invoicing | **Status tracking only** — QuickBooks generates/sends; app keeps a lightweight redundant record |
| 6 | Payment collection | In QuickBooks (QuickBooks Payments: card/ACH). Not in the app |
| 7 | Payment terms | **Net 30** default (adjustable per invoice) |
| 8 | Deployment | Cloud-hosted single-user web app + automated daily backups |
| 9 | Data at launch | **Start fresh** — no spreadsheet import in v1 |
| 10 | Job status flow | Accepted → Materials → In Queue → Machining → Finishing/QC → Done → Invoiced → Paid |
| 11 | Job file attachments | Nice-to-have, low priority (drawings/prints/PDF/STEP) |
| 12 | **Tech stack** | **Python 3.12 · FastAPI · Jinja2 + HTMX · Pico.css · SQLite (SQLModel) · session auth** |
| 13 | **Maintainer** | **Future Claude sessions** (repo optimized for this) |
| 14 | **Quality bar** | **Lean but real** — focused tests on core logic + GitHub Actions CI |
| 15 | Live QuickBooks API sync | Deferred to v2+ |
| 16 | Multi-user / inventory / reporting | Deferred to v2+ |

---

## 3. Glossary (for a session new to the domain)

- **CNC** — Computer Numerical Control machining; the shop makes machined parts from digital designs.
- **Quote** — a price estimate sent to a customer for potential work.
- **Job** — accepted work moving through production.
- **Net 30** — payment due 30 days after the invoice is issued.
- **ACH** — bank-to-bank electronic payment (vs. a card).
- **QuickBooks / QuickBooks Payments** — the accounting software (and its card/ACH feature) that owns the books.
- **Receivables / Outstanding** — money invoiced but not yet paid.
- **Overdue** — an unpaid invoice past its due date.
- **Print / Drawing** — engineering drawing (often PDF) specifying a part. **STEP** — a common 3D CAD file format.

---

## 4. Goals & Non-Goals

**Goals (v1)**
- One place to run daily operations, replacing the whiteboard + spreadsheet sprawl.
- Track a job's full lifecycle: quote → accepted → in production → invoiced → paid.
- Keep clean records that make QuickBooks entry and tax time painless.

**Non-Goals (do NOT build)**
- Any accounting, tax calculation, expense categorization, or bookkeeping. QuickBooks owns this.
- Invoice generation/sending or payment processing. QuickBooks owns this; the app only mirrors status.
- Cost estimating / quoting math. The owner prices work externally and types the result in.
- Payroll, inventory/materials, multi-user, reporting suites. Later, if ever.

---

## 5. Tech Stack (locked) & Rationale

- **Language:** Python 3.12+
- **Web framework:** FastAPI (with Uvicorn)
- **UI:** Jinja2 server-rendered templates + **HTMX** for interactivity (moving jobs between stages, inline updates) — no single-page-app machinery
- **CSS:** **Pico.css** (classless, tiny, responsive out of the box; the job board must be usable on a phone). *(Swap for Tailwind only if more visual control is wanted.)*
- **Data:** **SQLite** via **SQLModel** (SQLAlchemy + Pydantic). One-file DB, trivial to back up, Postgres-migratable later. v1 can create tables at startup; add Alembic migrations when the schema starts evolving.
- **Auth:** single-user, session-based login with a bcrypt-hashed password (passlib). Credentials/secret via env vars.
- **Packaging/deploy:** `pyproject.toml`, one `Dockerfile`, deploy to Render / Fly / Railway.

**Why this stack:** it's a single language with minimal moving parts (no separate frontend build, no API/client split to keep in sync), trivial to host and back up, and — critically, since **future Claude sessions maintain it** — it's the kind of common, readable code an AI session writes and extends most reliably. HTMX delivers a dynamic, mobile-friendly board without the overhead of React.

**Caveat to confirm before building:** if shop internet is unreliable, revisit a local-first/offline design with sync instead of pure cloud.

---

## 6. QuickBooks & Compliance — Division of Labor

The owner wants help staying tax-compliant despite limited accounting knowledge. The responsible approach (which also keeps the build small): **the app never touches taxes; QuickBooks does.**

| Layer | Owner | Responsible for |
|---|---|---|
| Operations | **This app** | Customers, quotes, jobs, invoice **status** tracking |
| Books & compliance | **QuickBooks Online** | Income/expense categorization, sales tax, reports, accountant hand-off, invoice **sending** + card/ACH **collection** |
| Expert oversight | **A bookkeeper/accountant** | One-time QuickBooks setup + periodic review |

**Relay to the owner (not accounting/legal advice — confirm with a professional):** use QuickBooks Online; spend a few hours with a bookkeeper to set it up once (chart of accounts, sales-tax settings if applicable, bank/card feeds). After that, staying compliant is mostly "keep records clean," which the app + QuickBooks make easy. The app's invoice is a convenience **mirror — never the source of truth for money**; the `qb_reference` field ties each record back to its QuickBooks invoice.

---

## 7. Repository Structure

Suggested tree (`HANDOFF.md` and `CLAUDE.md` at the root so any session finds them immediately):

```
cnc-shop-ops/
├── README.md
├── CLAUDE.md                 # rules & orientation for AI sessions (see §9)
├── HANDOFF.md                # this document
├── .gitignore
├── .env.example
├── pyproject.toml
├── Dockerfile
├── .github/workflows/ci.yml
├── app/
│   ├── main.py               # FastAPI app, startup (create tables), route mounting
│   ├── db.py                 # engine + session
│   ├── models.py             # SQLModel entities (§10)
│   ├── auth.py               # single-user session login
│   ├── logic/                # PURE functions — the tested core (§11)
│   │   ├── invoicing.py      #   due-date (Net 30), overdue check
│   │   ├── quoting.py        #   quote totals
│   │   └── jobs.py           #   status-transition rules
│   ├── routes/
│   │   ├── customers.py
│   │   ├── quotes.py
│   │   ├── jobs.py
│   │   ├── invoices.py
│   │   └── dashboard.py
│   ├── templates/            # base.html + per-module pages + HTMX partials
│   └── static/
└── tests/
    ├── test_invoicing.py
    ├── test_quoting.py
    └── test_jobs.py
```

**`.gitignore` essentials**
```
__pycache__/
*.pyc
.venv/
venv/
*.db
*.sqlite3
.env
.DS_Store
```

**`.env.example`**
```
SECRET_KEY=change-me
APP_USERNAME=owner
APP_PASSWORD_HASH=            # bcrypt hash of your chosen password
DATABASE_URL=sqlite:///./shop.db
```

**`README.md`** should cover, briefly: what the app is (one paragraph, pointing to `HANDOFF.md`), local setup (`python -m venv .venv`, install, copy `.env.example` → `.env`, generate a password hash, `uvicorn app.main:app --reload`), how to run tests (`pytest`), and how to deploy (build the Docker image, set env vars on the host, persist the SQLite volume, schedule the backup).

---

## 8. Modules — Detailed Specs & Acceptance Criteria

### 8.1 Customers
The address book everything hangs off of. Fields: name, company, email, phone, billing address, notes, created date. List with search; detail page shows the customer's quotes, jobs, invoices.
**Done when:** create/edit/delete + search work; related records visible from the detail page.

### 8.2 Quotes
Capture estimates the owner already priced. Create with customer + line items (**description, qty, unit price** — typed) + notes; total auto-sums. Status: **Draft → Sent → Accepted / Declined**. **Convert accepted → Job** in one click (carries customer + lines/price). *(Nice-to-have)* PDF export.
**Done when:** multi-line quote with auto total; status transitions; accepting creates a linked, pre-filled job.

### 8.3 Jobs — core module (whiteboard replacement)
Created from an accepted quote (or manually). Fields: linked customer, linked quote, title/part, due date, status, notes, created date. **Kanban board** using the confirmed flow. Advancing a job is quick (tap-to-move controls on each card; drag optional via SortableJS). The last two stages are **driven by the linked invoice** (§9). *(Nice-to-have, low priority)* file attachments.
**Done when:** jobs grouped by stage on a board; moving stages persists; job links back to customer and quote.

### 8.4 Invoices — status mirror (lightweight, NOT a generator)
Created from a job (usually at *Done*). Fields: linked job + customer, **amount** (defaults from quote total, editable), issue date, **due date** (auto = issue + 30 days), status, payment method (card/ACH), paid date, optional **qb_reference** (the QuickBooks invoice #), notes. Status: **Draft → Sent → Paid**. **Overdue is computed, not stored** (Sent + past due + unpaid) and shown as a flag. Receivables view with outstanding + overdue totals.
**Done when:** create from a job; Net 30 due date auto-calculates; transitions persist; overdue flagged; receivables total shown. Never generates or sends an actual invoice.

### 8.5 Dashboard / Home
Default widgets (adjustable): total **outstanding** receivables; **overdue** invoices; **active jobs** count; **jobs due within 7 days**; **quotes in "Sent"** awaiting a response. Each links to its list.

### 8.6 Settings
Business info (name/address for reference), numbering preferences, Net 30 default. Minimal.

---

## 9. CLAUDE.md — Contents for the Repo

Drop this at the repo root so every future AI session gets the rules automatically:

```
# CLAUDE.md — Guide for AI sessions

This repo is the operations tool for a solo CNC machine shop. Read HANDOFF.md (full spec) before changing anything.

## What it is
A minimal, single-user web app tracking the shop's work: customers, quotes, jobs (a status board), and invoice status. Operations only.

## Hard rules
- Operations only. QuickBooks owns all accounting, tax, invoice sending, and payment collection. Never add accounting/tax logic or an invoice generator/sender. The Invoice model is a status mirror of QuickBooks — never the source of truth for money.
- Keep it minimal. Smallest change that solves the problem. ~1–5 concurrent jobs; do not over-engineer.
- Single user. No multi-user/roles unless explicitly asked.

## Stack
Python 3.12, FastAPI, Jinja2 + HTMX, Pico.css, SQLite via SQLModel, session auth, Uvicorn.

## Working conventions
- Run `pytest` before and after changes; keep CI green.
- Keep core logic covered: Net 30 due dates, quote totals, invoice<->job status transitions, overdue computation. Put that logic in app/logic/ as pure functions.
- Secrets come from env vars (.env.example). Never commit secrets or the SQLite DB.
- Small, focused commits referencing the issue number.

## Where things live
app/models.py (entities) · app/routes/ (one router per module) · app/templates/ (Jinja + HTMX partials) · app/logic/ (tested pure logic) · tests/ (pytest).
```

---

## 10. Data Model

Types indicative (SQLModel entities).

- **Customer** (id, name, company, email, phone, billing_address, notes, created_at)
- **Quote** (id, customer_id, quote_number, status, notes, created_at)
  - **QuoteLine** (id, quote_id, description, qty, unit_price)
- **Job** (id, customer_id, quote_id, job_number, title, due_date, status, notes, created_at)
  - **JobFile** (id, job_id, filename, url) — *nice-to-have*
- **Invoice** (id, job_id, customer_id, amount, issue_date, due_date, status, payment_method, paid_date, qb_reference, notes)

**Notes:** No `InvoiceLine` or `Payment` tables in v1 — the invoice is a single-amount status mirror; line detail lives in the Quote/Job. Add a `Payment` table in v2 only if partial payments are needed. Quote total = sum of its lines. **Relationships:** Customer 1—* Quotes/Jobs/Invoices · Quote 1—1 Job (on acceptance) · Job 1—1 Invoice (typical).

---

## 11. State Machines & the Tests That Guard Them

**Quote:** `Draft → Sent → Accepted | Declined` — accepting creates a pre-filled Job.
**Job:** `Accepted → Materials → In Queue → Machining → Finishing/QC → Done → Invoiced → Paid` — manual up to *Done*; *Invoiced* set when an Invoice is created; *Paid* set when that Invoice is marked Paid.
**Invoice:** `Draft → Sent → Paid` — **Overdue** is a computed display flag (Sent + today > due_date + unpaid), not a stored status. Marking Paid records `paid_date` and moves the linked job to *Paid*.

**Required tests (the lean core net):**
- `test_invoicing`: due_date = issue_date + 30 days; overdue is true only when Sent + past due + unpaid.
- `test_quoting`: quote total equals the sum of its line items.
- `test_jobs`: accepting a quote creates a job at *Accepted*; creating an invoice moves the job to *Invoiced*; marking the invoice Paid moves the job to *Paid*.

---

## 12. Defaults, Conventions & Config

- **Currency:** USD. **Mobile:** the UI (especially the board) must be usable on a phone.
- **Numbering (auto, adjustable):** Quotes `Q-YYYY-NNN`, Jobs `J-YYYY-NNN`, Invoices `INV-YYYY-NNN` (+ `qb_reference` for the QuickBooks number). Counters reset each calendar year.
- **Terms:** Net 30 default; `due_date = issue_date + 30 days`; terms editable per invoice.
- **Flags (visual only in v1):** overdue = red, due-soon (≤7 days) = amber. Email reminders → v2.
- **Environment variables:** `SECRET_KEY`, `APP_USERNAME`, `APP_PASSWORD_HASH`, `DATABASE_URL`. Secrets are never committed; the SQLite DB is gitignored.
- **CI (`.github/workflows/ci.yml`):**
```
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: pytest -q
```
- **Deployment:** build the Docker image, deploy to Render/Fly/Railway, set env vars on the host, **persist the SQLite volume**, and schedule the daily backup (and verify a restore before go-live). A single Uvicorn worker is fine for one user.

---

## 13. Suggested GitHub Issues (map 1:1 to build order)

1. **Project skeleton** — FastAPI app, SQLite/SQLModel, `base.html` + Pico.css, single-user auth, `Dockerfile`, CI workflow. *(Acceptance: app runs locally and CI is green.)*
2. **Backups** — automated daily SQLite backup + a documented, tested restore.
3. **Customers** — model, CRUD, list/search, detail page + tests.
4. **Quotes** — model + lines, CRUD, auto-total, statuses, convert-to-job + tests.
5. **Jobs board** — model, kanban columns, tap-to-move stages, job detail, quote link + tests.
6. **Invoices** — model, create-from-job, Net 30 due date, status mirror, overdue flag, receivables list + tests.
7. **Dashboard** — outstanding, overdue, active jobs, due-soon, quotes-awaiting widgets.
8. **Polish** — due-soon/overdue styling, settings/numbering, optional job file attachments.

A future session can create these issues directly from this list, then work them in order.

---

## 14. Future Roadmap (v2+)

Architected for, out of scope now: live **QuickBooks Online API** sync (push invoices, pull payment status); email reminders (overdue, due-soon); simple reporting (revenue by month/customer, quote win rate); CSV import; inventory/materials, multi-user, partial-payment tracking — only if the shop grows into them.

---

## 15. Risks & Things to Watch

- **Scope creep into accounting** — the biggest temptation. Hold the line: QuickBooks owns the money.
- **Invoice record drifting from QuickBooks** — it's a convenience mirror; QuickBooks is the source of truth. `qb_reference` reconciles them.
- **Backups never tested** — configure *and* verify a restore before go-live.
- **Outgrowing the assumptions** — past ~5 concurrent jobs or the first employee, revisit SQLite→Postgres and multi-user.
- **Shop internet reliability** (§5) — confirm before committing to pure cloud.
