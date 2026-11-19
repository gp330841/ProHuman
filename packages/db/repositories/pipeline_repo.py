"""Create stage jobs in the same transaction as their source data."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.pipeline_job import PipelineJob

async def enqueue_stage(
    db: AsyncSession, session_id: UUID, stage: str, *, run_key: str = "initial", **payload
) -> None:
    stmt = insert(PipelineJob).values(
        session_id=session_id, stage=stage, run_key=run_key, payload=payload
    )
    await db.execute(stmt.on_conflict_do_nothing(constraint="uq_pipeline_stage_run"))


async def stage_statuses(db: AsyncSession, session_id: UUID) -> dict[str, str]:
    result = await db.execute(
        select(PipelineJob.stage, PipelineJob.state)
        .where(PipelineJob.session_id == session_id)
        .distinct(PipelineJob.stage)
        .order_by(PipelineJob.stage, PipelineJob.created_at.desc(), PipelineJob.id.desc())
    )
    return dict(result.tuples().all())
