"""
Session Repository handling conversation sessions and turns.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import MessageModel, SessionModel
from database.repositories.base import BaseRepository


class SessionRepository(BaseRepository[SessionModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SessionModel, session)

    async def get_or_create_session(
        self, session_id: str, channel: str = "cli"
    ) -> SessionModel:
        sess = await self.get_by_id(session_id)
        now = datetime.now(timezone.utc)
        if not sess:
            sess = SessionModel(
                session_id=session_id,
                channel=channel,
                created_at=now,
                last_active_at=now,
            )
            self.session.add(sess)
        else:
            sess.last_active_at = now
        await self.session.flush()
        return sess

    async def attach_user(self, session_id: str, user_id: str) -> None:
        sess = await self.get_by_id(session_id)
        if sess:
            sess.user_id = user_id
            sess.last_active_at = datetime.now(timezone.utc)
            await self.session.flush()

    async def add_message(
        self, session_id: str, turn: int, role: str, content: str
    ) -> MessageModel:
        msg = MessageModel(
            session_id=session_id,
            turn=turn,
            role=role,
            content=content,
            timestamp=datetime.now(timezone.utc),
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def get_messages(
        self, session_id: str, limit: int = 100
    ) -> list[MessageModel]:
        stmt = (
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.turn.asc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
