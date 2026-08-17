"""
Structured JSON Audit Logger for Compliance & Security Event Tracking.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

LOGGER = logging.getLogger("security.audit")


def log_audit_event(
    event_type: str,
    user_id: str | None = None,
    session_id: str | None = None,
    ip_address: str | None = None,
    status: str = "success",
    details: dict[str, Any] | None = None,
) -> None:
    """Record a structured JSON security audit log event."""
    audit_record = {
        "@timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "user_id": user_id or "anonymous",
        "session_id": session_id or "none",
        "ip_address": ip_address or "unknown",
        "status": status,
        "details": details or {},
    }
    LOGGER.info(json.dumps(audit_record))
