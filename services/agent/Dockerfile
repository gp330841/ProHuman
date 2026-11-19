FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir build setuptools wheel

COPY services/agent/pyproject.toml /build/agent/
COPY services/agent/app /build/agent/app
COPY services/agent/app ./app
COPY packages ./packages

RUN pip install --no-cache-dir /build/agent

ENV PYTHONPATH=/app

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
