FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# sqlite3 CLI is needed by scripts/backup.sh and scripts/restore.sh (the slim
# image ships libsqlite3 for Python but not the command-line tool). curl is for
# the container healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends sqlite3 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the app (pyproject packages templates/static as package data).
COPY pyproject.toml README.md ./
COPY app ./app
COPY scripts ./scripts
RUN pip install --no-cache-dir .

# SQLite DB + uploaded files live here; mount a persistent volume at /data.
ENV DATABASE_URL=sqlite:////data/shop.db \
    UPLOAD_DIR=/data/uploads
VOLUME ["/data"]

# Run as a non-root user; ensure it owns the data volume.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

# Single Uvicorn worker is plenty for one user.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
