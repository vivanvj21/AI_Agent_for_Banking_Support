"""
Phase 12 — Perimeter API Authentication Test Suite.

Verifies:
- Valid API-Key header (X-API-Key) allows access to protected endpoints.
- Missing / invalid keys yield 401 Unauthorized.
- Keys passed via query parameters (?api_key=...) are rejected (header-only enforcement).
- Public probes and OpenAPI docs (/health, /health/live, /health/ready, /docs, /redoc, /openapi.json) remain exempt.
- secrets.compare_digest primitive is invoked for constant-time comparison.
- Production profile missing API_KEY fails fast (ConfigurationError).
- Development profile missing API_KEY without PERIMETER_AUTH_OPT_OUT=true fails fast (ConfigurationError).
- Development profile with PERIMETER_AUTH_OPT_OUT=true logs explicit warning.
- SecretStr redaction for API_KEY.
- Dependency ordering: perimeter authentication is evaluated before rate limiting.
"""

from __future__ import annotations

import secrets
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from config import AppConfig, ConfigurationError, SecretStr


@pytest.fixture
def client_with_key(monkeypatch):
    """TestClient configured with API_KEY='test-secret-key-1234'."""
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("API_KEY", "test-secret-key-1234")
    monkeypatch.delenv("PERIMETER_AUTH_OPT_OUT", raising=False)
    # Re-evaluate config settings
    cfg = AppConfig.load_from_env()
    monkeypatch.setattr("config.settings", cfg)
    return TestClient(app)


def test_public_routes_exempt(client_with_key):
    """Verify health and docs routes do not require X-API-Key."""
    for path in ["/health", "/health/live", "/health/ready", "/docs", "/openapi.json"]:
        res = client_with_key.get(path)
        assert res.status_code in (
            200,
            307,
            503,
        ), f"Expected public access for {path}, got {res.status_code}"


def test_protected_route_without_key(client_with_key):
    """Verify protected route yields 401 Unauthorized when X-API-Key is missing."""
    res = client_with_key.post("/chat", json={"message": "hello"})
    assert res.status_code == 401
    assert res.json() == {"detail": "Unauthorized"}


def test_protected_route_with_invalid_key(client_with_key):
    """Verify protected route yields 401 Unauthorized when X-API-Key is wrong."""
    res = client_with_key.post(
        "/chat",
        headers={"X-API-Key": "wrong-key-value"},
        json={"message": "hello"},
    )
    assert res.status_code == 401
    assert res.json() == {"detail": "Unauthorized"}


def test_protected_route_with_query_param_key_rejected(client_with_key):
    """Verify API_KEY passed as query parameter is ignored and yields 401 (header-only)."""
    res = client_with_key.post(
        "/chat?api_key=test-secret-key-1234",
        json={"message": "hello"},
    )
    assert res.status_code == 401
    assert res.json() == {"detail": "Unauthorized"}


def test_protected_route_with_valid_key(client_with_key):
    """Verify protected route succeeds when valid X-API-Key is provided."""
    res = client_with_key.post(
        "/chat",
        headers={"X-API-Key": "test-secret-key-1234"},
        json={"message": "hello"},
    )
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.json()}"
    assert "reply" in res.json()


def test_mcp_routes_protected_by_perimeter_auth(client_with_key):
    """Verify MCP endpoints require X-API-Key header."""
    res_unauth = client_with_key.get("/mcp/status")
    assert res_unauth.status_code == 401

    res_auth = client_with_key.get(
        "/mcp/status", headers={"X-API-Key": "test-secret-key-1234"}
    )
    assert res_auth.status_code == 200


def test_secrets_compare_digest_invoked(client_with_key):
    """Verify secrets.compare_digest primitive is called for key validation."""
    with patch("secrets.compare_digest", wraps=secrets.compare_digest) as mock_compare:
        res = client_with_key.post(
            "/chat",
            headers={"X-API-Key": "test-secret-key-1234"},
            json={"message": "hello"},
        )
        assert res.status_code == 200
        assert mock_compare.called
        # Check args passed to compare_digest
        args = mock_compare.call_args[0]
        assert args[0] == "test-secret-key-1234"
        assert args[1] == "test-secret-key-1234"


def test_production_profile_fails_fast_without_key(monkeypatch):
    """Verify production mode missing API_KEY raises ConfigurationError during startup."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("PERIMETER_AUTH_OPT_OUT", raising=False)

    with pytest.raises(ConfigurationError) as exc_info:
        AppConfig.load_from_env()

    assert "API_KEY must be configured in production profile" in str(exc_info.value)


def test_development_profile_fails_fast_without_key_and_without_opt_out(monkeypatch):
    """Verify dev mode missing API_KEY raises ConfigurationError unless PERIMETER_AUTH_OPT_OUT=true is set."""
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("PERIMETER_AUTH_OPT_OUT", raising=False)

    with pytest.raises(ConfigurationError) as exc_info:
        AppConfig.load_from_env()

    assert "API_KEY is missing in 'development' profile" in str(exc_info.value)


def test_development_profile_explicit_opt_out_logs_warning(monkeypatch, caplog):
    """Verify dev mode missing API_KEY with PERIMETER_AUTH_OPT_OUT=true logs warning and allows dev mode."""
    import logging

    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setenv("PERIMETER_AUTH_OPT_OUT", "true")

    with caplog.at_level(logging.WARNING):
        cfg = AppConfig.load_from_env()

    assert cfg.security.require_api_key is False
    assert "perimeter_auth_explicit_dev_opt_out_active" in caplog.text


def test_secret_str_redaction_for_api_key():
    """Verify API_KEY SecretStr redacts plaintext value."""
    sec = SecretStr("secret-api-key-9999")
    assert sec.get_secret_value() == "secret-api-key-9999"
    assert str(sec) == "secr***************"
    assert repr(sec) == "SecretStr('secr***************')"
    assert "secret-api-key-9999" not in str(sec)


def test_auth_evaluated_before_rate_limiter(client_with_key):
    """
    Verify that unauthenticated requests return 401 BEFORE rate limiter
    counters are incremented.
    """
    from api.rate_limiter import rate_limit_chat

    client_ip = "testclient"
    initial_count = len(rate_limit_chat.history.get(client_ip, []))

    # 1. Unauthenticated request -> should return 401 without updating rate limit history
    res_unauth = client_with_key.post("/chat", json={"message": "test"})
    assert res_unauth.status_code == 401
    assert len(rate_limit_chat.history.get(client_ip, [])) == initial_count

    # 2. Authenticated request -> should pass auth and update rate limit history
    res_auth = client_with_key.post(
        "/chat",
        headers={"X-API-Key": "test-secret-key-1234"},
        json={"message": "test"},
    )
    assert res_auth.status_code == 200
    assert len(rate_limit_chat.history.get(client_ip, [])) == initial_count + 1
