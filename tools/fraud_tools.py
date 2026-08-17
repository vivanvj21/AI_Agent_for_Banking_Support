"""
Fraud tools: state-changing operations, so each function is defensive about
ownership checks before acting. These are only reachable after identity
verification (enforced in the graph, not here — but we double check
ownership here too, since a tool should never trust its caller blindly).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from db.connection import DB_PATH, get_connection
from db.init_db import ensure_database

LOGGER = logging.getLogger(__name__)


def _connect(db_path=None):
    ensure_database(db_path or DB_PATH, seed_demo_data=True)
    return get_connection(db_path or DB_PATH)


def lock_card(user_id: str, card_id: str) -> dict:
    """
    Lock a card belonging to this user. Reversible action (see unlock_card).
    """
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT c.card_id, c.status FROM cards c "
            "JOIN accounts a ON c.account_id = a.account_id "
            "WHERE c.card_id = ? AND a.user_id = ?",
            (card_id, user_id),
        ).fetchone()
        if row is None:
            return {"error": f"Card {card_id} not found for this user."}
        if row["status"] == "locked":
            return {"status": "already_locked", "card_id": card_id}

        conn.execute("UPDATE cards SET status = 'locked' WHERE card_id = ?", (card_id,))
        conn.commit()
        LOGGER.info("card_locked", extra={"user_id": user_id, "card_id": card_id})
        return {"status": "locked", "card_id": card_id}
    finally:
        conn.close()


def unlock_card(user_id: str, card_id: str) -> dict:
    """Unlock a previously locked card belonging to this user."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT c.card_id, c.status FROM cards c "
            "JOIN accounts a ON c.account_id = a.account_id "
            "WHERE c.card_id = ? AND a.user_id = ?",
            (card_id, user_id),
        ).fetchone()
        if row is None:
            return {"error": f"Card {card_id} not found for this user."}
        if row["status"] == "reported_lost":
            return {
                "error": "This card was reported lost/stolen and cannot be unlocked. It must be replaced."
            }

        conn.execute("UPDATE cards SET status = 'active' WHERE card_id = ?", (card_id,))
        conn.commit()
        LOGGER.info("card_unlocked", extra={"user_id": user_id, "card_id": card_id})
        return {"status": "active", "card_id": card_id}
    finally:
        conn.close()


def report_card_lost(user_id: str, card_id: str) -> dict:
    """Permanently report a card lost/stolen (distinct from lock_card — not reversible)."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT c.card_id FROM cards c JOIN accounts a ON c.account_id = a.account_id "
            "WHERE c.card_id = ? AND a.user_id = ?",
            (card_id, user_id),
        ).fetchone()
        if row is None:
            return {"error": f"Card {card_id} not found for this user."}

        conn.execute(
            "UPDATE cards SET status = 'reported_lost' WHERE card_id = ?", (card_id,)
        )
        conn.commit()
        LOGGER.info(
            "card_reported_lost", extra={"user_id": user_id, "card_id": card_id}
        )
        return {
            "status": "reported_lost",
            "card_id": card_id,
            "note": "Replacement will be issued in 5-7 business days.",
        }
    finally:
        conn.close()


def report_fraud_transaction(
    user_id: str, transaction_id: str, reason: str = ""
) -> dict:
    """Flag a specific transaction as fraudulent for investigation."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT t.transaction_id, t.flagged_fraud FROM transactions t "
            "JOIN accounts a ON t.account_id = a.account_id "
            "WHERE t.transaction_id = ? AND a.user_id = ?",
            (transaction_id, user_id),
        ).fetchone()
        if row is None:
            return {"error": f"Transaction {transaction_id} not found for this user."}
        if row["flagged_fraud"]:
            return {"status": "already_flagged", "transaction_id": transaction_id}

        conn.execute(
            "UPDATE transactions SET flagged_fraud = 1 WHERE transaction_id = ?",
            (transaction_id,),
        )
        conn.commit()
        reported_at = datetime.now(timezone.utc).isoformat()
        LOGGER.info(
            "fraud_transaction_reported",
            extra={
                "user_id": user_id,
                "transaction_id": transaction_id,
                "reason": reason,
            },
        )
        return {
            "status": "flagged",
            "transaction_id": transaction_id,
            "reported_at": reported_at,
            "note": "Provisional credit may be issued within 10 business days pending investigation.",
        }
    finally:
        conn.close()


def get_flagged_transactions(user_id: str) -> dict:
    """List all transactions currently flagged as fraud for this user."""
    from utils.money import format_currency, paise_to_rupees

    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT t.transaction_id, t.account_id, t.txn_type, t.amount_paise, t.merchant, t.timestamp "
            "FROM transactions t JOIN accounts a ON t.account_id = a.account_id "
            "WHERE a.user_id = ? AND t.flagged_fraud = 1 ORDER BY t.timestamp DESC",
            (user_id,),
        ).fetchall()
        formatted_rows = []
        for r in rows:
            res = dict(r)
            paise = res["amount_paise"]
            res["amount"] = paise_to_rupees(paise)  # Read-only compatibility field
            res["amount_formatted"] = format_currency(paise)
            formatted_rows.append(res)
        return {"flagged_transactions": formatted_rows}
    finally:
        conn.close()
