"""
LangSmith configuration loader and runtime enable/disable control.

LangSmith is entirely OPTIONAL. If langsmith is not installed or
LANGSMITH_TRACING is not set to "true", the application continues to
work with zero overhead — every tracing call becomes a no-op.

Environment variables (all optional):
    LANGSMITH_API_KEY      – Your LangSmith API key.
    LANGSMITH_PROJECT      – Project name (default: "bank-assistant").
    LANGSMITH_ENDPOINT     – API endpoint (default: LangSmith cloud).
    LANGSMITH_TRACING      – "true" / "1" to enable (default: disabled).

Usage:
    from observability.langsmith_config import is_tracing_enabled, configure_langsmith

    configure_langsmith()          # call once at startup
    if is_tracing_enabled():
        ...                        # safe to use LangSmith client
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

LOGGER = logging.getLogger(__name__)

# Module-level state — mutated by configure_langsmith() exactly once per process.
_configured: bool = False
_tracing_enabled: bool = False


@dataclass(frozen=True)
class LangSmithConfig:
    """Immutable snapshot of LangSmith runtime configuration."""

    enabled: bool
    api_key: str | None
    project: str
    endpoint: str | None
    extras: dict = field(default_factory=dict)


def _parse_bool(value: str | None) -> bool:
    """Parse "true" / "1" / "yes" as True; everything else as False."""
    return str(value or "").strip().lower() in ("true", "1", "yes")


def get_langsmith_config() -> LangSmithConfig:
    """Read LangSmith configuration from central settings.

    Never raises — returns a disabled config on any error.
    """
    try:
        from config import settings
        obs = settings.observability
        api_key = obs.api_key.get_secret_value() or None
        enabled = obs.enabled

        if enabled and not api_key:
            LOGGER.warning(
                "langsmith_tracing_requested_but_no_api_key: "
                "set LANGSMITH_API_KEY to enable tracing"
            )
            enabled = False

        return LangSmithConfig(
            enabled=enabled,
            api_key=api_key,
            project=obs.project,
            endpoint=obs.endpoint,
        )
    except Exception:
        LOGGER.exception("langsmith_config_read_failed; tracing disabled")
        return LangSmithConfig(
            enabled=False, api_key=None, project="bank-assistant", endpoint=None
        )


def configure_langsmith() -> bool:
    """Configure the LangSmith SDK via environment variables.

    Idempotent — safe to call multiple times.  Returns True if tracing
    was successfully enabled, False otherwise.

    This sets the OS-level environment variables that the LangSmith SDK
    reads automatically, so LangGraph traces are captured without any
    further instrumentation of the graph itself.
    """
    global _configured, _tracing_enabled

    if _configured:
        return _tracing_enabled

    cfg = get_langsmith_config()

    if not cfg.enabled:
        _configured = True
        _tracing_enabled = False
        LOGGER.debug("langsmith_tracing_disabled")
        return False

    try:
        # Validate that langsmith is importable before setting env vars.
        import langsmith  # noqa: F401

        # Set the canonical env vars the SDK reads.
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = cfg.api_key  # type: ignore[assignment]
        os.environ["LANGCHAIN_PROJECT"] = cfg.project
        if cfg.endpoint:
            os.environ["LANGCHAIN_ENDPOINT"] = cfg.endpoint

        _tracing_enabled = True
        LOGGER.info(
            "langsmith_tracing_enabled",
            extra={"project": cfg.project, "endpoint": cfg.endpoint or "cloud"},
        )
    except ImportError:
        LOGGER.warning(
            "langsmith_package_not_installed: "
            "run `pip install langsmith` to enable tracing"
        )
        _tracing_enabled = False
    except Exception:
        LOGGER.exception("langsmith_configure_failed; tracing disabled")
        _tracing_enabled = False

    _configured = True
    return _tracing_enabled


def is_tracing_enabled() -> bool:
    """Return True if LangSmith tracing is active in this process."""
    return _tracing_enabled


def reset_for_testing() -> None:
    """Reset module-level state.  FOR TESTS ONLY."""
    global _configured, _tracing_enabled
    _configured = False
    _tracing_enabled = False
