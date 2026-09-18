from __future__ import annotations

from celery import Celery
from app.config import settings

celery_app = Celery("worker")

celery_app.conf.update(
    broker_url=settings.redis_url,
    result_backend=settings.redis_url,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    task_time_limit=3600,
    task_soft_time_limit=3300,
    task_routes={
        "transcription.*": {"queue": "transcription"},
        "embedding.*": {"queue": "embedding"},
        "features.*": {"queue": "features"},
    }
)

# Import tasks to ensure they're registered
import app.tasks
