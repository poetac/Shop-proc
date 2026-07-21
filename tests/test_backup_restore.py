"""Backup -> restore round-trip (HANDOFF.md §13/§15 — a *tested* restore).

Exercises scripts/backup.sh and scripts/restore.sh end to end, including the
uploaded-files archive. Skips automatically where the sqlite3 CLI isn't present
(it is on GitHub's ubuntu runners and in the Docker image).
"""

import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("sqlite3") is None, reason="sqlite3 CLI not installed"
)

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _rows(db: Path) -> list:
    con = sqlite3.connect(db)
    try:
        return con.execute("SELECT id, name FROM customer ORDER BY id").fetchall()
    finally:
        con.close()


def test_backup_then_restore_roundtrip_db_and_uploads(tmp_path):
    data = tmp_path / "data"
    backups = data / "backups"
    uploads = data / "uploads"
    uploads.mkdir(parents=True)
    db = data / "shop.db"

    # Seed a DB and an uploaded file.
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE customer (id INTEGER PRIMARY KEY, name TEXT)")
    con.execute("INSERT INTO customer (name) VALUES ('Acme'), ('Globex')")
    con.commit()
    con.close()
    (uploads / "1").mkdir()
    (uploads / "1" / "drawing.pdf").write_bytes(b"%PDF-1.4 original")

    env = {
        "DB_PATH": str(db),
        "BACKUP_DIR": str(backups),
        "UPLOAD_DIR": str(uploads),
        "PATH": __import__("os").environ["PATH"],
    }
    subprocess.run(["bash", str(SCRIPTS / "backup.sh")], check=True, env=env)

    db_backup = next(backups.glob("shop-*.db.gz"))
    uploads_backup = next(backups.glob("uploads-*.tgz"))

    # Simulate data loss: wipe the DB and the uploaded file.
    db.unlink()
    shutil.rmtree(uploads)

    subprocess.run(
        [
            "bash", str(SCRIPTS / "restore.sh"),
            str(db_backup), str(db), str(uploads_backup), str(data),
        ],
        check=True,
        env=env,
    )

    assert _rows(db) == [(1, "Acme"), (2, "Globex")]
    assert (uploads / "1" / "drawing.pdf").read_bytes() == b"%PDF-1.4 original"
