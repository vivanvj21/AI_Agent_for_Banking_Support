"""
Card Repository handling card status updates (active, locked, reported_lost).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AccountModel, CardModel
from database.repositories.base import BaseRepository


class CardRepository(BaseRepository[CardModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(CardModel, session)

    async def get_user_card(self, user_id: str, card_id: str) -> CardModel | None:
        stmt = (
            select(CardModel)
            .join(AccountModel, CardModel.account_id == AccountModel.account_id)
            .where(CardModel.card_id == card_id, AccountModel.user_id == user_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_user_cards(self, user_id: str) -> list[CardModel]:
        stmt = (
            select(CardModel)
            .join(AccountModel, CardModel.account_id == AccountModel.account_id)
            .where(AccountModel.user_id == user_id)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def update_status(self, card_id: str, new_status: str) -> bool:
        card = await self.get_by_id(card_id)
        if card:
            card.status = new_status
            await self.session.flush()
            return True
        return False
