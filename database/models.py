"""
SQLAlchemy Declarative Base and ORM Models for PostgreSQL (with pgvector support).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import (
    BIGINT,
    BOOLEAN,
    FLOAT,
    INTEGER,
    TEXT,
    VARCHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

try:
    from pgvector.sqlalchemy import Vector
    _PGVECTOR_AVAILABLE = True
except ImportError:
    _PGVECTOR_AVAILABLE = False


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""
    pass


class UserModel(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(VARCHAR(50), primary_key=True)
    first_name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    last_name: Mapped[str] = mapped_column(VARCHAR(100), nullable=False)
    email: Mapped[str] = mapped_column(VARCHAR(255), unique=True, nullable=False)
    pin_hash: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    failed_attempts: Mapped[int] = mapped_column(INTEGER, nullable=False, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    accounts: Mapped[List["AccountModel"]] = relationship("AccountModel", back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[List["SessionModel"]] = relationship("SessionModel", back_populates="user", cascade="all, delete-orphan")


class AccountModel(Base):
    __tablename__ = "accounts"

    account_id: Mapped[str] = mapped_column(VARCHAR(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(VARCHAR(50), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    account_type: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    balance_paise: Mapped[int] = mapped_column(BIGINT, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(VARCHAR(10), nullable=False, default="INR")
    is_active: Mapped[int] = mapped_column(INTEGER, nullable=False, default=1)

    __table_args__ = (
        CheckConstraint("account_type IN ('checking', 'savings', 'credit')", name="ck_accounts_account_type"),
        Index("idx_accounts_user_id", "user_id"),
    )

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="accounts")
    cards: Mapped[List["CardModel"]] = relationship("CardModel", back_populates="account", cascade="all, delete-orphan")
    transactions: Mapped[List["TransactionModel"]] = relationship("TransactionModel", back_populates="account", cascade="all, delete-orphan")


class CardModel(Base):
    __tablename__ = "cards"

    card_id: Mapped[str] = mapped_column(VARCHAR(50), primary_key=True)
    account_id: Mapped[str] = mapped_column(VARCHAR(50), ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False, index=True)
    last4: Mapped[str] = mapped_column(VARCHAR(4), nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="active")

    __table_args__ = (
        CheckConstraint("status IN ('active', 'locked', 'reported_lost')", name="ck_cards_status"),
        Index("idx_cards_account_id", "account_id"),
    )

    account: Mapped["AccountModel"] = relationship("AccountModel", back_populates="cards")


class TransactionModel(Base):
    __tablename__ = "transactions"

    transaction_id: Mapped[str] = mapped_column(VARCHAR(50), primary_key=True)
    account_id: Mapped[str] = mapped_column(VARCHAR(50), ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False, index=True)
    txn_type: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    amount_paise: Mapped[int] = mapped_column(BIGINT, nullable=False)
    merchant: Mapped[Optional[str]] = mapped_column(VARCHAR(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True, default=utc_now)
    flagged_fraud: Mapped[int] = mapped_column(INTEGER, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("txn_type IN ('deposit', 'withdrawal', 'purchase', 'transfer', 'fee', 'interest')", name="ck_transactions_txn_type"),
        Index("idx_transactions_account_id", "account_id"),
        Index("idx_transactions_timestamp", "timestamp"),
    )

    account: Mapped["AccountModel"] = relationship("AccountModel", back_populates="transactions")


class SessionModel(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(VARCHAR(64), primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(VARCHAR(50), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(VARCHAR(20), nullable=False, default="cli")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        Index("idx_sessions_user_id", "user_id"),
    )

    user: Mapped[Optional["UserModel"]] = relationship("UserModel", back_populates="sessions")
    messages: Mapped[List["MessageModel"]] = relationship("MessageModel", back_populates="session", cascade="all, delete-orphan")


class MessageModel(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(INTEGER, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(VARCHAR(64), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    turn: Mapped[int] = mapped_column(INTEGER, nullable=False)
    role: Mapped[str] = mapped_column(VARCHAR(20), nullable=False)
    content: Mapped[str] = mapped_column(TEXT, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_messages_role"),
        Index("idx_messages_session_id", "session_id"),
    )

    session: Mapped["SessionModel"] = relationship("SessionModel", back_populates="messages")


class MemoryEntryModel(Base):
    __tablename__ = "memory_entries"

    memory_id: Mapped[str] = mapped_column(VARCHAR(64), primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(VARCHAR(50), nullable=True, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(VARCHAR(64), nullable=True, index=True)
    memory_type: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    content: Mapped[str] = mapped_column(TEXT, nullable=False)
    role: Mapped[Optional[str]] = mapped_column(VARCHAR(20), nullable=True)
    importance: Mapped[float] = mapped_column(FLOAT, nullable=False, default=0.5)
    recency_score: Mapped[float] = mapped_column(FLOAT, nullable=False, default=1.0)
    relevance_score: Mapped[float] = mapped_column(FLOAT, nullable=False, default=0.0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True, default=utc_now)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    is_deleted: Mapped[int] = mapped_column(INTEGER, nullable=False, default=0)

    __table_args__ = (
        Index("idx_memory_user_id", "user_id"),
        Index("idx_memory_session_id", "session_id"),
        Index("idx_memory_type", "memory_type"),
        Index("idx_memory_created", "created_at"),
        Index("idx_memory_expires", "expires_at"),
    )


class MemorySummaryModel(Base):
    __tablename__ = "memory_summaries"

    summary_id: Mapped[str] = mapped_column(VARCHAR(64), primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(VARCHAR(50), nullable=True, index=True)
    session_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    content: Mapped[str] = mapped_column(TEXT, nullable=False)
    turn_start: Mapped[int] = mapped_column(INTEGER, nullable=False)
    turn_end: Mapped[int] = mapped_column(INTEGER, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        Index("idx_summary_session", "session_id"),
        Index("idx_summary_user", "user_id"),
    )


class UserProfileModel(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(VARCHAR(50), primary_key=True)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    facts: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class VectorEmbeddingModel(Base):
    __tablename__ = "vector_embeddings"

    embedding_id: Mapped[str] = mapped_column(VARCHAR(64), primary_key=True)
    entity_type: Mapped[str] = mapped_column(VARCHAR(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(VARCHAR(64), nullable=False, index=True)
    content: Mapped[str] = mapped_column(TEXT, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
