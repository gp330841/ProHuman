"""Publish durable jobs and republish work that remains unfinished."""

import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from celery import Celery
from sqlalchemy import select

from packages.db.engine import get_db_context
from packages.db.models.pipeline_job import PipelineJob

logger = structlog.get_logger(__name__)


async def publish_pending_jobs(broker_url: str) -> None:
    with Celery("gateway", broker=broker_url, broker_connection_timeout=3) as celery:
        while True:
            try:
                async with get_db_context() as db:
                    now = datetime.now(timezone.utc)
                    jobs = (await db.scalars(
                        select(PipelineJob)
                        .where(
                            PipelineJob.state.in_(("queued", "dispatched")),
                            PipelineJob.available_at <= now,
                        )
                        .order_by(PipelineJob.available_at)
                        .limit(20)
                        .with_for_update(skip_locked=True)
                    )).all()
                    for job in jobs:
                        await asyncio.to_thread(
                            celery.send_task,
                            "app.tasks.execute_pipeline_job",
                            args=[str(job.id)],
                            queue=job.stage,
                            retry=False,
                        )
                        job.state = "dispatched"
                        job.available_at = now + timedelta(minutes=5)
            except Exception:
                logger.exception("pipeline_publish_failed")
            await asyncio.sleep(2)
