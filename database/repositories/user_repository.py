"""
User Repository handling User authentication, failed attempts, and lockouts.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import UserModel
from database.repositories.base import BaseRepository


class UserRepository(BaseRepository[UserModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(UserModel, session)

    async def get_by_email(self, email: str) -> UserModel | None:
        stmt = select(UserModel).where(UserModel.email == email)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def increment_failed_attempts(
        self, user_id: str, max_attempts: int = 5, lockout_minutes: int = 15
    ) -> UserModel:
        user = await self.get_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        user.failed_attempts += 1
        if user.failed_attempts >= max_attempts:
            user.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=lockout_minutes
            )

        await self.session.flush()
        return user

    async def reset_failed_attempts(self, user_id: str) -> UserModel:
        user = await self.get_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        user.failed_attempts = 0
        user.locked_until = None
        await self.session.flush()
        return user
