# Centralized Configuration & Secrets Architecture

This document provides a comprehensive technical overview of the production-grade configuration system and secret management architecture implemented in Step D.

---

## 1. Architecture Overview

The system establishes a **single authoritative source of truth** for all application settings, deployment options, component thresholds, and credentials. 

Direct calls to `os.environ` or `os.getenv()` inside business logic are strictly prohibited. All components query the centralized `settings` container exposed by `config.py`.

```
                       ┌─────────────────────────────────────┐
                       │  Environment / .env / OS Defaults   │
                       └──────────────────┬──────────────────┘
                                          │
                                          ▼
                       ┌─────────────────────────────────────┐
                       │     AppConfig.load_from_env()       │
                       │   (Validation & Secret Wrapping)    │
                       └──────────────────┬──────────────────┘
                                          │
                                          ▼
                       ┌─────────────────────────────────────┐
                       │      Global `settings` Singleton    │
                       └──────────────────┬──────────────────┘
                                          │
           ┌──────────────────────────────┼──────────────────────────────┐
           ▼                              ▼                              ▼
┌────────────────────┐         ┌────────────────────┐         ┌────────────────────┐
│   FastAPI / CLI    │         │ Multi-Agent Graph  │         │  MCP Platform /    │
│  (CORS, Ports, IP) │         │ (Thresholds, LLM)  │         │   Memory Engine    │
└────────────────────┘         └────────────────────┘         └────────────────────┘
```

---

## 2. Configuration Domains (Sub-settings)

Configuration parameters are partitioned into 12 domain-specific dataclasses:

| Domain Sub-Class | Responsibility |
| :--- | :--- |
| `AppSettings` | Application metadata (`name`, `version`, `env` profile). |
| `DeploymentSettings` | Network ports (`port_streamlit`, `port_api`), uvicorn worker count, trusted proxy IPs (`forwarded_allow_ips`). |
| `SecuritySettings` | Allowed CORS origins list, rate-limiting limits for `/chat`, `/verify`, and default endpoints. |
| `DatabaseSettings` | SQLite database file paths (`db_path`) and timeout parameters. |
| `LoggingSettings` | Logging level (`level`), JSON formatting flag (`json_logging`). |
| `LLMSettings` | Provider selection (`anthropic`), API keys wrapped in `SecretStr`, model identifier (`claude-sonnet-4-5`). |
| `EmbeddingSettings` | Provider selection (`local` vs `voyage`), Voyage API keys wrapped in `SecretStr`, Voyage model. |
| `ObservabilitySettings` | LangSmith tracing flags, API keys wrapped in `SecretStr`, project name. |
| `OrchestrationSettings` | Confidence thresholds (`ORCH_HIGH_CONF`), context token limits, fallback limits. |
| `MCPSettings` | Auto-discovery flags, timeouts, retries, disabled/preferred server lists. |
| `MemorySettings` | Recency/importance weights, conversation turn TTLs, Chroma collection name. |
| `EvaluationSettings` | Metrics list, output directories, evaluation batch sizes. |

---

## 3. Secret Management & Redaction Strategy

To prevent credentials leakage in logs, error stack traces, UI displays, or startup banners:

1. **`SecretStr` Wrapper**: All sensitive fields (`ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `LANGSMITH_API_KEY`) are stored as instances of `SecretStr`.
2. **Automatic Redaction**: Calling `str(secret)` or `repr(secret)` automatically masks the value (e.g. `sk-ant-***************`).
3. **Authorized Retrieval**: Business code calls `secret.get_secret_value()` explicitly when sending headers to external APIs.
4. **Serialization Safety**: `settings.to_dict(include_secrets=False)` automatically redacts all credentials during dictionary conversion.

---

## 4. Deterministic Loading Hierarchy

Settings are loaded in a strict, predictable order:

1. **Internal Defaults**: Hardcoded safe fallbacks defined inside dataclass field constructors.
2. **Environment Variables**: Overrides from `.env` or system environment variables.
3. **Runtime Overrides**: Programmatic dictionary overrides passed to `AppConfig.load_from_env(env_overrides)` (primarily for testing and mock runs).

---

## 5. Configuration Fingerprint

To detect configuration drift across deployments without exposing credentials:
- `settings.get_fingerprint()` generates a **SHA-256 hash** over the non-sensitive configuration parameters.
- Changing ports, rate limits, or environment profiles updates the hash.
- Credentials and API keys are excluded from the hash payload.

---

## 6. Future Enterprise Secret Providers Architecture

The architecture is designed to support external secret management systems (e.g. HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, Google Secret Manager) without breaking business logic.

To integrate a secret provider in the future:
1. Implement a `SecretProvider` interface with a `.fetch_secret(key_name: str) -> str` method.
2. Plug the provider into `AppConfig.load_from_env()` prior to initializing `SecretStr` fields:
   ```python
   # Future Vault extension example:
   if get_val("VAULT_ADDR"):
       vault_client = VaultSecretProvider(addr=get_val("VAULT_ADDR"))
       anthropic_key = SecretStr(vault_client.fetch_secret("ANTHROPIC_API_KEY"))
   ```
3. Business logic remains untouched because it consumes `settings.llm.api_key.get_secret_value()`.
