"""
Production Gunicorn Configuration for FastAPI ASGI deployment.

Usage:
    gunicorn -c gunicorn.conf.py api.main:app
"""

import multiprocessing
import os

# Server socket
bind = os.getenv("BIND", "0.0.0.0:8000")
backlog = 2048

# Worker processes
workers_per_core_str = os.getenv("WORKERS_PER_CORE", "2.0")
workers_per_core = float(workers_per_core_str)
default_web_concurrency = workers_per_core * multiprocessing.cpu_count() + 1
workers = int(os.getenv("WEB_CONCURRENCY", str(int(default_web_concurrency))))

# Worker class for FastAPI / Uvicorn ASGI
worker_class = "uvicorn.workers.UvicornWorker"

# Worker lifecycle & recycling
max_requests = int(os.getenv("MAX_REQUESTS", "1000"))
max_requests_jitter = int(os.getenv("MAX_REQUESTS_JITTER", "50"))
timeout = int(os.getenv("TIMEOUT", "120"))
graceful_timeout = int(os.getenv("GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("KEEPALIVE", "5"))

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()

# Server mechanics
preload_app = False
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None


def on_starting(server):
    server.log.info("gunicorn_master_starting", extra={"bind": bind, "workers": workers})


def on_exit(server):
    server.log.info("gunicorn_master_exiting")
