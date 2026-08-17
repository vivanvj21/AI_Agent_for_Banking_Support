"""Initial PostgreSQL Database Schema with pgvector and indexes

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-05 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Extension for vector embeddings if running on PostgreSQL
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "users",
        sa.Column("user_id", sa.VARCHAR(length=50), nullable=False),
        sa.Column("first_name", sa.VARCHAR(length=100), nullable=False),
        sa.Column("last_name", sa.VARCHAR(length=100), nullable=False),
        sa.Column("email", sa.VARCHAR(length=255), nullable=False),
        sa.Column("pin_hash", sa.VARCHAR(length=255), nullable=False),
        sa.Column("failed_attempts", sa.INTEGER(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "accounts",
        sa.Column("account_id", sa.VARCHAR(length=50), nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=50), nullable=False),
        sa.Column("account_type", sa.VARCHAR(length=20), nullable=False),
        sa.Column("balance_paise", sa.BIGINT(), nullable=False, server_default="0"),
        sa.Column(
            "currency", sa.VARCHAR(length=10), nullable=False, server_default="INR"
        ),
        sa.Column("is_active", sa.INTEGER(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "account_type IN ('checking', 'savings', 'credit')",
            name="ck_accounts_account_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("account_id"),
    )
    op.create_index("idx_accounts_user_id", "accounts", ["user_id"])

    op.create_table(
        "cards",
        sa.Column("card_id", sa.VARCHAR(length=50), nullable=False),
        sa.Column("account_id", sa.VARCHAR(length=50), nullable=False),
        sa.Column("last4", sa.VARCHAR(length=4), nullable=False),
        sa.Column(
            "status", sa.VARCHAR(length=20), nullable=False, server_default="active"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'locked', 'reported_lost')", name="ck_cards_status"
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.account_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("card_id"),
    )
    op.create_index("idx_cards_account_id", "cards", ["account_id"])

    op.create_table(
        "transactions",
        sa.Column("transaction_id", sa.VARCHAR(length=50), nullable=False),
        sa.Column("account_id", sa.VARCHAR(length=50), nullable=False),
        sa.Column("txn_type", sa.VARCHAR(length=20), nullable=False),
        sa.Column("amount_paise", sa.BIGINT(), nullable=False),
        sa.Column("merchant", sa.VARCHAR(length=255), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("flagged_fraud", sa.INTEGER(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "txn_type IN ('deposit', 'withdrawal', 'purchase', 'transfer', 'fee', 'interest')",
            name="ck_transactions_txn_type",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.account_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("transaction_id"),
    )
    op.create_index("idx_transactions_account_id", "transactions", ["account_id"])
    op.create_index("idx_transactions_timestamp", "transactions", ["timestamp"])

    op.create_table(
        "sessions",
        sa.Column("session_id", sa.VARCHAR(length=64), nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=50), nullable=True),
        sa.Column(
            "channel", sa.VARCHAR(length=20), nullable=False, server_default="cli"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index("idx_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.VARCHAR(length=64), nullable=False),
        sa.Column("turn", sa.INTEGER(), nullable=False),
        sa.Column("role", sa.VARCHAR(length=20), nullable=False),
        sa.Column("content", sa.TEXT(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'system')", name="ck_messages_role"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.session_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_messages_session_id", "messages", ["session_id"])

    op.create_table(
        "memory_entries",
        sa.Column("memory_id", sa.VARCHAR(length=64), nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=50), nullable=True),
        sa.Column("session_id", sa.VARCHAR(length=64), nullable=True),
        sa.Column("memory_type", sa.VARCHAR(length=50), nullable=False),
        sa.Column("content", sa.TEXT(), nullable=False),
        sa.Column("role", sa.VARCHAR(length=20), nullable=True),
        sa.Column("importance", sa.FLOAT(), nullable=False, server_default="0.5"),
        sa.Column("recency_score", sa.FLOAT(), nullable=False, server_default="1.0"),
        sa.Column("relevance_score", sa.FLOAT(), nullable=False, server_default="0.0"),
        sa.Column(
            "metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.INTEGER(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("memory_id"),
    )
    op.create_index("idx_memory_user_id", "memory_entries", ["user_id"])
    op.create_index("idx_memory_session_id", "memory_entries", ["session_id"])
    op.create_index("idx_memory_type", "memory_entries", ["memory_type"])
    op.create_index("idx_memory_created", "memory_entries", ["created_at"])
    op.create_index("idx_memory_expires", "memory_entries", ["expires_at"])

    op.create_table(
        "memory_summaries",
        sa.Column("summary_id", sa.VARCHAR(length=64), nullable=False),
        sa.Column("user_id", sa.VARCHAR(length=50), nullable=True),
        sa.Column("session_id", sa.VARCHAR(length=64), nullable=False),
        sa.Column("content", sa.TEXT(), nullable=False),
        sa.Column("turn_start", sa.INTEGER(), nullable=False),
        sa.Column("turn_end", sa.INTEGER(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("summary_id"),
    )
    op.create_index("idx_summary_session", "memory_summaries", ["session_id"])
    op.create_index("idx_summary_user", "memory_summaries", ["user_id"])

    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.VARCHAR(length=50), nullable=False),
        sa.Column(
            "preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("facts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "vector_embeddings",
        sa.Column("embedding_id", sa.VARCHAR(length=64), nullable=False),
        sa.Column("entity_type", sa.VARCHAR(length=50), nullable=False),
        sa.Column("entity_id", sa.VARCHAR(length=64), nullable=False),
        sa.Column("content", sa.TEXT(), nullable=False),
        sa.Column(
            "metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("embedding_id"),
    )
    op.create_index(
        "idx_vector_entity", "vector_embeddings", ["entity_type", "entity_id"]
    )


def downgrade() -> None:
    op.drop_table("vector_embeddings")
    op.drop_table("user_profiles")
    op.drop_table("memory_summaries")
    op.drop_table("memory_entries")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("transactions")
    op.drop_table("cards")
    op.drop_table("accounts")
    op.drop_table("users")
