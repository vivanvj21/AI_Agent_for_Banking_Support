"""
Input Sanitization, XSS Prevention, and Prompt Injection Defense Heuristics.
"""

from __future__ import annotations

import html
import re
from typing import Tuple

# Prominent prompt injection attack patterns
_PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+all\s+prior\s+prompts", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
    re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"act\s+as\s+an\s+unrestricted\s+ai", re.IGNORECASE),
]


def sanitize_input_text(text: str) -> str:
    """Escape HTML entities to prevent stored/reflected XSS."""
    if not text:
        return ""
    return html.escape(text.strip())


def detect_prompt_injection(text: str) -> Tuple[bool, str]:
    """
    Scans input for prompt injection heuristics.
    Returns: (is_injection_detected: bool, matching_pattern: str)
    """
    if not text:
        return False, ""

    for pattern in _PROMPT_INJECTION_PATTERNS:
        if pattern.search(text):
            return True, pattern.pattern

    return False, ""
