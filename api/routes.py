"""
Route handlers.

Every handler here is a thin wrapper: it validates the request via the
Pydantic schemas in api/schemas.py, calls existing graph.py / tools/*.py
functions unchanged, and shapes the result into a response schema. No SQL,
no LLM calls, no verification logic is reimplemented in this file — that
would violate the "don't duplicate business logic" requirement.

Endpoint -> underlying implementation it reuses:
  POST /chat              -> graph.build_graph() / new_session_state() /
                              resume_session() / persist_turn()  (same as
                              cli.py and app_streamlit.py)
  POST /verify             -> tools.account_tools.verify_identity +
                               tools.memory.create_session/link_session_to_user
                               (same function agents/verification.py calls)
  POST /account/balance     -> tools.account_tools.get_balance
  POST /account/history      -> tools.account_tools.get_transaction_history
  POST /fraud/lock-card       -> tools.fraud_tools.lock_card
  POST /fraud/report            -> tools.fraud_tools.report_fraud_transaction
  POST /faq/search                -> tools.faq_search.search_faq
  GET  /health                      -> config.validate_startup
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_graph, require_verified_user
from api.metrics import record_request
from api.rate_limiter import rate_limit_chat, rate_limit_verify, rate_limit_default
from api.schemas import (
    BalanceRequest,
    BalanceResponse,
    ChatRequest,
    ChatResponse,
    FaqSearchRequest,
    FaqSearchResponse,
    HealthResponse,
    HistoryRequest,
    HistoryResponse,
    LockCardRequest,
    LockCardResponse,
    ReportFraudRequest,
    ReportFraudResponse,
    VerifyRequest,
    VerifyResponse,
)
from config import MissingAPIKeyError, validate_startup
from graph import new_session_state, persist_turn, resume_session
from tools import memory
from tools.account_tools import get_balance, get_transaction_history, verify_identity
from tools.faq_search import search_faq
from tools.fraud_tools import lock_card, report_fraud_transaction

LOGGER = logging.getLogger(__name__)

router = APIRouter()


def _timed(endpoint_name: str):
    """Small decorator-less timing helper used inline in each handler so
    /metrics has real numbers without adding middleware complexity."""
    return endpoint_name, time.perf_counter()


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(verify_perimeter_api_key), Depends(rate_limit_chat)])
def chat(payload: ChatRequest) -> ChatResponse:
    name, start = _timed("chat")
    try:
        app = get_graph()

        if payload.session_id:
            state = resume_session(payload.session_id)
        else:
            state = new_session_state(channel=payload.channel)

        if payload.auth:
            state["auth_user_id"] = payload.auth.user_id
            state["auth_pin"] = payload.auth.pin

        state["turn"] += 1
        state["messages"].append({"role": "user", "content": payload.message})
        state["reply"] = None

        state = app.invoke(state)
        persist_turn(state, payload.message)

        return ChatResponse(
            session_id=state["session_id"],
            reply=state.get("reply") or "",
            intent=state.get("intent"),
            verified=bool(state.get("verified")),
            user_id=state.get("user_id"),
            turn=state["turn"],
            end_session=bool(state.get("end_session")),
            tool_calls_log=state.get("tool_calls_log", []),
        )
    except MissingAPIKeyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception:
        LOGGER.exception("api_chat_failed")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while processing that request.",
        )
    finally:
        record_request(name, time.perf_counter() - start)


# ---------------------------------------------------------------------------
# POST /verify
# ---------------------------------------------------------------------------


@router.post("/verify", response_model=VerifyResponse, dependencies=[Depends(verify_perimeter_api_key), Depends(rate_limit_verify)])
def verify(payload: VerifyRequest) -> VerifyResponse:
    name, start = _timed("verify")
    try:
        result = verify_identity(payload.user_id, payload.pin)

        if not result.get("verified"):
            return VerifyResponse(
                verified=False,
                error=result.get("error", "Verification failed."),
                session_id=payload.session_id,
            )

        session_id = payload.session_id
        if session_id:
            if not memory.session_exists(session_id):
                raise HTTPException(
                    status_code=404, detail=f"Unknown session_id: {session_id}"
                )
        else:
            session_id = memory.create_session(channel="api")

        memory.link_session_to_user(session_id, result["user_id"])

        return VerifyResponse(
            verified=True,
            user_id=result["user_id"],
            first_name=result.get("first_name"),
            session_id=session_id,
        )
    finally:
        record_request(name, time.perf_counter() - start)


# ---------------------------------------------------------------------------
# POST /account/balance
# ---------------------------------------------------------------------------


@router.post("/account/balance", response_model=BalanceResponse, dependencies=[Depends(verify_perimeter_api_key), Depends(rate_limit_default)])
def account_balance(payload: BalanceRequest) -> BalanceResponse:
    name, start = _timed("account_balance")
    try:
        user_id = require_verified_user(payload.session_id)
        result = get_balance(user_id, account_id=payload.account_id)
        return BalanceResponse(**result)
    finally:
        record_request(name, time.perf_counter() - start)


# ---------------------------------------------------------------------------
# POST /account/history
# ---------------------------------------------------------------------------


@router.post("/account/history", response_model=HistoryResponse, dependencies=[Depends(verify_perimeter_api_key), Depends(rate_limit_default)])
def account_history(payload: HistoryRequest) -> HistoryResponse:
    name, start = _timed("account_history")
    try:
        user_id = require_verified_user(payload.session_id)
        result = get_transaction_history(
            user_id, account_id=payload.account_id, limit=payload.limit
        )
        return HistoryResponse(**result)
    finally:
        record_request(name, time.perf_counter() - start)


# ---------------------------------------------------------------------------
# POST /fraud/lock-card
# ---------------------------------------------------------------------------


@router.post("/fraud/lock-card", response_model=LockCardResponse, dependencies=[Depends(verify_perimeter_api_key), Depends(rate_limit_default)])
def fraud_lock_card(payload: LockCardRequest) -> LockCardResponse:
    name, start = _timed("fraud_lock_card")
    try:
        user_id = require_verified_user(payload.session_id)
        result = lock_card(user_id, payload.card_id)
        return LockCardResponse(**result)
    finally:
        record_request(name, time.perf_counter() - start)


# ---------------------------------------------------------------------------
# POST /fraud/report
# ---------------------------------------------------------------------------


@router.post("/fraud/report", response_model=ReportFraudResponse, dependencies=[Depends(verify_perimeter_api_key), Depends(rate_limit_default)])
def fraud_report(payload: ReportFraudRequest) -> ReportFraudResponse:
    name, start = _timed("fraud_report")
    try:
        user_id = require_verified_user(payload.session_id)
        result = report_fraud_transaction(
            user_id, payload.transaction_id, reason=payload.reason
        )
        return ReportFraudResponse(**result)
    finally:
        record_request(name, time.perf_counter() - start)


# ---------------------------------------------------------------------------
# POST /faq/search
# ---------------------------------------------------------------------------


@router.post("/faq/search", response_model=FaqSearchResponse, dependencies=[Depends(verify_perimeter_api_key), Depends(rate_limit_default)])
def faq_search_route(payload: FaqSearchRequest) -> FaqSearchResponse:
    name, start = _timed("faq_search")
    try:
        result = search_faq(payload.query, k=payload.k, source=payload.source)
        return FaqSearchResponse(**result)
    finally:
        record_request(name, time.perf_counter() - start)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    # require_llm=False: same reasoning as `cli.py --check-startup` -- health
    # checks should not hard-fail a running deployment just because the LLM
    # key check is stricter than "is this service up".
    status = validate_startup(require_llm=False, initialize=False)
    return HealthResponse(ok=status.ok, message=status.message, details=status.details)
