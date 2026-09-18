from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from .session import Session

class FeatureResultModel(Base, TimestampMixin):
    __tablename__ = "feature_results"
    __table_args__ = (
        UniqueConstraint("session_id", "feature_name", "version", name="uq_feature_session_name_version"),
    )

    id: Mapped[uuid_pk]
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    feature_name: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[int] = mapped_column(default=1)
    data: Mapped[dict] = mapped_column(JSONB)
    processing_time_ms: Mapped[int | None]
    provider_model: Mapped[str | None] = mapped_column(String(100))

    session: Mapped["Session"] = relationship(back_populates="feature_results")
