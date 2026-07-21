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

## Running locally
```
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # then generate a password hash (see README)
uvicorn app.main:app --reload
```
Tests: `pytest -q`
