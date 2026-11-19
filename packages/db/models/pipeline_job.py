"""Durable stage work published to Celery from PostgreSQL."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, TimestampMixin, uuid_pk


class PipelineJob(Base, TimestampMixin):
    __tablename__ = "pipeline_jobs"
    __table_args__ = (
        UniqueConstraint("session_id", "stage", "run_key", name="uq_pipeline_stage_run"),
    )

    id: Mapped[uuid_pk]
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(20))
    run_key: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict]
    state: Mapped[str] = mapped_column(String(20), server_default="queued")
    attempts: Mapped[int] = mapped_column(server_default="0")
    available_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
