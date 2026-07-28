# Railway Deployment Guide

This guide details instructions for deploying the Autonomous Bank Assistant API and Streamlit UI services to [Railway](https://railway.app/).

---

## 1. Service Definition

In Railway, add your GitHub repository to a project. Create **two separate services** in the Railway builder interface:
1. **bank-api** (FastAPI backend service).
2. **bank-streamlit** (Streamlit web dashboard UI).

---

## 2. API Service Configuration (bank-api)

- **Builder**: `Dockerfile`
- **Dockerfile Path**: `docker/Dockerfile`
- **Start Command**:
  ```bash
  python start.py worker --workers 2 --port 8000
  ```
- **Port Variable**: Railway automatically maps traffic to the exposed port or reads `PORT` (defaults to `8000`).

### Environment Variables Checklist
Define these in the **Variables** tab of the service:
| Variable | Value | Description |
| :--- | :--- | :--- |
| `ENV` | `production` | Enforces production logs & configuration validation. |
| `ALLOWED_ORIGINS` | `${{bank-streamlit.RAILWAY_STATIC_URL}}` | Automatically whitelist the Streamlit service URL using Railway variable referencing. |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | Trust local proxy forwarding headers. |
| `ANTHROPIC_API_KEY` | `sk-ant-xxx` | Production LLM credentials. |
| `VOYAGE_API_KEY` | `xxx` | Enable Voyage embeddings. |

### Health Checks Settings
Under the **Settings** tab in Railway:
- **Health Check Path**: `/health/ready`
- **Health Check Port**: `8000`

---

## 3. Streamlit UI Service Configuration (bank-streamlit)

- **Builder**: `Dockerfile`
- **Dockerfile Path**: `docker/Dockerfile`
- **Start Command**: Allow default CMD (runs Streamlit on port 8501).

### Environment Variables Checklist
| Variable | Value | Description |
| :--- | :--- | :--- |
| `BANK_API_URL` | `${{bank-api.RAILWAY_STATIC_URL}}` | Points to the API service dynamically. |

---

## 4. Operational Trust Model & Reverse Proxy

Railway routes traffic through an edge proxy before delivering it to your containers:
- **Proxy Headers**: Injects standard forwarding headers like `X-Forwarded-For` and `X-Forwarded-Proto`.
- **IP Extraction**: The API extracts client IPs from the first token in `X-Forwarded-For`.
- **Safety**: Do **NOT** set `FORWARDED_ALLOW_IPS` to `*` (wildcard) in production unless you are running behind a custom proxy VPC. Trusting only local loopback interfaces (`127.0.0.1`) prevents header injection from direct API endpoints requests.

---

## 5. Deployment Validation Checklist

Before declaring the deployment live, verify the following:
- [ ] **HTTPS Enforced**: Confirm access is routed via HTTPS.
- [ ] **Startup Logs**: Check the logs to ensure structured JSON formatting is activated and CORS whitelist matches the Streamlit host.
- [ ] **Readiness Check**: Query `https://your-api-url.railway.app/health/ready` to ensure it reports `"status": "ready"`.
