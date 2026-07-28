import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
import sqlite3

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.account_tools import verify_identity, _connect, DB_PATH

@pytest.fixture(autouse=True)
def reset_lockout_states():
    """Ensure user U1002 has 0 failed attempts and NULL locked_until before and after tests."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE user_id = 'U1002'"
    )
    conn.commit()
    conn.close()
    yield
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE user_id = 'U1002'"
    )
    conn.commit()
    conn.close()


def test_lockout_after_five_failed_attempts():
    """Test that account gets locked after exactly 5 failed attempts."""
    # First 4 attempts fail with wrong PIN
    for i in range(4):
        res = verify_identity("U1002", "9999")
        assert res["verified"] is False
        assert "did not match our records" in res["error"]

    # 5th attempt locks the account
    res = verify_identity("U1002", "9999")
    assert res["verified"] is False
    assert "temporarily locked" in res["error"]

    # Even with correct PIN, verification is rejected while locked
    res = verify_identity("U1002", "1222")
    assert res["verified"] is False
    assert "temporarily locked" in res["error"]


def test_lockout_expiration_unlocks_account():
    """Test that after lockout duration passes, the correct PIN succeeds."""
    # Trigger lockout
    for _ in range(5):
        verify_identity("U1002", "9999")

    # Lockout timestamp is in DB. Let's fake it to the past to simulate expiration
    conn = _connect()
    past_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    conn.execute(
        "UPDATE users SET locked_until = ? WHERE user_id = 'U1002'",
        (past_time.isoformat(),)
    )
    conn.commit()
    conn.close()

    # Now verify with correct PIN. It should succeed and reset failed_attempts
    res = verify_identity("U1002", "1222")
    assert res["verified"] is True

    # Check database counters have been reset
    conn = _connect()
    row = conn.execute(
        "SELECT failed_attempts, locked_until FROM users WHERE user_id = 'U1002'"
    ).fetchone()
    conn.close()
    assert row["failed_attempts"] == 0
    assert row["locked_until"] is None


def test_regression_four_failed_one_success_resets():
    """
    Regression Test:
    Attempt 1-4 -> wrong PIN
    Attempt 5 -> correct PIN -> succeeds and resets
    Attempt 6 -> wrong PIN -> failed_attempts == 1
    """
    # 1-4: Wrong PIN
    for _ in range(4):
        res = verify_identity("U1002", "9999")
        assert res["verified"] is False

    # 5: Correct PIN (succeeds)
    res = verify_identity("U1002", "1222")
    assert res["verified"] is True

    # Check DB reset
    conn = _connect()
    row = conn.execute(
        "SELECT failed_attempts, locked_until FROM users WHERE user_id = 'U1002'"
    ).fetchone()
    conn.close()
    assert row["failed_attempts"] == 0
    assert row["locked_until"] is None

    # 6: Wrong PIN
    res = verify_identity("U1002", "9999")
    assert res["verified"] is False

    # Verify counter is 1, not 5
    conn = _connect()
    row = conn.execute(
        "SELECT failed_attempts, locked_until FROM users WHERE user_id = 'U1002'"
    ).fetchone()
    conn.close()
    assert row["failed_attempts"] == 1
    assert row["locked_until"] is None
