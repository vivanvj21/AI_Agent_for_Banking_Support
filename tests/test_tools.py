"""
Unit tests for the tool layer. These never call the Anthropic API, so they
run in CI without needing secrets — only the graph/agent integration tests
(test_conversations.py) need ANTHROPIC_API_KEY.
"""

import sys
from pathlib import Path
import sqlite3
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.account_tools import verify_identity, get_balance, get_transaction_history, mask_account_number
from tools.fraud_tools import lock_card, unlock_card, report_card_lost, report_fraud_transaction, get_flagged_transactions

DB_PATH = Path(__file__).parent.parent / "db" / "bank.db"


@pytest.fixture(scope="module")
def known_user():
    return "U1002"


@pytest.fixture(scope="module")
def known_card(known_user):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT c.card_id FROM cards c JOIN accounts a ON c.account_id = a.account_id WHERE a.user_id = ? LIMIT 1",
        (known_user,),
    ).fetchone()
    conn.close()
    assert row is not None, "Seed data must include at least one card for U1002 — run db/seed_synthetic_data.py"
    return row[0]


def test_verify_identity_success(known_user):
    result = verify_identity(known_user, "1222")
    assert result["verified"] is True
    assert result["user_id"] == known_user


def test_verify_identity_wrong_pin(known_user):
    result = verify_identity(known_user, "0000")
    assert result["verified"] is False


def test_verify_identity_unknown_user():
    result = verify_identity("U9999", "1234")
    assert result["verified"] is False


def test_get_balance_returns_accounts(known_user):
    result = get_balance(known_user)
    assert "accounts" in result
    assert len(result["accounts"]) > 0
    assert "balance" in result["accounts"][0]


def test_get_balance_unknown_user():
    result = get_balance("U9999")
    assert "error" in result


def test_get_transaction_history_limit(known_user):
    result = get_transaction_history(known_user, limit=5)
    assert "transactions" in result
    assert len(result["transactions"]) <= 5


def test_lock_and_unlock_card_roundtrip(known_user, known_card):
    result = lock_card(known_user, known_card)
    assert result["status"] == "locked"

    result_again = lock_card(known_user, known_card)
    assert result_again["status"] == "already_locked"

    result_unlock = unlock_card(known_user, known_card)
    assert result_unlock["status"] == "active"


def test_cannot_lock_another_users_card(known_card):
    """Ownership check: a different user must not be able to act on this card."""
    result = lock_card("U1003", known_card)
    assert "error" in result


def test_report_fraud_transaction_requires_ownership(known_user):
    # Grab a real transaction ID belonging to this user
    history = get_transaction_history(known_user, limit=1)
    txn_id = history["transactions"][0]["transaction_id"]

    result = report_fraud_transaction(known_user, txn_id, reason="test")
    assert result["status"] in ("flagged", "already_flagged")

    # Wrong user cannot flag someone else's transaction
    other_result = report_fraud_transaction("U1003", txn_id, reason="test")
    assert "error" in other_result


def test_mask_account_number():
    assert mask_account_number("123456789012") == "********9012"
    assert mask_account_number("12", visible_last=4) == "12"


def test_get_flagged_transactions_structure(known_user):
    result = get_flagged_transactions(known_user)
    assert "flagged_transactions" in result
    assert isinstance(result["flagged_transactions"], list)
