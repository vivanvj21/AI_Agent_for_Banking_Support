"""
Pydantic request/response models for the FastAPI layer.

These are pure I/O shapes — they carry no business logic. Every field maps
directly onto arguments already accepted by graph.py / tools/*.py functions.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# /chat
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user's chat message.")
    session_id: Optional[str] = Field(
        None,
        description=(
            "Existing session_id to continue a conversation. Omit to start a "
            "new session (same behavior as cli.py with no --resume flag)."
        ),
    )
    channel: str = Field("api", description="Channel label stored on the session row.")


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: Optional[str] = None
    verified: bool
    user_id: Optional[str] = None
    turn: int
    end_session: bool = False
    tool_calls_log: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# /verify
# ---------------------------------------------------------------------------


class VerifyRequest(BaseModel):
    user_id: str = Field(..., description="e.g. 'U1002'")
    pin: str = Field(..., min_length=4, max_length=4, description="4-digit PIN")
    session_id: Optional[str] = Field(
        None,
        description=(
            "If provided, this session is linked to the verified user (same "
            "effect as verify_gate succeeding inside /chat). If omitted, a "
            "new session is created and linked."
        ),
    )


class VerifyResponse(BaseModel):
    verified: bool
    user_id: Optional[str] = None
    first_name: Optional[str] = None
    session_id: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# /account/*
# ---------------------------------------------------------------------------


class BalanceRequest(BaseModel):
    session_id: str = Field(
        ..., description="A session_id previously verified via /verify or /chat."
    )
    account_id: Optional[str] = Field(
        None, description="Specific account. Omit for all accounts."
    )


class BalanceResponse(BaseModel):
    accounts: Optional[list[dict[str, Any]]] = None
    account_id: Optional[str] = None
    account_type: Optional[str] = None
    balance: Optional[float] = None
    currency: Optional[str] = None
    error: Optional[str] = None


class HistoryRequest(BaseModel):
    session_id: str
    account_id: Optional[str] = None
    limit: int = Field(10, ge=1, le=100)


class HistoryResponse(BaseModel):
    transactions: list[dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# /fraud/*
# ---------------------------------------------------------------------------


class LockCardRequest(BaseModel):
    session_id: str
    card_id: str


class LockCardResponse(BaseModel):
    status: Optional[str] = None
    card_id: Optional[str] = None
    error: Optional[str] = None


class ReportFraudRequest(BaseModel):
    session_id: str
    transaction_id: str
    reason: str = ""


class ReportFraudResponse(BaseModel):
    status: Optional[str] = None
    transaction_id: Optional[str] = None
    reported_at: Optional[str] = None
    note: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# /faq/search
# ---------------------------------------------------------------------------


class FaqSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    k: int = Field(3, ge=1, le=10)
    source: Optional[str] = None


class FaqSearchResponse(BaseModel):
    results: list[dict[str, Any]] = Field(default_factory=list)
    warning: Optional[str] = None


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
