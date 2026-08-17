"""
Comprehensive unit and integration test suite for Fixed-Point Money Storage (Step E).

Covers:
  - Exact decimal conversion & arithmetic precision (0.10 + 0.20 = 0.30).
  - Boundary rounding (1.005 -> 101, -1.005 -> -101).
  - NULL and unexpected legacy data fail-safe handling.
  - SQLite schema migration from REAL to INTEGER minor units (balance_paise / amount_paise).
  - Preservation of row counts, primary key IDs, foreign keys, and indexes.
  - Migration idempotency.
  - Tool and API response contracts.
"""

from __future__ import annotations

import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.init_db import create_schema_if_needed, migrate_money_columns_if_needed
from tools.account_tools import get_balance, get_transaction_history
from utils.money import format_currency, paise_to_decimal, paise_to_rupees, to_paise


def test_exact_decimal_conversion():
    """Verify to_paise converts float, string, int, and Decimal cleanly."""
    assert to_paise(12.34) == 1234
    assert to_paise("12.34") == 1234
    assert to_paise(Decimal("12.34")) == 1234
    assert to_paise(100) == 10000


def test_floating_point_inaccuracy_prevention():
    """Verify that 0.10 + 0.20 produces exactly 30 paise (0.30) without float drift."""
    val1 = to_paise("0.10")  # 10 paise
    val2 = to_paise("0.20")  # 20 paise
    total = val1 + val2
    assert total == 30
    assert paise_to_rupees(total) == 0.30
    assert paise_to_decimal(total) == Decimal("0.30")
    assert format_currency(total) == "₹0.30"


def test_boundary_rounding():
    """Verify boundary rounding rules using Decimal ROUND_HALF_UP (1.005 -> 101, -1.005 -> -101)."""
    assert to_paise("1.005") == 101
    assert to_paise("-1.005") == -101
    assert to_paise("1.004") == 100
    assert to_paise("-1.004") == -100


def test_null_and_corrupt_failsafe_handling():
    """Verify fail-safe default behavior for NULL or unparseable input."""
    assert to_paise(None) == 0
    assert to_paise("corrupt_value") == 0
    assert paise_to_rupees("invalid") == 0.0
    assert format_currency("invalid") == "₹0.00"


def test_format_currency():
    """Verify human-friendly currency formatting for positive, negative, and custom symbols."""
    assert format_currency(1542050) == "₹15,420.50"
    assert format_currency(-5000) == "-₹50.00"
    assert format_currency(0) == "₹0.00"
    assert format_currency(2500, currency="USD") == "$25.00"
    assert format_currency(2500, currency="EUR") == "€25.00"


def test_legacy_database_migration(tmp_path):
    """
    Test safe transaction-based migration of legacy SQLite schema with REAL money columns.

    Asserts:
      - balance -> balance_paise and amount -> amount_paise conversion.
      - Exact preservation of row counts and primary key IDs.
      - Foreign key constraints, indexes, and schema integrity preservation.
      - Idempotency when run multiple times.
    """
    db_file = tmp_path / "legacy_test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA foreign_keys = ON")

    # Create legacy schema with REAL columns
    conn.executescript("""
        CREATE TABLE users (
            user_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            pin_hash TEXT NOT NULL,
            failed_attempts INTEGER NOT NULL DEFAULT 0,
            locked_until TEXT DEFAULT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE accounts (
            account_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            account_type TEXT NOT NULL,
            balance REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'INR',
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE transactions (
            transaction_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            txn_type TEXT NOT NULL,
            amount REAL NOT NULL,
            merchant TEXT,
            timestamp TEXT NOT NULL,
            flagged_fraud INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        );

        CREATE TABLE cards (
            card_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            last4 TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        );

        CREATE TABLE sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT,
            channel TEXT NOT NULL DEFAULT 'cli',
            created_at TEXT NOT NULL,
            last_active_at TEXT NOT NULL
        );

        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            turn INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE INDEX idx_accounts_user_id ON accounts(user_id);
        CREATE INDEX idx_transactions_account_id ON transactions(account_id);
        """)

    # Insert legacy records with floating point balance and amounts (including NULL legacy test row)
    conn.execute(
        "INSERT INTO users VALUES ('U1', 'Test', 'User', 'test@example.com', 'hash', 0, NULL, '2026-01-01')"
    )
    conn.execute(
        "INSERT INTO accounts VALUES ('A1', 'U1', 'checking', 15420.50, 'INR', 1)"
    )
    conn.execute(
        "INSERT INTO accounts VALUES ('A2', 'U1', 'savings', 500.05, 'INR', 1)"
    )
    conn.execute(
        "INSERT INTO transactions VALUES ('T1', 'A1', 'deposit', 1000.25, 'Salary', '2026-01-02', 0)"
    )
    conn.execute(
        "INSERT INTO transactions VALUES ('T2', 'A1', 'withdrawal', -500.50, 'ATM', '2026-01-03', 0)"
    )
    conn.commit()

    # Verify pre-migration state
    acc_count_before = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    txn_count_before = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    assert acc_count_before == 2
    assert txn_count_before == 2

    # Execute migration
    migrated = migrate_money_columns_if_needed(conn)
    assert migrated is True

    # 1. Verify row counts and IDs preserved
    acc_rows = conn.execute(
        "SELECT account_id, balance_paise FROM accounts ORDER BY account_id"
    ).fetchall()
    txn_rows = conn.execute(
        "SELECT transaction_id, amount_paise FROM transactions ORDER BY transaction_id"
    ).fetchall()

    assert len(acc_rows) == 2
    assert len(txn_rows) == 2

    assert acc_rows[0] == ("A1", 1542050)
    assert acc_rows[1] == ("A2", 50005)

    assert txn_rows[0] == ("T1", 100025)
    assert txn_rows[1] == ("T2", -50050)

    # 2. Verify Foreign Keys and Indexes present
    conn.execute("PRAGMA foreign_keys = ON")
    fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
    assert len(fk_errors) == 0

    idx_rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index'"
    ).fetchall()
    idx_names = {r[0] for r in idx_rows}
    assert "idx_accounts_user_id" in idx_names
    assert "idx_transactions_account_id" in idx_names

    # 3. Verify Idempotency — re-running migration returns False and makes no changes
    re_migrated = migrate_money_columns_if_needed(conn)
    assert re_migrated is False

    re_migrated_schema = create_schema_if_needed(conn)
    assert re_migrated_schema is False

    conn.close()


def test_trigger_preservation_and_auditable_null_warning(tmp_path, caplog):
    """
    Verify that triggers are preserved across migration and that NULL values emit
    auditable structured log warnings.
    """
    import logging

    db_file = tmp_path / "trigger_test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA foreign_keys = ON")

    conn.executescript("""
        CREATE TABLE users (
            user_id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            pin_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE accounts (
            account_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            account_type TEXT NOT NULL,
            balance REAL,  -- NULL allowed for legacy test
            currency TEXT DEFAULT 'INR',
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TRIGGER trg_test_account AFTER INSERT ON accounts
        BEGIN
            SELECT 1;
        END;
        """)

    conn.execute(
        "INSERT INTO users VALUES ('U9', 'Null', 'Test', 'null@test.com', 'hash', '2026-01-01')"
    )
    conn.execute("INSERT INTO accounts VALUES ('A9', 'U9', 'checking', NULL, 'INR', 1)")
    conn.commit()

    with caplog.at_level(logging.WARNING):
        migrated = migrate_money_columns_if_needed(conn)

    assert migrated is True

    # 1. Verify trigger preserved
    trig_rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'accounts'"
    ).fetchall()
    assert len(trig_rows) == 1
    assert trig_rows[0][0] == "trg_test_account"

    # 2. Verify auditable log warning was logged with structured extra attributes
    assert "legacy_money_data_corruption_normalized" in caplog.text
    record = [
        r for r in caplog.records if r.msg == "legacy_money_data_corruption_normalized"
    ][0]
    assert record.reason == "NULL balance normalized to 0 paise"
    assert record.table == "accounts"
    assert record.primary_key == "A9"

    # 3. Verify normalized value is 0
    row = conn.execute(
        "SELECT balance_paise FROM accounts WHERE account_id = 'A9'"
    ).fetchone()
    assert row[0] == 0

    conn.close()


def test_tool_responses_use_minor_units_and_formatting():
    """Verify get_balance and get_transaction_history return authoritative balance_paise and formatted string."""
    res_bal = get_balance("U1001")
    assert "accounts" in res_bal
    account = res_bal["accounts"][0]
    assert "balance_paise" in account
    assert isinstance(account["balance_paise"], int)
    assert "balance_formatted" in account
    assert account["balance_formatted"].startswith("₹")
    assert "balance" in account  # Compatibility field

    res_txn = get_transaction_history("U1001", limit=1)
    assert "transactions" in res_txn
    if res_txn["transactions"]:
        txn = res_txn["transactions"][0]
        assert "amount_paise" in txn
        assert isinstance(txn["amount_paise"], int)
        assert "amount_formatted" in txn
        assert "amount" in txn  # Compatibility field
