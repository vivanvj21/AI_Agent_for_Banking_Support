#!/usr/bin/env python3
"""
Autonomous Bank Assistant — startup script.

Single entry point for every run mode. Replaces having to remember
the exact uvicorn / streamlit / python commands.

Usage:
    python start.py              # default: Streamlit UI
    python start.py streamlit    # Streamlit UI
    python start.py api          # FastAPI REST API
    python start.py cli          # Interactive CLI
    python start.py check        # Startup validation only (no server)
    python start.py init-db      # Initialize/seed the database, then exit
    python start.py worker       # API with multiple workers (production)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def _load_env() -> None:
    """Load .env if it exists. No hard dependency on python-dotenv."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    try:
        # Try python-dotenv if available
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(env_file, override=False)
        return
    except ImportError:
        pass
    # Manual fallback: parse key=value lines
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _python() -> str:
    return sys.executable


def run_streamlit(port: int = 8501) -> None:
    print(f"\n[Streamlit] Starting UI on http://localhost:{port}\n")
    cmd = [
        _python(),
        "-m",
        "streamlit",
        "run",
        "app_streamlit.py",
        f"--server.port={port}",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]
    subprocess.run(cmd, cwd=ROOT)


def run_api(port: int = 8000, workers: int = 1, reload: bool = False) -> None:
    print(f"\n[API] Starting FastAPI on http://localhost:{port}")
    print(f"   Docs: http://localhost:{port}/docs\n")
    cmd = [
        _python(),
        "-m",
        "uvicorn",
        "api.main:app",
        "--host",
        "0.0.0.0",
        f"--port={port}",
        f"--workers={workers}",
        "--log-level",
        os.environ.get("LOG_LEVEL", "info").lower(),
    ]
    if reload:
        cmd.append("--reload")
    subprocess.run(cmd, cwd=ROOT)


def run_cli() -> None:
    print("\n[CLI] Starting interactive CLI...\n")
    subprocess.run([_python(), "cli.py"], cwd=ROOT)


def run_check() -> None:
    print("\n[CHECK] Running startup validation...\n")
    subprocess.run([_python(), "cli.py", "--check-startup"], cwd=ROOT)


def run_init_db() -> None:
    print("\n[DB] Initializing database...\n")
    code = (
        "from db.init_db import ensure_database; "
        "from memory.store import ensure_memory_schema; "
        "r = ensure_database(seed_demo_data=True); "
        "ensure_memory_schema(); "
        "print('Database ready:', r)"
    )
    subprocess.run([_python(), "-c", code], cwd=ROOT)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Autonomous Bank Assistant — unified startup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  streamlit   Streamlit web UI           (default, port 8501)
  api         FastAPI REST API           (port 8000)
  cli         Interactive terminal chat
  check       Startup validation check
  init-db     Initialize/seed database
  worker      FastAPI multi-worker mode  (production)

Examples:
  python start.py
  python start.py api
  python start.py api --port 9000 --reload
  python start.py worker --workers 4
        """,
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="streamlit",
        choices=["streamlit", "api", "cli", "check", "init-db", "worker"],
    )
    parser.add_argument("--port", type=int, default=None, help="Override default port")
    parser.add_argument(
        "--workers", type=int, default=None, help="Uvicorn worker count"
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload (dev)"
    )
    return parser.parse_args()


def main() -> None:
    _load_env()
    args = _parse_args()

    mode = args.mode

    if mode == "streamlit":
        port = args.port or int(os.environ.get("STREAMLIT_PORT", 8501))
        run_streamlit(port=port)

    elif mode == "api":
        port = args.port or int(os.environ.get("API_PORT", 8000))
        run_api(port=port, workers=1, reload=args.reload)

    elif mode == "worker":
        port = args.port or int(os.environ.get("API_PORT", 8000))
        workers = args.workers or int(os.environ.get("API_WORKERS", 2))
        run_api(port=port, workers=workers, reload=False)

    elif mode == "cli":
        run_cli()

    elif mode == "check":
        run_check()

    elif mode == "init-db":
        run_init_db()


if __name__ == "__main__":
    main()
