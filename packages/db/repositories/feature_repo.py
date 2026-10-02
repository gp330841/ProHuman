"""
Repository for managing extracted AI features.
"""
from __future__ import annotations

from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from .base import BaseRepository
from ..models.feature_result import FeatureResultModel

class FeatureRepository(BaseRepository[FeatureResultModel]):
    """Repository for querying and persisting feature results."""
    def __init__(self, session: AsyncSession):
        super().__init__(session, FeatureResultModel)

    async def get_by_session_and_name(self, session_id: UUID, feature_name: str, version: int | None = None) -> FeatureResultModel | None:
        """
        Get a specific feature result for a session.
        If version is not provided, returns the latest version.
        """
        stmt = select(FeatureResultModel).filter_by(session_id=session_id, feature_name=feature_name)
        if version is not None:
            stmt = stmt.filter_by(version=version)
        else:
            stmt = stmt.order_by(FeatureResultModel.version.desc())
        
        result = await self.session.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def get_latest_version(self, session_id: UUID, feature_name: str) -> int:
        """
        Get the highest version number for a given feature in a session.
        Returns 0 if no features exist.
        """
        stmt = select(func.max(FeatureResultModel.version)).filter_by(
            session_id=session_id, feature_name=feature_name
        )
        result = await self.session.execute(stmt)
        max_version = result.scalar_one_or_none()
        return max_version or 0

    async def list_by_session(self, session_id: UUID) -> list[FeatureResultModel]:
        """
        List all feature results associated with a session, ordered by name.
        """
        stmt = select(FeatureResultModel).filter_by(session_id=session_id).order_by(FeatureResultModel.feature_name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
