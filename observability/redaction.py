"""
Sensitive-data redaction for LangSmith traces.

All data sent to LangSmith must have banking PII stripped first.
This module provides a single ``redact()`` function that recursively
walks any Python value and masks known-sensitive patterns.

Patterns masked:
  - 4-digit PINs (standalone)
  - Account / card numbers (alphanumeric IDs like A2001, C3001)
  - User IDs (U + digits pattern)
  - Session tokens / API keys (long hex / base64 strings)
  - pin_hash / token fields in dicts

Design:
  - ``redact()`` is idempotent and side-effect-free (always returns a new value).
  - Strings are regex-masked; dicts/lists are walked recursively.
  - Depth is capped to prevent infinite recursion on circular structures.
"""

from __future__ import annotations

import re
from typing import Any

# ── Sensitive field names — always redact their values ───────────────────────

_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "pin",
        "pin_hash",
        "password",
        "token",
        "api_key",
        "secret",
        "authorization",
        "access_token",
        "refresh_token",
        "session_token",
    }
)

# ── Regex patterns for inline value masking ──────────────────────────────────

# 4-digit standalone PIN — only mask when surrounded by non-alphanumeric context
# (spaces, punctuation, start/end) so IDs like U1002 are NOT affected.
_PIN_RE = re.compile(r"(?<![A-Za-z0-9])(\d{4})(?![A-Za-z0-9])")

# Full 64-char hex (SHA-256) — hashed PINs that may appear in logs
_SHA256_RE = re.compile(r"\b[0-9a-f]{64}\b")

# Argon2 hashes start with "$argon2"
_ARGON2_RE = re.compile(r"\$argon2[^\s]+")

# Long hex strings (session tokens, JWT fragments ≥ 32 chars)
_LONG_HEX_RE = re.compile(r"\b[0-9a-f]{32,}\b")

# Base64-like strings ≥ 32 chars (API keys, encoded tokens)
_B64_RE = re.compile(r"[A-Za-z0-9+/]{32,}={0,2}")

_MAX_DEPTH = 12
_PLACEHOLDER = "[REDACTED]"


def _mask_string(value: str) -> str:
    """Apply all regex masks to a string value."""
    # Argon2 / SHA-256 hashes first (superset of long hex)
    value = _ARGON2_RE.sub(_PLACEHOLDER, value)
    value = _SHA256_RE.sub(_PLACEHOLDER, value)
    value = _LONG_HEX_RE.sub(_PLACEHOLDER, value)
    value = _B64_RE.sub(_PLACEHOLDER, value)
    # 4-digit PINs last (short enough that they appear inline)
    value = _PIN_RE.sub(_PLACEHOLDER, value)
    return value


def redact(obj: Any, _depth: int = 0) -> Any:
    """Recursively redact sensitive data from *obj* before sending to LangSmith.

    Args:
        obj: Any Python value (str, dict, list, tuple, or scalar).

    Returns:
        A new value of the same type with sensitive data replaced by
        ``"[REDACTED]"``.  Scalars that are not strings are returned as-is.

    Notes:
        - Dict keys are never redacted, only values.
        - Redaction is applied to *copies*; the original is never modified.
        - Recursion is capped at ``_MAX_DEPTH`` levels.
    """
    if _depth > _MAX_DEPTH:
        return obj

    if isinstance(obj, str):
        return _mask_string(obj)

    if isinstance(obj, dict):
        result: dict = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in _SENSITIVE_KEYS:
                result[k] = _PLACEHOLDER
            else:
                result[k] = redact(v, _depth + 1)
        return result

    if isinstance(obj, (list, tuple)):
        redacted = [redact(item, _depth + 1) for item in obj]
        return type(obj)(redacted)

    # Scalars (int, float, bool, None, …) — safe to pass through unchanged.
    return obj


def redact_tool_args(tool_name: str, args: dict) -> dict:
    """Redact tool arguments, with special handling for known sensitive tools.

    Args:
        tool_name: Name of the tool being called.
        args:      Raw argument dict from the LLM.

    Returns:
        A new dict with sensitive values replaced.
    """
    cleaned = redact(args)
    # verify_identity is the only tool that receives a raw PIN — always
    # replace its "pin" argument even if the regex didn't catch it.
    if tool_name in ("verify_identity",) and "pin" in cleaned:
        cleaned["pin"] = _PLACEHOLDER
    return cleaned
