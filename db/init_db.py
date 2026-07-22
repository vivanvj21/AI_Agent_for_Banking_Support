"""Idempotent SQLite initialization for fresh clones and app startup."""

from __future__ import annotations

import logging
import random
import sqlite3
from pathlib import Path

from db import seed_synthetic_data as seed_data

LOGGER = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "bank.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"
REQUIRED_TABLES = {"users", "accounts", "cards", "transactions", "sessions", "messages"}


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _existing_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row["name"] for row in rows}


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


def create_schema_if_needed(conn: sqlite3.Connection) -> bool:
    """Create missing schema objects without dropping existing data."""
    before = _existing_tables(conn)
    conn.executescript(_schema_without_destructive_statements())
    conn.commit()
    after = _existing_tables(conn)
    created = not REQUIRED_TABLES.issubset(before) and REQUIRED_TABLES.issubset(after)
    if created:
        LOGGER.info("database_schema_initialized")
    return created


def _table_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])


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
    conn = _connect(db_path)
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
