"""Database engine and session helpers."""

from __future__ import annotations

import os
from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./shop.db")

# check_same_thread=False is required for SQLite under FastAPI's threadpool.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


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
