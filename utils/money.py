"""
Centralized Money Conversion and Formatting Utility (Step E — Fixed-Point Money Storage).

Provides exact, deterministic monetary conversions between Rupees (Decimal/float/string)
and integer minor units (paise/cents). Prevents IEEE 754 floating-point arithmetic errors.

Rules:
  - All database fields and internal calculations consume integer paise.
  - to_paise uses Decimal arithmetic with ROUND_HALF_UP.
  - format_currency outputs human-friendly representations (e.g. "₹1,234.56").
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

PAISE_PER_RUPEE = 100


def to_paise(val: int | float | str | Decimal | None) -> int:
    """
    Convert a monetary value (Rupees) into integer minor units (paise).

    Handles boundary rounding cleanly using Decimal ROUND_HALF_UP:
      - to_paise(12.34) -> 1234
      - to_paise("1.005") -> 101
      - to_paise("-1.005") -> -101
      - to_paise(None) -> 0 (fail-safe fallback)
    """
    if val is None:
        return 0
    if isinstance(val, int):
        # Integer values passed directly are assumed to be Rupees
        val = str(val)
    try:
        # Convert float/str/Decimal via Decimal string representation to avoid float drift
        d = Decimal(str(val))
        paise = (d * PAISE_PER_RUPEE).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return int(paise)
    except Exception:
        # Fail-safe default for corrupted/unexpected non-numeric legacy data
        return 0


def paise_to_rupees(paise: int) -> float:
    """Convert integer paise back to float Rupees for legacy API backward compatibility."""
    if not isinstance(paise, int):
        try:
            paise = int(paise)
        except Exception:
            return 0.0
    return float((Decimal(paise) / Decimal(PAISE_PER_RUPEE)).quantize(Decimal("0.01")))


def paise_to_decimal(paise: int) -> Decimal:
    """Convert integer paise to exact Decimal Rupees."""
    if not isinstance(paise, int):
        try:
            paise = int(paise)
        except Exception:
            return Decimal("0.00")
    return (Decimal(paise) / Decimal(PAISE_PER_RUPEE)).quantize(Decimal("0.01"))


def format_currency(paise: int, currency: str = "INR", symbol: bool = True) -> str:
    """
    Format integer paise into a human-friendly string.

    Examples:
      - format_currency(1542050) -> "₹15,420.50"
      - format_currency(-5000) -> "-₹50.00"
      - format_currency(1000, currency="USD") -> "$10.00"
    """
    if not isinstance(paise, int):
        try:
            paise = int(paise)
        except Exception:
            paise = 0

    is_negative = paise < 0
    abs_paise = abs(paise)
    rupees = Decimal(abs_paise) / Decimal(PAISE_PER_RUPEE)
    formatted_val = f"{rupees:,.2f}"

    prefix = "-" if is_negative else ""
    if not symbol:
        return f"{prefix}{formatted_val}"

    if currency.upper() == "INR":
        sym = "₹"
    elif currency.upper() == "USD":
        sym = "$"
    elif currency.upper() == "EUR":
        sym = "€"
    elif currency.upper() == "GBP":
        sym = "£"
    else:
        sym = f"{currency} "

    return f"{prefix}{sym}{formatted_val}"
