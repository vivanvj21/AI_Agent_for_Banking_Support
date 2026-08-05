"""
Transaction Repository handling transaction history and fraud flagging.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AccountModel, TransactionModel
from database.repositories.base import BaseRepository


class TransactionRepository(BaseRepository[TransactionModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(TransactionModel, session)

    async def get_user_transactions(self, user_id: str, limit: int = 50) -> List[TransactionModel]:
        stmt = (
            select(TransactionModel)
            .join(AccountModel, TransactionModel.account_id == AccountModel.account_id)
            .where(AccountModel.user_id == user_id)
            .order_by(TransactionModel.timestamp.desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_user_transaction_by_id(self, user_id: str, transaction_id: str) -> Optional[TransactionModel]:
        stmt = (
            select(TransactionModel)
            .join(AccountModel, TransactionModel.account_id == AccountModel.account_id)
            .where(TransactionModel.transaction_id == transaction_id, AccountModel.user_id == user_id)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def flag_fraud(self, transaction_id: str) -> bool:
        txn = await self.get_by_id(transaction_id)
        if txn:
            txn.flagged_fraud = 1
            await self.session.flush()
            return True
        return False
