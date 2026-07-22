"""
Account tools: read-mostly operations against the SQL database.
Every function returns a plain dict/list — never raises for expected failure
cases (e.g. user not found); it returns {"error": "..."} instead, so the
calling agent can react to it in-conversation rather than crashing.
"""

import sqlite3
import hashlib
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "bank.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()


def verify_identity(user_id: str, pin: str) -> dict:
    """
    Verify a user's identity by user_id + 4-digit PIN.
    This is the ONLY function that unlocks access to account/fraud tools —
    it is called from a deterministic graph node, not left to LLM discretion.
    """
    conn = _connect()
    row = conn.execute(
        "SELECT user_id, first_name FROM users WHERE user_id = ? AND pin_hash = ?",
        (user_id, hash_pin(pin)),
    ).fetchone()
    conn.close()
    if row is None:
        return {"verified": False, "error": "User ID or PIN did not match our records."}
    return {"verified": True, "user_id": row["user_id"], "first_name": row["first_name"]}


def get_balance(user_id: str, account_id: str | None = None) -> dict:
    """
    Get balance for a specific account, or all accounts for a user if
    account_id is omitted.
    """
    conn = _connect()
    if account_id:
        row = conn.execute(
            "SELECT account_id, account_type, balance, currency FROM accounts "
            "WHERE user_id = ? AND account_id = ?",
            (user_id, account_id),
        ).fetchone()
        conn.close()
        if row is None:
            return {"error": f"No account {account_id} found for this user."}
        return dict(row)

    rows = conn.execute(
        "SELECT account_id, account_type, balance, currency FROM accounts WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    conn.close()
    if not rows:
        return {"error": "No accounts found for this user."}
    return {"accounts": [dict(r) for r in rows]}


def get_transaction_history(user_id: str, account_id: str | None = None, limit: int = 10) -> dict:
    """
    Get recent transactions for a user, optionally scoped to one account.
    """
    conn = _connect()
    if account_id:
        # confirm the account belongs to this user before returning anything
        owned = conn.execute(
            "SELECT 1 FROM accounts WHERE user_id = ? AND account_id = ?",
            (user_id, account_id),
        ).fetchone()
        if not owned:
            conn.close()
            return {"error": f"Account {account_id} does not belong to this user."}
        rows = conn.execute(
            "SELECT transaction_id, txn_type, amount, merchant, timestamp "
            "FROM transactions WHERE account_id = ? ORDER BY timestamp DESC LIMIT ?",
            (account_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT t.transaction_id, t.account_id, t.txn_type, t.amount, t.merchant, t.timestamp "
            "FROM transactions t JOIN accounts a ON t.account_id = a.account_id "
            "WHERE a.user_id = ? ORDER BY t.timestamp DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    conn.close()
    return {"transactions": [dict(r) for r in rows]}


def mask_account_number(account_number: str, mask_char: str = "*", visible_last: int = 4) -> str:
    """Mask an account/card identifier, showing only the last `visible_last` chars."""
    cleaned = "".join(filter(str.isalnum, account_number))
    if len(cleaned) <= visible_last:
        return cleaned
    return mask_char * (len(cleaned) - visible_last) + cleaned[-visible_last:]
