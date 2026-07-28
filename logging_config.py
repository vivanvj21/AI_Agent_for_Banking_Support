"""Application logging configuration."""

from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"
LOG_FILE = LOG_DIR / "bank_assistant.log"

_CONFIGURED = False


class JSONFormatter(logging.Formatter):
    """Structured JSON logging formatter for production log parsing.

    Filters out standard LogRecord attributes to capture custom extra parameters.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Capture custom extra properties passed via extra={...}
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "asctime", "extra"
        }
        for k, v in record.__dict__.items():
            if k not in standard_attrs:
                log_data[k] = v

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


def configure_logging(level: int = logging.INFO) -> None:
    """Configure console + rotating-file logging once per process.

    Uses structured JSON logs in production, and standard formatted text in development.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from config import settings
        env = settings.app.env.lower()
        json_logging = settings.logging.json_logging
    except Exception:
        env = os.environ.get("ENV", "development").lower()
        json_logging = os.environ.get("JSON_LOGGING", "false").lower() == "true"

    if env in ("production", "prod") or json_logging:
        formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%SZ")
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )

    root = logging.getLogger()
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    _CONFIGURED = True
