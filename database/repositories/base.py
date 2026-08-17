"""
Generic Async Base Repository providing CRUD, pagination, and transaction safety.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic async repository for SQLAlchemy models."""

    def __init__(self, model: type[ModelT], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get_by_id(self, ident: Any) -> ModelT | None:
        """Fetch a single record by primary key."""
        return await self.session.get(self.model, ident)

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[ModelT]:
        """List all records with pagination."""
        stmt = select(self.model).limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def create(self, instance: ModelT) -> ModelT:
        """Add and flush a new record."""
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(self, instance: ModelT) -> ModelT:
        """Merge and flush an updated record."""
        merged = await self.session.merge(instance)
        await self.session.flush()
        return merged

    async def delete_by_id(self, ident: Any) -> bool:
        """Delete a record by primary key."""
        instance = await self.get_by_id(ident)
        if instance is not None:
            await self.session.delete(instance)
            await self.session.flush()
            return True
        return False

    async def count(self) -> int:
        """Return total row count for table."""
        stmt = select(func.count()).select_from(self.model)
        res = await self.session.execute(stmt)
        return res.scalar_one()
