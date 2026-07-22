"""Runtime configuration and startup validation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib.util
import logging
import os
from pathlib import Path

from logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
REQUIRED_DIRECTORIES = (
    ROOT_DIR / "knowledge_base",
    ROOT_DIR / "knowledge_base" / "faq_docs",
    ROOT_DIR / "db",
    ROOT_DIR / "docker",
    ROOT_DIR / "logs",
)


@dataclass(frozen=True)
class StartupStatus:
    """Component validation status suitable for CLI/Streamlit display."""

    ok: bool
    message: str
    details: dict[str, str] = field(default_factory=dict)


class ConfigurationError(RuntimeError):
    """Raised when required runtime configuration is missing or invalid."""


class MissingAPIKeyError(ConfigurationError):
    """Raised when an LLM call is requested without an API key."""


@dataclass(frozen=True)
class LLMProviderConfig:
    provider: str
    api_key: str | None
    model: str


def get_llm_config(provider: str | None = None) -> LLMProviderConfig:
    """Return the configured LLM provider without logging secret values."""
    selected = (provider or os.environ.get("LLM_PROVIDER") or "anthropic").lower()
    if selected != "anthropic":
        raise ConfigurationError(
            f"Unsupported LLM_PROVIDER={selected!r}. Currently supported: anthropic."
        )
    return LLMProviderConfig(
        provider="anthropic",
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
    )


def require_llm_config() -> LLMProviderConfig:
    """Validate LLM configuration before creating a model client."""
    config = get_llm_config()
    if not config.api_key:
        raise MissingAPIKeyError(
            "ANTHROPIC_API_KEY is not set. Set it to use the LangGraph agents "
            "or run offline tool tests that do not call the LLM."
        )
    if importlib.util.find_spec("anthropic") is None:
        raise ConfigurationError(
            "The anthropic package is not installed. Run: pip install -r requirements.txt"
        )
    return config


def ensure_directories() -> None:
    """Create runtime directories that are safe to create at startup."""
    for directory in REQUIRED_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)


def validate_startup(
    require_llm: bool = False, initialize: bool = True
) -> StartupStatus:
    """Validate directories, database, Chroma/index, memory, and optional LLM config."""
    configure_logging()
    details: dict[str, str] = {}
    try:
        ensure_directories()
        details["directories"] = "ok"

        if initialize:
            from db.init_db import ensure_database
            from tools.faq_search import build_index

            db_status = ensure_database(seed_demo_data=True)
            details["database"] = db_status["status"]
            details["demo_data"] = str(db_status.get("demo_data", "unknown"))

            index_status = build_index(rebuild=False)
            details["chroma"] = f"{index_status['chunks']} chunks indexed"
        else:
            details["database"] = "not initialized by validation"
            details["chroma"] = "not initialized by validation"

        if require_llm:
            llm_config = require_llm_config()
            details["llm"] = f"{llm_config.provider}:{llm_config.model}"
        else:
            details["llm"] = "not required for this check"

        LOGGER.info("startup_validation_ok", extra={"details": details})
        return StartupStatus(
            ok=True, message="Startup validation passed.", details=details
        )
    except ConfigurationError as exc:
        LOGGER.warning("startup_validation_failed", extra={"details": details})
        return StartupStatus(ok=False, message=str(exc), details=details)
    except Exception as exc:
        LOGGER.exception("startup_validation_failed")
        return StartupStatus(ok=False, message=str(exc), details=details)
