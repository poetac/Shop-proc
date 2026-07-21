"""Database engine and session helpers."""

from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./shop.db")

_is_sqlite = DATABASE_URL.startswith("sqlite")
# check_same_thread=False is required for SQLite under FastAPI's threadpool;
# timeout makes writers wait for a lock instead of erroring instantly (e.g. a
# request landing during a backup).
connect_args = {"check_same_thread": False, "timeout": 30} if _is_sqlite else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        """WAL lets readers/backups and a writer coexist; busy_timeout waits on
        locks; foreign_keys enforces referential integrity."""
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def init_db() -> None:
    """Create tables at startup. v1 uses create_all; add Alembic when the
    schema starts evolving (HANDOFF.md §5)."""
    # Import models so they register on SQLModel.metadata before create_all.
    from app import models  # noqa: F401
    from app.migrations import run_migrations

    SQLModel.metadata.create_all(engine)
    run_migrations(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""
    with Session(engine) as session:
        yield session
