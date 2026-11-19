"""
Repository for managing recording sessions.
"""
from __future__ import annotations

from typing import Sequence
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from .base import BaseRepository
from ..models.session import Session, SessionStatusEnum

class SessionRepository(BaseRepository[Session]):
    """Repository for querying and updating audio recording sessions."""
    def __init__(
        self, session: AsyncSession, workspace_id: UUID | None = None,
        *, owner_id: str | None = None, restrict_reads: bool = False,
    ):
        super().__init__(session, Session)
        self.workspace_id = workspace_id
        self.owner_id = owner_id
        self.restrict_reads = restrict_reads

    def _scope(self, stmt, *, write: bool = False):
        if self.workspace_id is not None:
            stmt = stmt.where(Session.workspace_id == self.workspace_id)
        if self.owner_id is not None and (write or self.restrict_reads):
            stmt = stmt.where(Session.owner_id == self.owner_id)
        return stmt

    async def get_by_id(self, id: UUID) -> Session | None:
        if self.workspace_id is None:
            return await super().get_by_id(id)
        result = await self.session.execute(self._scope(select(Session).where(Session.id == id)))
        return result.scalar_one_or_none()

    async def get_for_update(self, session_id: UUID) -> Session | None:
        return await self.session.scalar(
            self._scope(select(Session).where(Session.id == session_id), write=True).with_for_update()
        )

    async def create(self, **kwargs) -> Session:
        if self.workspace_id is not None:
            kwargs["workspace_id"] = self.workspace_id
        return await super().create(**kwargs)

    async def get_with_details(self, session_id: UUID) -> Session | None:
        """
        Get a session by ID and eagerly load all its relationships
        (audio chunks, transcript segments, feature results).
        """
        stmt = select(Session).options(
            selectinload(Session.audio_chunks),
            selectinload(Session.transcript_segments),
            selectinload(Session.feature_results)
        ).filter_by(id=session_id)
        result = await self.session.execute(self._scope(stmt))
        return result.scalar_one_or_none()

    async def list_sessions(
        self,
        limit: int = 20,
        offset: int = 0,
        status_filter: SessionStatusEnum | None = None,
        device_id_filter: str | None = None,
        user_id_filter: str | None = None,
    ) -> tuple[list[Session], int]:
        """
        List sessions with optional filtering and pagination.
        
        Returns:
            A tuple of (sessions_list, total_count).
        """
        stmt = select(Session)
        count_stmt = self._scope(select(func.count()).select_from(Session))

        if status_filter:
            stmt = stmt.filter(Session.status == status_filter)
            count_stmt = count_stmt.filter(Session.status == status_filter)
        if device_id_filter:
            stmt = stmt.filter(Session.device_id == device_id_filter)
            count_stmt = count_stmt.filter(Session.device_id == device_id_filter)
        if user_id_filter:
            stmt = stmt.filter(Session.owner_id == user_id_filter)
            count_stmt = count_stmt.filter(Session.owner_id == user_id_filter)

        stmt = stmt.limit(limit).offset(offset).order_by(Session.created_at.desc())

        result = await self.session.execute(self._scope(stmt))
        sessions = list(result.scalars().all())

        count_result = await self.session.execute(count_stmt)
        total_count = count_result.scalar_one()

        return sessions, total_count

    async def update_status(self, session_id: UUID, status: SessionStatusEnum) -> Session | None:
        """
        Update the status of a specific session.
        """
        return await self.update(session_id, status=status)
