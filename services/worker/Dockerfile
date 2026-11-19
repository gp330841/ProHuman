FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir build setuptools wheel

COPY services/worker/pyproject.toml /build/worker/
COPY services/worker/app /build/worker/app
COPY services/worker/app ./app
COPY packages ./packages

RUN pip install --no-cache-dir /build/worker

ENV PYTHONPATH=/app

CMD ["celery", "-A", "app.celery_app", "worker", "--loglevel=info"]
