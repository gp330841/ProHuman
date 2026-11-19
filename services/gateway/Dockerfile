FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir build setuptools wheel

COPY services/gateway/pyproject.toml /build/gateway/
COPY services/gateway/app /build/gateway/app
COPY services/gateway/app ./app
COPY packages ./packages

RUN pip install --no-cache-dir /build/gateway alembic

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
