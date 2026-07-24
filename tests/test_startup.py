import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from config import MissingAPIKeyError, require_llm_config, validate_startup
from db.init_db import REQUIRED_TABLES, ensure_database
from mcp_servers.common import safe_mcp_call
from tools import memory


def test_database_initialization_is_idempotent_and_preserves_data(tmp_path):
    db_path = tmp_path / "bank.db"

    first = ensure_database(db_path, seed_demo_data=True)
    second = ensure_database(db_path, seed_demo_data=True)

    assert first["status"] == "ready"
    assert second["status"] == "ready"
    assert second["demo_data"] == "preserved"

    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()

    assert REQUIRED_TABLES.issubset(tables)
    assert user_count == 8


def test_memory_session_persistence_uses_initialized_database(tmp_path, monkeypatch):
    db_path = tmp_path / "memory.db"
    monkeypatch.setattr(memory, "DB_PATH", db_path)

    session_id = memory.create_session(channel="test")
    memory.append_message(session_id, 1, "user", "hello")
    memory.append_message(session_id, 1, "assistant", "hi")

    assert memory.session_exists(session_id)
    assert memory.load_session_messages(session_id) == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]


def test_missing_api_key_validation(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError):
        require_llm_config()


def test_startup_validation_without_llm(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REQUIRED_DIRECTORIES", (tmp_path / "logs",))
    status = validate_startup(require_llm=False, initialize=False)
    assert status.ok is True
    assert status.details["llm"] == "not required for this check"


def test_cli_check_startup_succeeds_without_api_key():
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    proc = subprocess.run(
        [sys.executable, "cli.py", "--check-startup"],
        cwd=Path(__file__).parent.parent,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0
    assert "Startup validation passed" in proc.stdout
    assert "Traceback" not in proc.stdout + proc.stderr


def test_cli_missing_api_key_exits_gracefully():
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    proc = subprocess.run(
        [sys.executable, "cli.py"],
        cwd=Path(__file__).parent.parent,
        env=env,
        input="exit\n",
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 2
    assert "ANTHROPIC_API_KEY is not set" in proc.stdout
    assert "Traceback" not in proc.stdout + proc.stderr


def test_mcp_safe_call_returns_structured_errors():
    def invalid_tool(required_arg):
        return {"ok": required_arg}

    result = safe_mcp_call("invalid_tool", invalid_tool)
    assert "error" in result
    assert result["error"] == "Invalid tool request."


def test_graph_and_agent_imports_do_not_require_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import agents.account_agent
    import agents.fraud_agent
    import agents.search_agent
    import agents.supervisor  # noqa: F401
    from graph import build_graph

    assert build_graph() is not None
