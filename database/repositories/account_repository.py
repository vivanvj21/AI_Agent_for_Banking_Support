"""
Account Repository handling account balances (in integer minor units / paise).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AccountModel
from database.repositories.base import BaseRepository


class AccountRepository(BaseRepository[AccountModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AccountModel, session)

    async def get_by_user_id(self, user_id: str) -> list[AccountModel]:
        stmt = select(AccountModel).where(
            AccountModel.user_id == user_id, AccountModel.is_active == 1
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_user_account(
        self, user_id: str, account_id: str
    ) -> AccountModel | None:
        stmt = select(AccountModel).where(
            AccountModel.account_id == account_id,
            AccountModel.user_id == user_id,
            AccountModel.is_active == 1,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()
