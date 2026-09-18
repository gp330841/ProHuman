from __future__ import annotations

from typing import Sequence
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from .base import BaseRepository
from ..models.session import Session, SessionStatusEnum

class SessionRepository(BaseRepository[Session]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Session)

    async def get_with_details(self, session_id: UUID) -> Session | None:
        stmt = select(Session).options(
            selectinload(Session.audio_chunks),
            selectinload(Session.transcript_segments),
            selectinload(Session.feature_results)
        ).filter_by(id=session_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_sessions(
        self, limit: int = 20, offset: int = 0, status_filter: SessionStatusEnum | None = None, device_id_filter: str | None = None
    ) -> tuple[list[Session], int]:
        stmt = select(Session)
        count_stmt = select(func.count()).select_from(Session)

        if status_filter:
            stmt = stmt.filter(Session.status == status_filter)
            count_stmt = count_stmt.filter(Session.status == status_filter)
        if device_id_filter:
            stmt = stmt.filter(Session.device_id == device_id_filter)
            count_stmt = count_stmt.filter(Session.device_id == device_id_filter)

        stmt = stmt.limit(limit).offset(offset).order_by(Session.created_at.desc())

        result = await self.session.execute(stmt)
        sessions = list(result.scalars().all())

        count_result = await self.session.execute(count_stmt)
        total_count = count_result.scalar_one()

        return sessions, total_count

    async def update_status(self, session_id: UUID, status: SessionStatusEnum) -> Session | None:
        return await self.update(session_id, status=status)
