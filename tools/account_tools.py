"""
Account tools: read-mostly operations against the SQL database.
Every function returns a plain dict/list — never raises for expected failure
cases (e.g. user not found); it returns {"error": "..."} instead, so the
calling agent can react to it in-conversation rather than crashing.

PIN hashing
-----------
New PINs are hashed with Argon2id (via argon2-cffi), the current OWASP
recommendation for password/PIN storage.  The ``argon2.PasswordHasher``
defaults (time_cost=3, memory_cost=65536, parallelism=4) are intentionally
conservative: a 4-digit PIN has only 10 000 combinations, so the KDF cost is
the primary defence against offline brute force.

Backwards-compat migration
--------------------------
The demo database was seeded with raw SHA-256 hashes.  When
``verify_identity`` detects a legacy SHA-256 hash in the ``pin_hash`` column
(recognised by its 64-char hex format and absence of an Argon2 prefix), it
falls back to SHA-256 comparison and, on success, **transparently rehashes the
PIN to Argon2** in the same transaction before returning to the caller.  No
migration script is required; the upgrade happens automatically on the next
successful login.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

from db.connection import DB_PATH, get_connection
from db.init_db import ensure_database

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Argon2 setup with graceful fallback to SHA-256
# ---------------------------------------------------------------------------

try:
    from argon2 import PasswordHasher as _Argon2PasswordHasher
    from argon2.exceptions import VerifyMismatchError as _VerifyMismatchError

    _ph = _Argon2PasswordHasher()
    _ARGON2_AVAILABLE = True
    _DUMMY_HASH = _ph.hash("0000")
except ImportError:  # pragma: no cover
    _ARGON2_AVAILABLE = False
    _DUMMY_HASH = hashlib.sha256(b"dummy").hexdigest()
    LOGGER.warning(
        "argon2_cffi_not_installed: falling back to SHA-256 for PIN hashing. "
        "Run `pip install argon2-cffi` for secure hashing."
    )


def _is_legacy_sha256(stored: str) -> bool:
    """Return True if *stored* looks like a raw hex-encoded SHA-256 digest."""
    return len(stored) == 64 and all(c in "0123456789abcdef" for c in stored)


def hash_pin(pin: str) -> str:
    """Hash a PIN for storage.

    Uses Argon2id when available; falls back to SHA-256 so the rest of the
    application keeps working if argon2-cffi is not installed yet.
    """
    if _ARGON2_AVAILABLE:
        return _ph.hash(pin)
    # Legacy / fallback — identical to the old implementation.
    return hashlib.sha256(pin.encode()).hexdigest()


def _verify_pin(pin: str, stored_hash: str) -> bool:
    """Verify *pin* against *stored_hash*, supporting both Argon2 and SHA-256."""
    if _ARGON2_AVAILABLE and not _is_legacy_sha256(stored_hash):
        try:
            return _ph.verify(stored_hash, pin)
        except _VerifyMismatchError:
            return False
    # Legacy SHA-256 path (demo data seeded before argon2 was added).
    return hashlib.sha256(pin.encode()).hexdigest() == stored_hash


def _rehash_to_argon2(conn: sqlite3.Connection, user_id: str, pin: str) -> None:
    """Transparently upgrade a stored SHA-256 hash to Argon2 after a successful login."""
    new_hash = _ph.hash(pin)
    conn.execute(
        "UPDATE users SET pin_hash = ? WHERE user_id = ?",
        (new_hash, user_id),
    )
    conn.commit()
    LOGGER.info("pin_rehashed_to_argon2", extra={"user_id": user_id})


# ---------------------------------------------------------------------------
# Connection helper (uses centralized factory + ensures DB is ready)
# ---------------------------------------------------------------------------


def _connect(db_path=None):
    ensure_database(db_path or DB_PATH, seed_demo_data=True)
    return get_connection(db_path or DB_PATH)


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------


MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


def verify_identity(user_id: str, pin: str) -> dict:
    """
    Verify a user's identity by user_id + 4-digit PIN.
    This is the ONLY function that unlocks access to account/fraud tools —
    it is called from a deterministic graph node, not left to LLM discretion.

    Failed attempts are tracked per user_id. After 5 consecutive failures,
    the account is temporarily locked for 15 minutes.
    Success resets the failure counter to 0. All operations are atomic.
    """
    conn = _connect()
    try:
        with conn:
            row = conn.execute(
                "SELECT user_id, first_name, pin_hash, failed_attempts, locked_until "
                "FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()

            if row is None:
                # Timing attack countermeasure: run a dummy verification hash
                _verify_pin("0000", _DUMMY_HASH)
                return {
                    "verified": False,
                    "error": "User ID or PIN did not match our records.",
                }

            stored_hash: str = row["pin_hash"]
            failed_attempts: int = row["failed_attempts"]
            locked_until_str: str | None = row["locked_until"]

            now = datetime.now(timezone.utc)

            # Check if currently locked
            if locked_until_str:
                try:
                    locked_until = datetime.fromisoformat(locked_until_str)
                    if now < locked_until:
                        LOGGER.warning(
                            "verify_identity_blocked_locked", extra={"user_id": user_id}
                        )
                        return {
                            "verified": False,
                            "error": "This account is temporarily locked due to multiple failed authentication attempts. Please try again later.",
                        }
                    else:
                        # Lockout expired, treat as reset failed attempts locally first
                        failed_attempts = 0
                        locked_until_str = None
                except Exception:
                    # Gracefully recovery on malformed timestamp
                    failed_attempts = 0
                    locked_until_str = None

            # Verify PIN
            verified = _verify_pin(pin, stored_hash)

            if verified:
                # Successful login: reset failed_attempts and locked_until
                conn.execute(
                    "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE user_id = ?",
                    (user_id,),
                )

                # Transparent SHA-256 → Argon2 upgrade on first successful login.
                if _ARGON2_AVAILABLE and _is_legacy_sha256(stored_hash):
                    new_hash = _ph.hash(pin)
                    conn.execute(
                        "UPDATE users SET pin_hash = ? WHERE user_id = ?",
                        (new_hash, user_id),
                    )
                    LOGGER.info("pin_rehashed_to_argon2", extra={"user_id": user_id})

                LOGGER.info("verify_identity_success", extra={"user_id": user_id})
                return {
                    "verified": True,
                    "user_id": row["user_id"],
                    "first_name": row["first_name"],
                }
            else:
                # Failed login: increment failed_attempts
                failed_attempts += 1
                new_locked_until = None
                if failed_attempts >= MAX_FAILED_ATTEMPTS:
                    lock_time = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                    new_locked_until = lock_time.isoformat()
                    conn.execute(
                        "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE user_id = ?",
                        (failed_attempts, new_locked_until, user_id),
                    )
                    LOGGER.warning(
                        "verify_identity_locked",
                        extra={
                            "user_id": user_id,
                            "failed_attempts": failed_attempts,
                            "locked_until": new_locked_until,
                        },
                    )
                    return {
                        "verified": False,
                        "error": "This account is temporarily locked due to multiple failed authentication attempts. Please try again later.",
                    }
                else:
                    conn.execute(
                        "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE user_id = ?",
                        (failed_attempts, locked_until_str, user_id),
                    )
                    LOGGER.warning(
                        "verify_identity_failed",
                        extra={"user_id": user_id, "failed_attempts": failed_attempts},
                    )
                    return {
                        "verified": False,
                        "error": "User ID or PIN did not match our records.",
                    }
    finally:
        conn.close()


def get_balance(user_id: str, account_id: str | None = None) -> dict:
    """
    Get balance for a specific account, or all accounts for a user if account_id is omitted.
    Uses authoritative balance_paise (integer minor units).
    """
    from utils.money import format_currency, paise_to_rupees

    conn = _connect()
    try:
        if account_id:
            row = conn.execute(
                "SELECT account_id, account_type, balance_paise, currency FROM accounts "
                "WHERE user_id = ? AND account_id = ?",
                (user_id, account_id),
            ).fetchone()
            if row is None:
                return {"error": f"No account {account_id} found for this user."}
            res = dict(row)
            paise = res["balance_paise"]
            res["balance"] = paise_to_rupees(paise)  # Read-only compatibility field
            res["balance_formatted"] = format_currency(
                paise, currency=res.get("currency", "INR")
            )
            return res

        rows = conn.execute(
            "SELECT account_id, account_type, balance_paise, currency FROM accounts WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        if not rows:
            return {"error": "No accounts found for this user."}
        formatted_rows = []
        for r in rows:
            res = dict(r)
            paise = res["balance_paise"]
            res["balance"] = paise_to_rupees(paise)  # Read-only compatibility field
            res["balance_formatted"] = format_currency(
                paise, currency=res.get("currency", "INR")
            )
            formatted_rows.append(res)
        return {"accounts": formatted_rows}
    finally:
        conn.close()


def get_transaction_history(
    user_id: str, account_id: str | None = None, limit: int = 10
) -> dict:
    """
    Get recent transactions for a user, optionally scoped to one account.
    Uses authoritative amount_paise (integer minor units).
    """
    from utils.money import format_currency, paise_to_rupees

    conn = _connect()
    try:
        if account_id:
            owned = conn.execute(
                "SELECT 1 FROM accounts WHERE user_id = ? AND account_id = ?",
                (user_id, account_id),
            ).fetchone()
            if not owned:
                return {"error": f"Account {account_id} does not belong to this user."}
            rows = conn.execute(
                "SELECT transaction_id, txn_type, amount_paise, merchant, timestamp "
                "FROM transactions WHERE account_id = ? ORDER BY timestamp DESC LIMIT ?",
                (account_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT t.transaction_id, t.account_id, t.txn_type, t.amount_paise, t.merchant, t.timestamp "
                "FROM transactions t JOIN accounts a ON t.account_id = a.account_id "
                "WHERE a.user_id = ? ORDER BY t.timestamp DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()

        formatted_rows = []
        for r in rows:
            res = dict(r)
            paise = res["amount_paise"]
            res["amount"] = paise_to_rupees(paise)  # Read-only compatibility field
            res["amount_formatted"] = format_currency(paise)
            formatted_rows.append(res)
        return {"transactions": formatted_rows}
    finally:
        conn.close()


def mask_account_number(
    account_number: str, mask_char: str = "*", visible_last: int = 4
) -> str:
    """Mask an account/card identifier, showing only the last `visible_last` chars."""
    cleaned = "".join(filter(str.isalnum, account_number))
    if len(cleaned) <= visible_last:
        return cleaned
    return mask_char * (len(cleaned) - visible_last) + cleaned[-visible_last:]
