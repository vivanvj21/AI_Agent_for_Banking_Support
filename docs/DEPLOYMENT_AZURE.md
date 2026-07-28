# Azure App Service Deployment Guide

This guide details instructions for deploying the Autonomous Bank Assistant API and Streamlit UI services to [Microsoft Azure App Service](https://azure.microsoft.com/en-us/products/app-service/) as Web Apps.

---

## 1. Azure App Service Setup

You will deploy two Linux-based Web Apps using Docker Containers:
1. **bank-api** (FastAPI backend service).
2. **bank-streamlit** (Streamlit web dashboard UI).

---

## 2. API Service Configuration (bank-api)

### 1. Resource Settings
- **Publish**: `Docker Container`
- **Operating System**: `Linux`
- **Plan**: Select a production-grade Linux App Service Plan (e.g. `B1` or `P1v3`).

### 2. Docker Container Settings
- **Options**: `Single Container`
- **Image Source**: `Azure Container Registry` (ACR) or `Docker Hub` (where your built image is pushed).
- **Image and Tag**: `bank-assistant:1.0.0`
- **Startup Command**: Override the default startup command:
  ```bash
  python start.py worker --workers 2 --port 8000
  ```

### 3. Application Settings (Configuration tab)
Define these key-value pairs in the **Configuration** panel:
| Name | Value | Description |
| :--- | :--- | :--- |
| `ENV` | `production` | Enforces production configurations & JSON logging. |
| `ALLOWED_ORIGINS` | `https://your-streamlit-app.azurewebsites.net` | Whitelist the Streamlit UI domain. |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | Trust local proxy forwarding headers. |
| `WEBSITES_PORT` | `8000` | Instructs Azure App Service to route container traffic to port `8000`. |
| `ANTHROPIC_API_KEY` | `sk-ant-xxx` | Production LLM credentials. |
| `VOYAGE_API_KEY` | `xxx` | Voyage embeddings. |

---

## 3. Streamlit UI Service Configuration (bank-streamlit)

- **Publish**: `Docker Container`
- **Operating System**: `Linux`
- **Startup Command**: Keep default (runs Streamlit on port `8501`).
- **Application Settings**:
  - `WEBSITES_PORT`: `8501`
  - `BANK_API_URL`: `https://your-api-app.azurewebsites.net` (URL of the deployed backend service).

---

## 4. Operational Trust Model & Reverse Proxy

Azure App Service runs containers behind an internal front-end load balancer:
- **Proxy Headers**: Injects headers such as `X-Forwarded-For` and `X-Forwarded-Proto`.
- **IP Extraction**: The API extracts client IPs from the first token in `X-Forwarded-For`.
- **Safety**: Do **NOT** set `FORWARDED_ALLOW_IPS` to `*` (wildcard) in production unless you are running behind a custom proxy VPC. Trusting only local loopback interfaces (`127.0.0.1`) prevents header injection from direct API endpoints requests.

---

## 5. Health Checks Settings
In the App Service **Health check** configuration menu:
- Enable health check.
- **Path**: `/health/ready`
- **Max time to live**: `10 minutes` (minimum standard).

---

## 6. Deployment Validation Checklist

Before declaring the deployment live, verify the following:
- [ ] **HTTPS Redirect**: Go to the **TLS/SSL settings** tab and ensure **HTTPS Only** is set to `On`.
- [ ] **Startup Logs**: Check the **Log stream** logs to ensure structured JSON formatting is activated.
- [ ] **Readiness Check**: Query `https://your-api-app.azurewebsites.net/health/ready` to ensure it reports `"status": "ready"`.
