import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_allowed_origins, ConfigurationError


def test_cors_dev_defaults(monkeypatch):
    """Test that default dev origins are returned when ENV is development/dev/local."""
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    origins = get_allowed_origins()
    assert "http://localhost:3000" in origins
    assert "http://localhost:8501" in origins
    assert "http://127.0.0.1:3000" in origins
    assert "http://127.0.0.1:8501" in origins
    assert len(origins) == 4

    monkeypatch.setenv("ENV", "local")
    origins = get_allowed_origins()
    assert "http://localhost:3000" in origins


def test_cors_custom_origins(monkeypatch):
    """Test that custom comma-separated ALLOWED_ORIGINS are parsed correctly."""
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://bank.example.com , http://localhost:3000,https://internal.bank.com")
    origins = get_allowed_origins()
    assert origins == [
        "https://bank.example.com",
        "http://localhost:3000",
        "https://internal.bank.com",
    ]


def test_cors_staging_defaults(monkeypatch):
    """Test that staging environment defaults are returned when ENV is staging."""
    monkeypatch.setenv("ENV", "staging")
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    origins = get_allowed_origins()
    assert origins == ["https://staging.bank.internal"]


def test_cors_production_defaults(monkeypatch):
    """Test that production environment defaults to empty (no access) for security."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    origins = get_allowed_origins()
    assert origins == []


def test_cors_wildcard_rejection(monkeypatch):
    """Test that wildcard '*' configuration throws ConfigurationError to prevent credential leakages."""
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")
    with pytest.raises(ConfigurationError) as exc_info:
        get_allowed_origins()
    assert "wildcard '*' is not allowed" in str(exc_info.value)

    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000, *")
    with pytest.raises(ConfigurationError):
        get_allowed_origins()
