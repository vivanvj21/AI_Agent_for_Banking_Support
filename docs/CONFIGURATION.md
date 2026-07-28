# Environment Configuration Reference

This guide provides a comprehensive list of environment variables used to configure the Autonomous Bank Assistant.

---

## 1. Environment & Server Settings

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ENV` | `development` | Environment profile (`development`, `staging`, `production`, `testing`). |
| `STREAMLIT_PORT` | `8501` | Network port for the Streamlit UI dashboard. |
| `API_PORT` | `8000` | Network port for the FastAPI REST API. |
| `API_WORKERS` | `2` | Number of Uvicorn worker processes in production mode. |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | Trusted proxy IP addresses for reverse proxies. |
| `LOG_LEVEL` | `INFO` | Logging output level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `JSON_LOGGING` | `false` | Enable structured JSON logging format (enabled by default in `production`). |

---

## 2. Credentials & LLM Settings

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ANTHROPIC_API_KEY` | `""` | Anthropic Claude API Key (wrapped securely in `SecretStr`). |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-5` | Primary agent LLM model identifier. |
| `VOYAGE_API_KEY` | `""` | Voyage AI API Key for production embeddings. |
| `VOYAGE_MODEL` | `voyage-3.5` | Voyage embeddings model identifier. |
| `LANGSMITH_TRACING` | `false` | Enable LangSmith observability tracing. |
| `LANGSMITH_API_KEY` | `""` | LangSmith API Key. |

---

## 3. Security & Rate Limiting

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ALLOWED_ORIGINS` | *(dev defaults)* | Comma-separated list of whitelisted CORS origins. Wildcard `*` is prohibited. |
| `RATE_LIMIT_CHAT` | `10,60` | `/chat` rate limit (requests, seconds). |
| `RATE_LIMIT_VERIFY` | `5,60` | `/verify` rate limit (requests, seconds). |
| `RATE_LIMIT_DEFAULT` | `15,60` | General endpoints rate limit (requests, seconds). |

---

## 4. Multi-Agent & Orchestration Settings

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ORCH_HIGH_CONF` | `0.75` | High confidence routing threshold. |
| `ORCH_MED_CONF` | `0.50` | Medium confidence routing threshold. |
| `ORCH_LOW_CONF` | `0.30` | Low confidence routing threshold. |
| `ORCH_SUPERVISOR_MODEL` | `claude-haiku-4-5` | Lightweight classification model identifier. |

---

## 5. Secret Protection Guidelines

- **Never hardcode secrets** in source code files or test files.
- All secrets are wrapped in `SecretStr` instances and automatically redacted in logs and error tracebacks.
- Use `.env` files for local development and secret managers (Render Environment Variables, Railway Variables, Azure Key Vault) in cloud environments.
