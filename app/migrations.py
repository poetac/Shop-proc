"""Tiny, idempotent SQLite migrations.

v1 creates tables at startup with SQLModel's create_all, which adds *new tables*
but never new *columns* on existing ones. As the schema evolves we add nullable
columns here with `ALTER TABLE ... ADD COLUMN`, guarded by a column check so it
is safe to run on every startup. This keeps redeploys over an existing /data
volume from crashing with "no such column".

If the schema ever grows complex (renames, constraints, data backfills), replace
this with Alembic (see HANDOFF.md §5).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

# (table, column, SQL type) — all must be nullable / have a sensible default.
_COLUMNS: list[tuple[str, str, str]] = [
    ("quote", "production_notes", "TEXT"),
    ("job", "production_notes", "TEXT"),
    ("invoice", "last_reminded_at", "TEXT"),
]

# (index_name, table, column) unique indexes — backstops for numbering and the
# one-invoice-per-job invariant. CREATE UNIQUE INDEX IF NOT EXISTS is idempotent
# and will fail loudly only if existing data already contains duplicates (which
# the owner would want to know about before it bites).
_UNIQUE_INDEXES: list[tuple[str, str, str]] = [
    ("ux_quote_number", "quote", "quote_number"),
    ("ux_job_number", "job", "job_number"),
    ("ux_invoice_number", "invoice", "invoice_number"),
    ("ux_invoice_job_id", "invoice", "job_id"),
]


def _existing_columns(conn, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def run_migrations(engine: Engine) -> None:
    """Add any missing columns. Only runs for SQLite; a no-op otherwise."""
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        for table, column, sqltype in _COLUMNS:
            # Skip tables that don't exist yet (create_all handles those).
            if not conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
                {"t": table},
            ).fetchone():
                continue
            if column not in _existing_columns(conn, table):
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sqltype}"))

        for index_name, table, column in _UNIQUE_INDEXES:
            if not conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
                {"t": table},
            ).fetchone():
                continue
            conn.execute(
                text(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} "
                    f"ON {table} ({column})"
                )
            )
