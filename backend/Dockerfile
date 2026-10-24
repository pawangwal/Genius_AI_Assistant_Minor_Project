# Multi-stage production container for Genius AI Assistant FastAPI backend
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final Runtime Image
FROM python:3.12-slim

WORKDIR /app

# Create non-root user
RUN groupadd -g 1000 genius && \
    useradd -u 1000 -g genius -s /bin/bash -m genius

# Copy installed wheels from builder
COPY --from=builder /install /usr/local

# Copy application code and model artifacts
COPY --chown=genius:genius backend/ /app/backend/
COPY --chown=genius:genius pipe.pkl /app/pipe.pkl
COPY --chown=genius:genius pytest.ini /app/pytest.ini

USER genius

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live')" || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
