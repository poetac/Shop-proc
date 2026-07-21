"""Test fixtures. Sets env (temp DB + credentials) before importing the app."""

import os
import tempfile

from passlib.context import CryptContext

# Must be set BEFORE importing the app: db.py and auth.py read env at import.
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="uploads-")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ["APP_USERNAME"] = "owner"
os.environ["APP_PASSWORD_HASH"] = CryptContext(schemes=["bcrypt"]).hash("test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client():
    """A logged-in TestClient against a fresh temp database."""
    from app.db import engine
    from app.main import app
    from sqlmodel import SQLModel

    # Clean slate for each test.
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    with TestClient(app) as c:
        resp = c.post("/login", data={"username": "owner", "password": "test"})
        assert resp.status_code == 200  # redirect followed to dashboard
        yield c
