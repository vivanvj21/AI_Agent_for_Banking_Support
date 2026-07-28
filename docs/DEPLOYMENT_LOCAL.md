# Local Docker & Compose Deployment Guide

This guide details the instructions for launching, validating, and testing the Autonomous Bank Assistant in local container environments using Docker and Docker Compose.

---

## 1. Local Configuration Setup

Before running the container, configure your local environment settings. Create a `.env` file at the root of the project:
```bash
# Core Environment settings
ENV=development
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8501

# LLM Config
ANTHROPIC_API_KEY=sk-ant-your-key-here
LLM_PROVIDER=anthropic
```

---

## 2. Running with Docker Compose

We provide a production-grade multi-container configurations template in `docker-compose.yml` to launch both the Streamlit UI and the FastAPI REST API.

### Build and Launch
To build and start the services in the background:
```bash
docker-compose up --build -d
```

### View Status
Verify that the containers are running and healthy:
```bash
docker-compose ps
```

### Tail logs
```bash
docker-compose logs -f
```

---

## 3. Launching Standalone Containers via Docker CLI

To run the containers manually without docker-compose:

### 1. Build the lean runtime image
```bash
docker build -f docker/Dockerfile -t bank-assistant:1.0.0 .
```

### 2. Launch the FastAPI API server
```bash
docker run -d \
  --name bank-api \
  -p 8000:8000 \
  -e ENV=development \
  -e ANTHROPIC_API_KEY=sk-ant-your-key-here \
  bank-assistant:1.0.0 \
  python start.py api
```

---

## 4. Signal Handling & Graceful Shutdown

Uvicorn handles process signals (`SIGTERM` and `SIGINT`) gracefully:
- **SIGTERM / SIGINT**: Uvicorn halts accepting new requests, waits for in-flight requests to complete under a timeout, triggers the FastAPI lifespan shutdown context, and terminates child processes safely.
- **MCP state safety**: Since MCP tool executions are stateless (opening/closing a process per call), there are no hanging child processes to clean up on server termination.
- **DB/Chroma locks**: SQLite database handles connections on a query-basis (closing connections immediately after transactions). On container termination, no file locks are kept active.

To trigger graceful shutdown locally:
```bash
docker stop bank-api
```

---

## 5. End-to-End Smoke Test Checklist

After launching:
1. **Health Verification**:
   Query the liveness and readiness endpoints:
   ```bash
   curl -i http://localhost:8000/health/live
   curl -i http://localhost:8000/health/ready
   # Expected status code: 200 OK
   ```
2. **CORS Restrictions**:
   Verify an untrusted Origin is blocked:
   ```bash
   curl -i -H "Origin: https://attacker.com" -H "Access-Control-Request-Method: POST" -X OPTIONS http://localhost:8000/chat
   # Expected: Header Access-Control-Allow-Origin is absent
   ```
3. **Rate Limiting**:
   Flood `/verify` to trigger `429 Too Many Requests`:
   ```bash
   for i in {1..6}; do
     curl -i -X POST http://localhost:8000/verify -H "Content-Type: application/json" -d '{"session_id": "", "user_id": "U1001", "pin": "1111"}'
   done
   # Expected: The 6th request returns 429 with a Retry-After header.
   ```
