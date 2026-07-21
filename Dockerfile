FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

# SQLite DB + uploaded files live here; mount a persistent volume at /data.
ENV DATABASE_URL=sqlite:////data/shop.db \
    UPLOAD_DIR=/data/uploads
VOLUME ["/data"]

EXPOSE 8000

# Single Uvicorn worker is plenty for one user.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
