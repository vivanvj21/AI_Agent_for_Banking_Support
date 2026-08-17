"""
Memory Repository handling long-term, turn, and profile memory storage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import MemoryEntryModel, UserProfileModel
from database.repositories.base import BaseRepository


class MemoryRepository(BaseRepository[MemoryEntryModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(MemoryEntryModel, session)

    async def store_memory(
        self,
        memory_id: str,
        memory_type: str,
        content: str,
        user_id: str | None = None,
        session_id: str | None = None,
        role: str | None = None,
        importance: float = 0.5,
        metadata_json: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
    ) -> MemoryEntryModel:
        now = datetime.now(timezone.utc)
        entry = MemoryEntryModel(
            memory_id=memory_id,
            user_id=user_id,
            session_id=session_id,
            memory_type=memory_type,
            content=content,
            role=role,
            importance=importance,
            recency_score=1.0,
            relevance_score=0.0,
            metadata_json=metadata_json or {},
            created_at=now,
            last_accessed_at=now,
            expires_at=expires_at,
            is_deleted=0,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_user_long_term_memories(
        self, user_id: str, limit: int = 50
    ) -> list[MemoryEntryModel]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(MemoryEntryModel)
            .where(
                MemoryEntryModel.user_id == user_id,
                MemoryEntryModel.memory_type == "long_term",
                MemoryEntryModel.is_deleted == 0,
                (MemoryEntryModel.expires_at.is_(None))
                | (MemoryEntryModel.expires_at > now),
            )
            .order_by(
                MemoryEntryModel.importance.desc(), MemoryEntryModel.created_at.desc()
            )
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_session_conversation_turns(
        self, session_id: str, limit: int = 50
    ) -> list[MemoryEntryModel]:
        stmt = (
            select(MemoryEntryModel)
            .where(
                MemoryEntryModel.session_id == session_id,
                MemoryEntryModel.memory_type == "conversation",
                MemoryEntryModel.is_deleted == 0,
            )
            .order_by(MemoryEntryModel.created_at.asc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def upsert_user_profile(
        self, user_id: str, preferences: dict[str, Any], facts: list[str]
    ) -> UserProfileModel:
        stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
        res = await self.session.execute(stmt)
        prof = res.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if prof:
            prof.preferences.update(preferences)
            # Deduplicate facts
            existing_facts = list(dict.fromkeys(prof.facts + facts))
            prof.facts = existing_facts
            prof.updated_at = now
        else:
            prof = UserProfileModel(
                user_id=user_id,
                preferences=preferences,
                facts=facts,
                updated_at=now,
            )
            self.session.add(prof)
        await self.session.flush()
        return prof

    async def get_user_profile(self, user_id: str) -> dict[str, Any]:
        stmt = select(UserProfileModel).where(UserProfileModel.user_id == user_id)
        res = await self.session.execute(stmt)
        prof = res.scalar_one_or_none()
        if not prof:
            return {"preferences": {}, "facts": []}
        return {"preferences": prof.preferences, "facts": prof.facts}
