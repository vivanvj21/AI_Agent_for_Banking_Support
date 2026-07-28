"""
Centralized Production-Grade Configuration & Secrets Architecture (Phase 1 — Step D).

Single source of truth for all application parameters, credentials, deployment ports,
and component settings.

Loading hierarchy:
  1. Internal Defaults
  2. Environment Variables (.env / system OS)
  3. Runtime Overrides (passed explicitly)
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.resolve()
REQUIRED_DIRECTORIES = (
    ROOT_DIR / "knowledge_base",
    ROOT_DIR / "knowledge_base" / "faq_docs",
    ROOT_DIR / "db",
    ROOT_DIR / "docker",
    ROOT_DIR / "logs",
)

# LangSmith tracing initialization flag
_langsmith_initialized: bool = False


# ── Secret Str Wrapper ─────────────────────────────────────────────────────────

class SecretStr:
    """
    Encapsulates a secret string value (API keys, tokens, passwords).

    Intercepts __str__, __repr__, and json serialization to automatically redact
    values and prevent credential exposure in logs, stack traces, or UI output.
    """

    def __init__(self, value: str | None = None) -> None:
        self._value = value or ""

    def get_secret_value(self) -> str:
        """Retrieve the unredacted secret string for authorized API calls."""
        return self._value

    def __bool__(self) -> bool:
        return bool(self._value)

    def __len__(self) -> int:
        return len(self._value)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, SecretStr):
            return self._value == other._value
        if isinstance(other, str):
            return self._value == other
        return False

    def __str__(self) -> str:
        return self.redact(self._value)

    def __repr__(self) -> str:
        return f"SecretStr('{self.redact(self._value)}')"

    @staticmethod
    def redact(val: str) -> str:
        """Redact API keys securely while revealing key prefixes for auditability."""
        if not val:
            return ""
        if val.startswith("sk-ant-"):
            return "sk-ant-" + "*" * max(4, len(val) - 7)
        if val.startswith("AIza"):
            return "AIza" + "*" * max(4, len(val) - 4)
        if len(val) <= 8:
            return "*" * len(val)
        return val[:4] + "*" * (len(val) - 4)


# ── Exceptions ─────────────────────────────────────────────────────────────────

class ConfigurationError(RuntimeError):
    """Raised when required runtime configuration is missing or invalid."""


class MissingAPIKeyError(ConfigurationError):
    """Raised when an LLM call is requested without an API key."""


@dataclass(frozen=True)
class StartupStatus:
    """Component validation status suitable for CLI/Streamlit display."""

    ok: bool
    message: str
    details: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMProviderConfig:
    provider: str
    api_key: str | None
    model: str


# ── Domain Configuration Sub-Classes ─────────────────────────────────────────

@dataclass
class AppSettings:
    name: str = "Autonomous Bank Assistant"
    version: str = "1.0.0"
    env: str = "development"


@dataclass
class DeploymentSettings:
    port_streamlit: int = 8501
    port_api: int = 8000
    api_workers: int = 2
    forwarded_allow_ips: str = "127.0.0.1"


@dataclass
class SecuritySettings:
    allowed_origins: list[str] = field(default_factory=list)
    rate_limit_chat: tuple[int, int] = (10, 60)
    rate_limit_verify: tuple[int, int] = (5, 60)
    rate_limit_default: tuple[int, int] = (15, 60)
    api_key: SecretStr = field(default_factory=lambda: SecretStr(""))
    api_key_header_name: str = "X-API-Key"
    require_api_key: bool = True


@dataclass
class DatabaseSettings:
    db_path: Path = field(default_factory=lambda: ROOT_DIR / "db" / "bank.db")
    timeout_ms: int = 5000


@dataclass
class LoggingSettings:
    level: str = "INFO"
    json_logging: bool = False


@dataclass
class LLMSettings:
    provider: str = "anthropic"
    api_key: SecretStr = field(default_factory=lambda: SecretStr(""))
    model: str = "claude-sonnet-4-5"


@dataclass
class EmbeddingSettings:
    provider: str = "local"
    voyage_api_key: SecretStr = field(default_factory=lambda: SecretStr(""))
    voyage_model: str = "voyage-3.5"


@dataclass
class ObservabilitySettings:
    enabled: bool = False
    api_key: SecretStr = field(default_factory=lambda: SecretStr(""))
    project: str = "bank-assistant"
    endpoint: str | None = None


@dataclass
class OrchestrationSettings:
    high_confidence_threshold: float = 0.75
    medium_confidence_threshold: float = 0.50
    low_confidence_threshold: float = 0.30
    fallback_threshold: float = 0.20
    max_fallback_attempts: int = 2
    enable_multi_agent_collab: bool = True
    max_context_tokens: int = 3000
    max_history_turns: int = 10
    max_rag_chunks: int = 5
    max_memory_facts: int = 8
    supervisor_model: str = "claude-haiku-4-5"


@dataclass
class MCPSettings:
    disabled_servers: list[str] = field(default_factory=list)
    preferred_servers: list[str] = field(default_factory=list)
    auto_discover: bool = True
    mcp_servers_dir: str = "mcp_servers"
    default_timeout: float = 30.0
    max_retries: int = 2
    retry_delay: float = 1.0
    max_concurrent_tools: int = 3
    normalize_errors: bool = True
    min_confidence_for_mcp: float = 0.60
    feed_results_to_memory: bool = True
    feed_results_to_prompt: bool = True


@dataclass
class MemorySettings:
    max_conversation_turns: int = 50
    max_long_term_memories: int = 200
    max_semantic_memories: int = 500
    max_context_tokens: int = 4000
    similarity_threshold: float = 0.35
    top_k_semantic: int = 5
    top_k_recency: int = 10
    top_k_context: int = 8
    summary_threshold_turns: int = 20
    summary_max_tokens: int = 600
    importance_weight: float = 0.4
    recency_weight: float = 0.3
    relevance_weight: float = 0.3
    session_ttl_days: int = 90
    long_term_ttl_days: int = 365
    conversation_ttl_days: int = 30
    recency_half_life_hours: float = 48.0
    chroma_collection_name: str = "bank_memories"


@dataclass
class EvaluationSettings:
    metrics: list[str] = field(default_factory=list)
    output_dir: Path = field(default_factory=lambda: ROOT_DIR / "evaluation_reports")
    model: str = "claude-sonnet-4-5"
    batch_size: int = 10


# ── AppConfig Master Container ───────────────────────────────────────────────

@dataclass
class AppConfig:
    """Master single source of truth for application configuration."""

    app: AppSettings
    deployment: DeploymentSettings
    security: SecuritySettings
    database: DatabaseSettings
    logging: LoggingSettings
    llm: LLMSettings
    embedding: EmbeddingSettings
    observability: ObservabilitySettings
    orchestration: OrchestrationSettings
    mcp: MCPSettings
    memory: MemorySettings
    evaluation: EvaluationSettings

    def get_fingerprint(self) -> str:
        """Compute a SHA-256 fingerprint over non-sensitive configuration properties."""
        data = self.to_dict(include_secrets=False)
        dumped = json.dumps(data, sort_keys=True)
        return hashlib.sha256(dumped.encode("utf-8")).hexdigest()

    def to_dict(self, include_secrets: bool = False) -> dict[str, Any]:
        """Serialize configuration. All SecretStr values are redacted by default."""
        res: dict[str, Any] = {}
        for domain_key, domain_obj in self.__dict__.items():
            if hasattr(domain_obj, "__dict__"):
                sub_dict: dict[str, Any] = {}
                for prop_key, prop_val in domain_obj.__dict__.items():
                    if isinstance(prop_val, SecretStr):
                        sub_dict[prop_key] = prop_val.get_secret_value() if include_secrets else str(prop_val)
                    elif isinstance(prop_val, Path):
                        sub_dict[prop_key] = str(prop_val)
                    else:
                        sub_dict[prop_key] = prop_val
                res[domain_key] = sub_dict
            else:
                res[domain_key] = domain_obj
        return res

    def get_startup_report(self) -> list[str]:
        """Generate human-readable status verification lines for startup audit."""
        return [
            f"✓ Environment Profile: {self.app.env.upper()}",
            f"✓ App Version: {self.app.version}",
            f"✓ Config Fingerprint: {self.get_fingerprint()[:12]}...",
            f"✓ Database Path: {self.database.db_path}",
            f"✓ LLM Provider: {self.llm.provider} ({self.llm.model}) [Key Set: {bool(self.llm.api_key.get_secret_value())}]",
            f"✓ Embedding Provider: {self.embedding.provider} [Voyage Key Set: {bool(self.embedding.voyage_api_key.get_secret_value())}]",
            f"✓ MCP Platform Auto-Discover: {self.mcp.auto_discover}",
            f"✓ Observability Tracing: {self.observability.enabled}",
            f"✓ Logging Level: {self.logging.level} (JSON: {self.logging.json_logging})",
        ]

    @classmethod
    def load_from_env(cls, env_overrides: dict[str, str] | None = None) -> AppConfig:
        """
        Load configuration according to the deterministic hierarchy:
          1. Internal Defaults
          2. Environment Variables (.env / system OS)
          3. Runtime Overrides dictionary
        """
        get_val = lambda key, default=None: (
            env_overrides.get(key)
            if env_overrides and key in env_overrides
            else os.environ.get(key, default)
        )

        # 1. App
        env_profile = (get_val("ENV") or "development").lower()
        if env_profile not in ("development", "dev", "local", "testing", "test", "staging", "production", "prod"):
            raise ConfigurationError(f"Invalid ENV profile: {env_profile!r}")
        app_settings = AppSettings(env=env_profile)

        # 2. Deployment
        try:
            port_st = int(get_val("STREAMLIT_PORT", "8501"))
            port_api = int(get_val("API_PORT", "8000"))
            workers = int(get_val("API_WORKERS", "2"))
        except ValueError as exc:
            raise ConfigurationError(f"Invalid port or worker count: {exc}")

        if not (1 <= port_st <= 65535) or not (1 <= port_api <= 65535):
            raise ConfigurationError(f"Port numbers out of valid range (1-65535): st={port_st}, api={port_api}")
        if workers < 1:
            raise ConfigurationError(f"API_WORKERS must be >= 1, got {workers}")

        dep_settings = DeploymentSettings(
            port_streamlit=port_st,
            port_api=port_api,
            api_workers=workers,
            forwarded_allow_ips=get_val("FORWARDED_ALLOW_IPS", "127.0.0.1"),
        )

        # 3. Security (CORS & Rate Limits)
        origins_str = get_val("ALLOWED_ORIGINS")
        if origins_str:
            origins = [o.strip() for o in origins_str.split(",") if o.strip()]
        else:
            if env_profile in ("development", "dev", "local"):
                origins = [
                    "http://localhost:3000",
                    "http://localhost:8501",
                    "http://127.0.0.1:3000",
                    "http://127.0.0.1:8501",
                ]
            elif env_profile in ("staging",):
                origins = ["https://staging.bank.internal"]
            else:
                origins = []

        if "*" in origins:
            raise ConfigurationError(
                "CORS configuration error: wildcard '*' is not allowed when credentials support is enabled."
            )

        rl_chat = _parse_rate_limit(get_val("RATE_LIMIT_CHAT"), (10, 60))
        rl_verify = _parse_rate_limit(get_val("RATE_LIMIT_VERIFY"), (5, 60))
        rl_default = _parse_rate_limit(get_val("RATE_LIMIT_DEFAULT"), (15, 60))

        # Perimeter API Auth (Phase 12)
        api_key_val = SecretStr(get_val("API_KEY"))
        perimeter_opt_out = (get_val("PERIMETER_AUTH_OPT_OUT") or "false").lower() in ("true", "1")

        if env_profile in ("production", "prod"):
            if not api_key_val:
                raise ConfigurationError(
                    "Production configuration error: API_KEY must be configured in production profile. "
                    "Set API_KEY in environment variables."
                )
            require_api_key = True
        else:  # development, testing, staging
            if api_key_val:
                require_api_key = True
            elif perimeter_opt_out:
                require_api_key = False
                LOGGER.warning("perimeter_auth_explicit_dev_opt_out_active")
            else:
                raise ConfigurationError(
                    f"Configuration error: API_KEY is missing in '{env_profile}' profile. "
                    "Set API_KEY in environment or explicitly set PERIMETER_AUTH_OPT_OUT=true for development/testing."
                )

        sec_settings = SecuritySettings(
            allowed_origins=origins,
            rate_limit_chat=rl_chat,
            rate_limit_verify=rl_verify,
            rate_limit_default=rl_default,
            api_key=api_key_val,
            api_key_header_name="X-API-Key",
            require_api_key=require_api_key,
        )

        # 4. Database
        db_path_str = get_val("DB_PATH")
        db_path = Path(db_path_str).resolve() if db_path_str else ROOT_DIR / "db" / "bank.db"
        db_settings = DatabaseSettings(db_path=db_path)

        # 5. Logging
        log_level = (get_val("LOG_LEVEL") or "INFO").upper()
        if log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ConfigurationError(f"Invalid LOG_LEVEL: {log_level!r}")
        json_log = (get_val("JSON_LOGGING") or "false").lower() == "true" or env_profile in ("production", "prod")
        log_settings = LoggingSettings(level=log_level, json_logging=json_log)

        # 6. LLM
        llm_provider = (get_val("LLM_PROVIDER") or "anthropic").lower()
        if llm_provider != "anthropic":
            raise ConfigurationError(f"Unsupported LLM_PROVIDER={llm_provider!r}. Supported: anthropic.")
        llm_key = SecretStr(get_val("ANTHROPIC_API_KEY"))
        llm_model = get_val("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        llm_settings = LLMSettings(provider=llm_provider, api_key=llm_key, model=llm_model)

        # 7. Embedding
        voyage_key = SecretStr(get_val("VOYAGE_API_KEY"))
        emb_provider = "voyage" if voyage_key else "local"
        emb_settings = EmbeddingSettings(
            provider=emb_provider,
            voyage_api_key=voyage_key,
            voyage_model=get_val("VOYAGE_MODEL", "voyage-3.5"),
        )

        # 8. Observability
        ls_tracing = (get_val("LANGSMITH_TRACING") or "false").lower() in ("true", "1")
        ls_key = SecretStr(get_val("LANGSMITH_API_KEY") or get_val("LANGCHAIN_API_KEY"))
        ls_project = get_val("LANGSMITH_PROJECT") or get_val("LANGCHAIN_PROJECT") or "bank-assistant"
        ls_endpoint = get_val("LANGSMITH_ENDPOINT") or get_val("LANGCHAIN_ENDPOINT")
        obs_settings = ObservabilitySettings(
            enabled=ls_tracing and bool(ls_key),
            api_key=ls_key,
            project=ls_project,
            endpoint=ls_endpoint,
        )

        # 9. Orchestration
        orch_settings = OrchestrationSettings(
            high_confidence_threshold=float(get_val("ORCH_HIGH_CONF", 0.75)),
            medium_confidence_threshold=float(get_val("ORCH_MED_CONF", 0.50)),
            low_confidence_threshold=float(get_val("ORCH_LOW_CONF", 0.30)),
            fallback_threshold=float(get_val("ORCH_FALLBACK_CONF", 0.20)),
            max_fallback_attempts=int(get_val("ORCH_MAX_FALLBACKS", 2)),
            enable_multi_agent_collab=(get_val("ORCH_ENABLE_COLLAB", "true")).lower() == "true",
            max_context_tokens=int(get_val("ORCH_MAX_CTX_TOKENS", 3000)),
            max_history_turns=int(get_val("ORCH_MAX_HISTORY_TURNS", 10)),
            max_rag_chunks=int(get_val("ORCH_MAX_RAG_CHUNKS", 5)),
            max_memory_facts=int(get_val("ORCH_MAX_MEMORY_FACTS", 8)),
            supervisor_model=get_val("ORCH_SUPERVISOR_MODEL", "claude-haiku-4-5"),
        )

        # 10. MCP Platform
        dis_raw = get_val("MCP_DISABLED_SERVERS", "")
        pref_raw = get_val("MCP_PREFERRED_SERVERS", "")
        disabled_srvs = [s.strip() for s in dis_raw.split(",") if s.strip()]
        preferred_srvs = [s.strip() for s in pref_raw.split(",") if s.strip()]
        
        mcp_timeout = float(get_val("MCP_DEFAULT_TIMEOUT", 30.0))
        mcp_retry_delay = float(get_val("MCP_RETRY_DELAY", 1.0))
        if mcp_timeout <= 0 or mcp_retry_delay <= 0:
            raise ConfigurationError("MCP timeouts and retry delays must be positive numbers.")

        mcp_settings = MCPSettings(
            disabled_servers=disabled_srvs,
            preferred_servers=preferred_srvs,
            auto_discover=(get_val("MCP_AUTO_DISCOVER", "true")).lower() == "true",
            mcp_servers_dir=get_val("MCP_SERVERS_DIR", "mcp_servers"),
            default_timeout=mcp_timeout,
            max_retries=int(get_val("MCP_MAX_RETRIES", 2)),
            retry_delay=mcp_retry_delay,
            max_concurrent_tools=int(get_val("MCP_MAX_CONCURRENT", 3)),
            normalize_errors=(get_val("MCP_NORMALIZE_ERRORS", "true")).lower() == "true",
            min_confidence_for_mcp=float(get_val("MCP_MIN_CONFIDENCE", 0.60)),
            feed_results_to_memory=(get_val("MCP_FEED_MEMORY", "true")).lower() == "true",
            feed_results_to_prompt=(get_val("MCP_FEED_PROMPT", "true")).lower() == "true",
        )

        # 11. Memory
        mem_settings = MemorySettings(
            max_conversation_turns=int(get_val("MEMORY_MAX_TURNS", 50)),
            max_long_term_memories=int(get_val("MEMORY_MAX_LT", 200)),
            max_semantic_memories=int(get_val("MEMORY_MAX_SEMANTIC", 500)),
            max_context_tokens=int(get_val("MEMORY_MAX_CTX_TOKENS", 4000)),
            similarity_threshold=float(get_val("MEMORY_SIM_THRESHOLD", 0.35)),
            top_k_semantic=int(get_val("MEMORY_TOP_K_SEMANTIC", 5)),
            top_k_recency=int(get_val("MEMORY_TOP_K_RECENCY", 10)),
            top_k_context=int(get_val("MEMORY_TOP_K_CTX", 8)),
            summary_threshold_turns=int(get_val("MEMORY_SUMMARY_THRESHOLD", 20)),
            summary_max_tokens=int(get_val("MEMORY_SUMMARY_MAX_TOKENS", 600)),
            importance_weight=float(get_val("MEMORY_IMPORTANCE_W", 0.4)),
            recency_weight=float(get_val("MEMORY_RECENCY_W", 0.3)),
            relevance_weight=float(get_val("MEMORY_RELEVANCE_W", 0.3)),
            session_ttl_days=int(get_val("MEMORY_SESSION_TTL_DAYS", 90)),
            long_term_ttl_days=int(get_val("MEMORY_LT_TTL_DAYS", 365)),
            conversation_ttl_days=int(get_val("MEMORY_CONV_TTL_DAYS", 30)),
            recency_half_life_hours=float(get_val("MEMORY_HALF_LIFE_HOURS", 48.0)),
            chroma_collection_name=get_val("MEMORY_CHROMA_COLLECTION", "bank_memories"),
        )

        # 12. Evaluation
        eval_metrics_raw = get_val("EVAL_METRICS", "faithfulness,answer_relevancy,context_precision,context_recall")
        eval_metrics = [m.strip() for m in eval_metrics_raw.split(",") if m.strip()]
        eval_out_str = get_val("EVAL_OUTPUT_DIR")
        eval_out_dir = Path(eval_out_str).resolve() if eval_out_str else ROOT_DIR / "evaluation_reports"

        eval_settings = EvaluationSettings(
            metrics=eval_metrics,
            output_dir=eval_out_dir,
            model=get_val("EVAL_MODEL") or get_val("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
            batch_size=int(get_val("EVAL_BATCH_SIZE", "10")),
        )

        return cls(
            app=app_settings,
            deployment=dep_settings,
            security=sec_settings,
            database=db_settings,
            logging=log_settings,
            llm=llm_settings,
            embedding=emb_settings,
            observability=obs_settings,
            orchestration=orch_settings,
            mcp=mcp_settings,
            memory=mem_settings,
            evaluation=eval_settings,
        )


def _parse_rate_limit(val: str | None, default: tuple[int, int]) -> tuple[int, int]:
    """Internal helper to parse rate-limit strings."""
    if not val:
        return default
    try:
        parts = val.split(",")
        if len(parts) == 2:
            times, seconds = int(parts[0].strip()), int(parts[1].strip())
            if times > 0 and seconds > 0:
                return times, seconds
    except Exception:
        pass
    return default


# ── Global Settings Instance & Dynamic Proxy ───────────────────────────────────

class _SettingsProxy:
    """Dynamic proxy for AppConfig that evaluates the current environment on attribute access."""

    def __getattr__(self, name: str) -> Any:
        return getattr(AppConfig.load_from_env(), name)

    def to_dict(self, include_secrets: bool = False) -> dict[str, Any]:
        return AppConfig.load_from_env().to_dict(include_secrets=include_secrets)

    def get_fingerprint(self) -> str:
        return AppConfig.load_from_env().get_fingerprint()

    def get_startup_report(self) -> list[str]:
        return AppConfig.load_from_env().get_startup_report()


settings: Any = _SettingsProxy()


def reload_settings(env_overrides: dict[str, str] | None = None) -> AppConfig:
    """Reload the global settings singleton (used for tests or runtime configuration updates)."""
    return AppConfig.load_from_env(env_overrides)


# ── Backward Compatibility API Delegates ──────────────────────────────────────

def get_llm_config(provider: str | None = None) -> LLMProviderConfig:
    """Return the configured LLM provider without exposing raw secret values."""
    cfg = AppConfig.load_from_env()
    if provider and provider.lower() != cfg.llm.provider:
        raise ConfigurationError(
            f"Unsupported LLM_PROVIDER={provider!r}. Currently supported: {cfg.llm.provider}."
        )
    return LLMProviderConfig(
        provider=cfg.llm.provider,
        api_key=cfg.llm.api_key.get_secret_value() or None,
        model=cfg.llm.model,
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
    global _langsmith_initialized
    configure_logging()
    details: dict[str, str] = {}

    if not _langsmith_initialized:
        try:
            from observability.langsmith_config import configure_langsmith

            tracing_on = configure_langsmith()
            details["langsmith"] = "enabled" if tracing_on else "disabled"
        except Exception:
            LOGGER.debug("langsmith_init_skipped", exc_info=True)
            details["langsmith"] = "disabled"
        _langsmith_initialized = True

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


def get_allowed_origins() -> list[str]:
    """Expose the allowed origin list from central settings."""
    return AppConfig.load_from_env().security.allowed_origins


def get_rate_limit(env_var: str, default_times: int, default_seconds: int) -> tuple[int, int]:
    """Expose rate limits from central settings based on environment variable key."""
    cfg = AppConfig.load_from_env()
    if env_var == "RATE_LIMIT_CHAT":
        return cfg.security.rate_limit_chat
    if env_var == "RATE_LIMIT_VERIFY":
        return cfg.security.rate_limit_verify
    if env_var == "RATE_LIMIT_DEFAULT":
        return cfg.security.rate_limit_default
    return _parse_rate_limit(os.environ.get(env_var), (default_times, default_seconds))
