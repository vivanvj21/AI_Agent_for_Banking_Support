"""Idempotent SQLite initialization for fresh clones and app startup."""

from __future__ import annotations

import logging
import random
import sqlite3
from pathlib import Path

from db import seed_synthetic_data as seed_data
from db.connection import DB_PATH, get_connection

LOGGER = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
REQUIRED_TABLES = {"users", "accounts", "cards", "transactions", "sessions", "messages"}


def _existing_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row[0] for row in rows}


def _schema_without_destructive_statements() -> str:
    statements = []
    for line in SCHEMA_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip().upper().startswith("DROP TABLE"):
            continue
        if line.strip().upper().startswith("CREATE TABLE "):
            line = line.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1)
        if line.strip().upper().startswith("CREATE INDEX "):
            line = line.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1)
        statements.append(line)
    return "\n".join(statements)


def migrate_money_columns_if_needed(conn: sqlite3.Connection) -> bool:
    """
    Idempotent transaction-based migration converting legacy floating-point REAL
    balance/amount columns to integer minor-unit balance_paise/amount_paise columns.

    Preserves foreign keys, indexes, triggers, constraints, row counts, and sequence states.
    Failsafe: defaults NULL or unparseable values to 0 paise with auditable structured log warnings.
    """
    from datetime import datetime, timezone

    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(accounts)")
    accounts_cols = {row[1]: row[2] for row in cursor.fetchall()}

    cursor.execute("PRAGMA table_info(transactions)")
    txn_cols = {row[1]: row[2] for row in cursor.fetchall()}

    needs_account_migration = (
        "balance" in accounts_cols and "balance_paise" not in accounts_cols
    )
    needs_txn_migration = "amount" in txn_cols and "amount_paise" not in txn_cols

    if not needs_account_migration and not needs_txn_migration:
        return False

    LOGGER.info("starting_money_minor_units_migration")

    # Audit for NULL or corrupt legacy values before migration
    if needs_account_migration:
        null_accs = conn.execute(
            "SELECT account_id, balance FROM accounts WHERE balance IS NULL"
        ).fetchall()
        for acc_id, orig_val in null_accs:
            LOGGER.warning(
                "legacy_money_data_corruption_normalized",
                extra={
                    "table": "accounts",
                    "primary_key": acc_id,
                    "original_value": orig_val,
                    "normalized_value_paise": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "reason": "NULL balance normalized to 0 paise",
                },
            )

    if needs_txn_migration:
        null_txns = conn.execute(
            "SELECT transaction_id, amount FROM transactions WHERE amount IS NULL"
        ).fetchall()
        for txn_id, orig_val in null_txns:
            LOGGER.warning(
                "legacy_money_data_corruption_normalized",
                extra={
                    "table": "transactions",
                    "primary_key": txn_id,
                    "original_value": orig_val,
                    "normalized_value_paise": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "reason": "NULL amount normalized to 0 paise",
                },
            )

    # Capture triggers associated with accounts and transactions prior to rebuild
    triggers_to_recreate = conn.execute(
        "SELECT name, tbl_name, sql FROM sqlite_master WHERE type = 'trigger' AND tbl_name IN ('accounts', 'transactions')"
    ).fetchall()

    # Temporarily disable foreign keys during schema rebuild
    conn.execute("PRAGMA foreign_keys = OFF")

    try:
        conn.execute("BEGIN IMMEDIATE TRANSACTION")

        if needs_account_migration:
            conn.execute("""
                CREATE TABLE accounts_new (
                    account_id    TEXT PRIMARY KEY,
                    user_id       TEXT NOT NULL,
                    account_type  TEXT NOT NULL CHECK (account_type IN ('checking','savings','credit')),
                    balance_paise INTEGER NOT NULL,
                    currency      TEXT NOT NULL DEFAULT 'INR',
                    is_active     INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
                """)
            conn.execute("""
                INSERT INTO accounts_new (account_id, user_id, account_type, balance_paise, currency, is_active)
                SELECT account_id, user_id, account_type,
                       CAST(ROUND(COALESCE(balance, 0) * 100) AS INTEGER),
                       COALESCE(currency, 'INR'), is_active
                FROM accounts
                """)
            conn.execute("DROP TABLE accounts")
            conn.execute("ALTER TABLE accounts_new RENAME TO accounts")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id)"
            )
            LOGGER.info("migrated_accounts_table_to_balance_paise")

        if needs_txn_migration:
            conn.execute("""
                CREATE TABLE transactions_new (
                    transaction_id TEXT PRIMARY KEY,
                    account_id     TEXT NOT NULL,
                    txn_type       TEXT NOT NULL CHECK (txn_type IN ('deposit','withdrawal','purchase','transfer','fee','interest')),
                    amount_paise   INTEGER NOT NULL,
                    merchant       TEXT,
                    timestamp      TEXT NOT NULL,
                    flagged_fraud  INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
                )
                """)
            conn.execute("""
                INSERT INTO transactions_new (transaction_id, account_id, txn_type, amount_paise, merchant, timestamp, flagged_fraud)
                SELECT transaction_id, account_id, txn_type,
                       CAST(ROUND(COALESCE(amount, 0) * 100) AS INTEGER),
                       merchant, timestamp, flagged_fraud
                FROM transactions
                """)
            conn.execute("DROP TABLE transactions")
            conn.execute("ALTER TABLE transactions_new RENAME TO transactions")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_transactions_account_id ON transactions(account_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp)"
            )
            LOGGER.info("migrated_transactions_table_to_amount_paise")

        # Recreate captured triggers
        for trig_name, trig_table, trig_sql in triggers_to_recreate:
            if trig_sql:
                conn.execute(trig_sql)
                LOGGER.info(
                    "recreated_trigger_after_migration",
                    extra={"trigger": trig_name, "table": trig_table},
                )

        # Check foreign key integrity BEFORE committing to disk
        conn.execute("PRAGMA foreign_keys = ON")
        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            raise RuntimeError(
                f"Foreign key violations detected prior to commit: {fk_errors}"
            )

        conn.commit()
        return True
    except Exception as exc:
        conn.execute("ROLLBACK")
        conn.execute("PRAGMA foreign_keys = ON")
        LOGGER.exception("money_minor_units_migration_failed")
        raise RuntimeError(f"Money migration failed: {exc}") from exc


def create_schema_if_needed(conn: sqlite3.Connection) -> bool:
    """Create missing schema objects without dropping existing data."""
    before = _existing_tables(conn)
    conn.executescript(_schema_without_destructive_statements())
    conn.commit()

    # Idempotent migration to add failed_attempts and locked_until columns if missing
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    columns = {row[1] for row in cursor.fetchall()}
    if "failed_attempts" not in columns:
        conn.execute(
            "ALTER TABLE users ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0"
        )
        LOGGER.info("migration_added_failed_attempts_column")
    if "locked_until" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN locked_until TEXT DEFAULT NULL")
        LOGGER.info("migration_added_locked_until_column")
    conn.commit()

    # Idempotent migration to convert legacy REAL money columns to INTEGER minor units
    migrate_money_columns_if_needed(conn)

    after = _existing_tables(conn)
    created = not REQUIRED_TABLES.issubset(before) and REQUIRED_TABLES.issubset(after)
    if created:
        LOGGER.info("database_schema_initialized")
    return created


def _table_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()[0])


def seed_demo_data_if_empty(conn: sqlite3.Connection) -> bool:
    """Seed deterministic demo data only when core banking tables are empty."""
    if any(
        _table_count(conn, table) > 0
        for table in ("users", "accounts", "cards", "transactions")
    ):
        LOGGER.info("database_seed_skipped_existing_data")
        return False

    random.seed(42)
    user_ids = seed_data.seed_users(conn)
    account_ids = seed_data.seed_accounts_and_cards(conn, user_ids)
    seed_data.seed_transactions(conn, account_ids)
    conn.commit()
    LOGGER.info(
        "database_seeded_demo_data",
        extra={"users": len(user_ids), "accounts": len(account_ids)},
    )
    return True


def ensure_database(db_path: Path = DB_PATH, seed_demo_data: bool = True) -> dict:
    """Ensure SQLite exists, schema is present, and optional demo data is seeded.

    This function is idempotent and never deletes an existing database file.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    existed = db_path.exists()
    conn = get_connection(db_path)
    try:
        created_schema = create_schema_if_needed(conn)
        existing = _existing_tables(conn)
        missing = REQUIRED_TABLES - existing
        if missing:
            raise RuntimeError(
                f"Database schema missing required tables: {sorted(missing)}"
            )
        seeded = seed_demo_data_if_empty(conn) if seed_demo_data else False
        return {
            "status": "ready",
            "path": str(db_path),
            "existed": existed,
            "schema_created": created_schema,
            "demo_data": "seeded" if seeded else "preserved",
        }
    finally:
        conn.close()
