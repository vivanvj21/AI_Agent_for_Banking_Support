"""
Pydantic request/response models for the FastAPI layer.

These are pure I/O shapes — they carry no business logic. Every field maps
directly onto arguments already accepted by graph.py / tools/*.py functions.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# /chat
# ---------------------------------------------------------------------------


class AuthInput(BaseModel):
    user_id: str = Field(..., description="e.g. 'U1002'")
    pin: str = Field(..., min_length=4, max_length=4, description="4-digit PIN")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user's chat message.")
    session_id: str | None = Field(
        None,
        description=(
            "Existing session_id to continue a conversation. Omit to start a "
            "new session (same behavior as cli.py with no --resume flag)."
        ),
    )
    channel: str = Field("api", description="Channel label stored on the session row.")
    auth: AuthInput | None = Field(
        None, description="Structured authentication credentials if requested."
    )


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: str | None = None
    verified: bool
    user_id: str | None = None
    turn: int
    end_session: bool = False
    tool_calls_log: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# /verify
# ---------------------------------------------------------------------------


class VerifyRequest(BaseModel):
    user_id: str = Field(..., description="e.g. 'U1002'")
    pin: str = Field(..., min_length=4, max_length=4, description="4-digit PIN")
    session_id: str | None = Field(
        None,
        description=(
            "If provided, this session is linked to the verified user (same "
            "effect as verify_gate succeeding inside /chat). If omitted, a "
            "new session is created and linked."
        ),
    )


class VerifyResponse(BaseModel):
    verified: bool
    user_id: str | None = None
    first_name: str | None = None
    session_id: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# /account/*
# ---------------------------------------------------------------------------


class BalanceRequest(BaseModel):
    session_id: str = Field(
        ..., description="A session_id previously verified via /verify or /chat."
    )
    account_id: str | None = Field(
        None, description="Specific account. Omit for all accounts."
    )


class BalanceResponse(BaseModel):
    accounts: list[dict[str, Any]] | None = None
    account_id: str | None = None
    account_type: str | None = None
    balance_paise: int | None = None
    balance: float | None = None
    balance_formatted: str | None = None
    currency: str | None = None
    error: str | None = None


class HistoryRequest(BaseModel):
    session_id: str
    account_id: str | None = None
    limit: int = Field(10, ge=1, le=100)


class HistoryResponse(BaseModel):
    transactions: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


# ---------------------------------------------------------------------------
# /fraud/*
# ---------------------------------------------------------------------------


class LockCardRequest(BaseModel):
    session_id: str
    card_id: str


class LockCardResponse(BaseModel):
    status: str | None = None
    card_id: str | None = None
    error: str | None = None


class ReportFraudRequest(BaseModel):
    session_id: str
    transaction_id: str
    reason: str = ""


class ReportFraudResponse(BaseModel):
    status: str | None = None
    transaction_id: str | None = None
    reported_at: str | None = None
    note: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# /faq/search
# ---------------------------------------------------------------------------


class FaqSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    k: int = Field(3, ge=1, le=10)
    source: str | None = None


class FaqSearchResponse(BaseModel):
    results: list[dict[str, Any]] = Field(default_factory=list)
    warning: str | None = None


# ---------------------------------------------------------------------------
# /health, /metrics
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    ok: bool
    message: str
    details: dict[str, str] = Field(default_factory=dict)


class MetricsResponse(BaseModel):
    uptime_seconds: float
    request_counts: dict[str, int]
    average_latency_ms: dict[str, float]
