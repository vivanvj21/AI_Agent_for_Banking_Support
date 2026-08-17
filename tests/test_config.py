"""
Unit tests for the centralized Configuration & Secrets Architecture (Step D).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    ConfigurationError,
    MissingAPIKeyError,
    SecretStr,
    reload_settings,
    require_llm_config,
    settings,
)


def test_secret_str_redaction():
    """Verify SecretStr redacts values and prevents accidental exposure in str/repr."""
    secret = SecretStr("sk-ant-1234567890abcdef")
    assert secret.get_secret_value() == "sk-ant-1234567890abcdef"
    assert str(secret) == "sk-ant-****************"
    assert "sk-ant-****************" in repr(secret)
    assert "1234567890abcdef" not in str(secret)
    assert "1234567890abcdef" not in repr(secret)

    short_secret = SecretStr("secret12")
    assert str(short_secret) == "********"


def test_environment_profile_switching(monkeypatch):
    """Verify switching ENV environment profiles updates configuration properties."""
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("API_KEY", "prod-test-key-12345")
    cfg = reload_settings()
    assert cfg.app.env == "production"
    assert (
        cfg.logging.json_logging is True
    )  # Production enables JSON logging by default

    monkeypatch.setenv("ENV", "development")
    cfg_dev = reload_settings()
    assert cfg_dev.app.env == "development"


def test_invalid_environment_profile(monkeypatch):
    """Verify that an unrecognized environment profile raises a ConfigurationError."""
    monkeypatch.setenv("ENV", "invalid_env_name")
    with pytest.raises(ConfigurationError) as exc_info:
        reload_settings()
    assert "Invalid ENV profile" in str(exc_info.value)


def test_invalid_port_validation(monkeypatch):
    """Verify that out-of-range ports fail validation at startup."""
    monkeypatch.setenv("API_PORT", "99999")
    with pytest.raises(ConfigurationError) as exc_info:
        reload_settings()
    assert "Port numbers out of valid range" in str(exc_info.value)


def test_invalid_log_level_validation(monkeypatch):
    """Verify that invalid log levels raise ConfigurationError."""
    monkeypatch.setenv("LOG_LEVEL", "SUPER_LOG")
    with pytest.raises(ConfigurationError) as exc_info:
        reload_settings()
    assert "Invalid LOG_LEVEL" in str(exc_info.value)


def test_invalid_mcp_timeout_validation(monkeypatch):
    """Verify that negative timeouts fail validation."""
    monkeypatch.setenv("MCP_DEFAULT_TIMEOUT", "-5.0")
    with pytest.raises(ConfigurationError) as exc_info:
        reload_settings()
    assert "MCP timeouts and retry delays must be positive numbers" in str(
        exc_info.value
    )


def test_cors_wildcard_rejection(monkeypatch):
    """Verify that wildcard CORS origins raise ConfigurationError when credentials are supported."""
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000,*")
    with pytest.raises(ConfigurationError) as exc_info:
        reload_settings()
    assert "wildcard '*' is not allowed" in str(exc_info.value)


def test_fingerprint_generation_and_drift(monkeypatch):
    """Verify SHA-256 fingerprint generation excludes secret values and changes on non-sensitive parameter drift."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret1")
    cfg1 = reload_settings()
    fp1 = cfg1.get_fingerprint()

    # Changing API key should NOT change non-sensitive fingerprint
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret2")
    cfg2 = reload_settings()
    fp2 = cfg2.get_fingerprint()
    assert fp1 == fp2

    # Changing a non-sensitive port SHOULD change the fingerprint
    monkeypatch.setenv("API_PORT", "8080")
    cfg3 = reload_settings()
    fp3 = cfg3.get_fingerprint()
    assert fp1 != fp3


def test_startup_report_generation(monkeypatch):
    """Verify startup report includes component statuses without revealing raw secrets."""
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("PERIMETER_AUTH_OPT_OUT", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-12345")
    cfg = reload_settings()
    report = cfg.get_startup_report()
    report_text = "\n".join(report)

    assert "✓ Environment Profile: DEVELOPMENT" in report_text
    assert "✓ Config Fingerprint:" in report_text
    assert "✓ LLM Provider: anthropic" in report_text
    assert (
        "sk-ant-test-key-12345" not in report_text
    )  # Raw secret must never be exposed


def test_api_routes_import_cleanly():
    """Verify api.routes module imports cleanly without missing dependency NameErrors."""
    import importlib

    api_routes = importlib.import_module("api.routes")
    assert hasattr(api_routes, "router")
    assert hasattr(api_routes, "verify_perimeter_api_key")


def test_missing_llm_api_key_raises():
    """Verify require_llm_config raises MissingAPIKeyError when API key is missing."""
    old_val = settings.llm.api_key
    try:
        settings.llm.api_key = SecretStr("")
        with pytest.raises(MissingAPIKeyError):
            require_llm_config()
    finally:
        settings.llm.api_key = old_val
