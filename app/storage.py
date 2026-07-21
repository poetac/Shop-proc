"""Local file storage for job attachments (HANDOFF.md §8.3).

Files are written under UPLOAD_DIR (a persistent volume in production). Names
are made safe and unique so uploads never collide or escape the directory.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))

# Attachments are drawings/prints/CAD — keep the allow-list tight but useful.
ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif",
    ".step", ".stp", ".stl", ".dxf", ".dwg",
    ".txt", ".csv", ".zip",
}
MAX_BYTES = 25 * 1024 * 1024  # 25 MB per file


def _safe_stem(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    return stem or "file"


def is_allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def save_upload(job_id: int, filename: str, data: bytes) -> str:
    """Write bytes to disk and return the stored path relative to UPLOAD_DIR."""
    ext = Path(filename).suffix.lower()
    unique = f"{_safe_stem(filename)}-{uuid.uuid4().hex[:8]}{ext}"
    rel = Path(str(job_id)) / unique
    dest = UPLOAD_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return str(rel)


def absolute_path(stored_path: str) -> Path:
    """Resolve a stored path back to an absolute path, guarding against escapes."""
    base = UPLOAD_DIR.resolve()
    full = (UPLOAD_DIR / stored_path).resolve()
    if not full.is_relative_to(base):
        raise ValueError("path escapes upload directory")
    return full


def delete_file(stored_path: str) -> None:
    try:
        absolute_path(stored_path).unlink(missing_ok=True)
    except (ValueError, OSError):
        pass
