import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from api import health
from api.main import app


@pytest.fixture
def client():
    # Ensure health probe starts fresh
    return TestClient(app)


def test_readiness_starting(client, monkeypatch):
    """Test readiness probe returns 503 during the initial startup phase."""
    monkeypatch.setattr(health, "_ready", False)
    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "starting"
    assert data["ready"] is False


def test_readiness_healthy(client, monkeypatch):
    """Test readiness probe returns 200 when all dependencies are healthy."""
    monkeypatch.setattr(health, "_ready", True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-here")

    from mcp_platform.manager import get_mcp_manager

    mcp_mgr = get_mcp_manager()
    monkeypatch.setattr(mcp_mgr, "_initialized", True)

    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["ready"] is True
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["vector_store"] == "ok"
    assert data["checks"]["mcp_platform"] == "ok"
    assert data["checks"]["configuration"] == "ok"


def test_readiness_degraded_database(client, monkeypatch):
    """Test readiness probe returns 503 when the database check fails."""
    monkeypatch.setattr(health, "_ready", True)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-here")

    from mcp_platform.manager import get_mcp_manager

    mcp_mgr = get_mcp_manager()
    monkeypatch.setattr(mcp_mgr, "_initialized", True)

    # Force a database failure on get_connection
    import db.connection

    def mock_get_connection(*args, **kwargs):
        raise RuntimeError("Database file is locked.")

    monkeypatch.setattr(db.connection, "get_connection", mock_get_connection)

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["ready"] is False
    assert data["checks"]["database"] == "failed"


def test_proxy_headers_environment_loading(monkeypatch):
    """Test that proxy header parameters are read correctly from environment settings."""
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "10.0.0.1,10.0.0.2")
    ips = os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1")
    assert ips == "10.0.0.1,10.0.0.2"
