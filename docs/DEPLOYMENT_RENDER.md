# Render Cloud Deployment Guide

This guide details instructions for deploying the Autonomous Bank Assistant API and Streamlit UI services to [Render](https://render.com/).

---

## 1. Render Deployment Architecture

In Render, you will deploy **two separate services** from the same GitHub repository:
1. **FastAPI API**: Deployed as a **Web Service**.
2. **Streamlit UI**: Deployed as a **Web Service**.

---

## 2. API Service Configuration (Web Service)

- **Environment**: `Docker`
- **Dockerfile Path**: `docker/Dockerfile`
- **Docker Build Context**: `.` (Root directory)
- **Start Command**: Override default CMD to run the production API:
  ```bash
  python start.py worker --workers 2 --port 10000
  ```
- **Port**: `10000` (Render binds to environment variable `PORT` automatically; our startup script parses this, or you can explicitly bind it).

### Environment Variables Checklist
Set the following keys under the **Environment** tab:
| Variable | Value | Description |
| :--- | :--- | :--- |
| `ENV` | `production` | Enables strict production settings & structured JSON logs. |
| `ALLOWED_ORIGINS` | `https://your-streamlit-url.onrender.com` | Whitelist the Streamlit UI domain. |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | Trust Render's local proxy router. Defaults to local interface for security. |
| `ANTHROPIC_API_KEY` | `sk-ant-xxx` | Production LLM keys. |
| `VOYAGE_API_KEY` | `xxx` | Enable production semantic embeddings. |

### Health Checks settings
In the service **Advanced** settings, configure:
- **Health Check Path**: `/health/ready`
- **HTTP status code**: `200`

---

## 3. Streamlit UI Service Configuration (Web Service)

- **Environment**: `Docker`
- **Dockerfile Path**: `docker/Dockerfile`
- **Docker Build Context**: `.`
- **Start Command**: Allow default CMD (runs Streamlit on port 8501).

### Environment Variables Checklist
| Variable | Value | Description |
| :--- | :--- | :--- |
| `BANK_API_URL` | `https://your-api-url.onrender.com` | URL of the API service deployed above. |

---

## 4. Operational Trust Model & Reverse Proxy

Render routes traffic through a centralized load balancer proxy before reaching your container. 
- **Header Trust**: Render injects headers such as `X-Forwarded-For` and `X-Forwarded-Proto`.
- **IP-Rate limiting**: The application's `RateLimiter` reads the first IP in `X-Forwarded-For`.
- **Safety**: Ensure `FORWARDED_ALLOW_IPS` is configured to Render's forwarding proxy interface (default: `127.0.0.1` is trusted since Render proxies pass traffic locally to the container). Do **NOT** set it to `*` in production unless you are running behind custom proxy networks.

---

## 5. Deployment Validation Checklist

Before declaring the deployment live, verify the following:
- [ ] **HTTPS Enforced**: Check that connections are redirected to `https://`.
- [ ] **Startup Logs**: Confirm that the audit log shows `ENV=PRODUCTION` and lists the active whitelist origins.
- [ ] **Readiness status**: Query `https://your-api-url.onrender.com/health/ready` to ensure it reports `"status": "ready"`.
