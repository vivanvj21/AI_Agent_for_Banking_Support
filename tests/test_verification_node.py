import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.state import AgentState
from agents.verification import extract_credentials, try_verify
from graph import verify_gate_node


def test_extract_credentials_deprecated():
    """Ensure extract_credentials has been successfully deprecated and returns None, None."""
    uid, pin = extract_credentials("What's my balance? U1002, 1222")
    assert uid is None
    assert pin is None


def test_try_verify_success():
    """Test try_verify with valid structured credentials."""
    result = try_verify(user_id="U1002", pin="1222")
    assert result["verified"] is True
    assert result["user_id"] == "U1002"
    assert result["first_name"] == "Vishnu"


def test_try_verify_wrong_pin():
    """Test try_verify with incorrect PIN."""
    result = try_verify(user_id="U1002", pin="9999")
    assert result["verified"] is False
    assert "error" in result


def test_try_verify_missing_params():
    """Test try_verify with missing parameters."""
    result = try_verify(user_id=None, pin=None)
    assert result["verified"] is False
    assert "verify your identity" in result["error"]


def test_verify_gate_node_success():
    """Test that verify_gate_node correctly reads credentials, verifies, and zeros the PIN."""
    state: AgentState = {
        "messages": [{"role": "user", "content": "What is my balance?"}],
        "turn": 1,
        "session_id": "test_session_123",
        "intent": "account",
        "verified": False,
        "auth_user_id": "U1002",
        "auth_pin": "1222",
        "retry_count": 0,
        "max_retries": 3,
        "tool_calls_log": [],
    }

    new_state = verify_gate_node(state)

    assert new_state["verified"] is True
    assert new_state["user_id"] == "U1002"
    assert new_state["auth_pin"] is None  # Zeroed out!


def test_verify_gate_node_failure():
    """Test verify_gate_node failure condition and correct zeroing of PIN."""
    state: AgentState = {
        "messages": [{"role": "user", "content": "What is my balance?"}],
        "turn": 1,
        "session_id": "test_session_123",
        "intent": "account",
        "verified": False,
        "auth_user_id": "U1002",
        "auth_pin": "9999",
        "retry_count": 0,
        "max_retries": 3,
        "tool_calls_log": [],
    }

    new_state = verify_gate_node(state)

    assert new_state["verified"] is False
    assert new_state["auth_pin"] is None  # Zeroed out!
    assert new_state["retry_count"] == 1
    assert any(
        term in new_state["reply"].lower()
        for term in ("records", "match", "error", "verify", "pin")
    )
