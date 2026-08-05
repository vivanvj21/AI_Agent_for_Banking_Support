"""
Authentication API Router handling JWT logins, token refreshes, and claims verification.
"""

from __future__ import annotations

from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from security.jwt import create_access_token, create_refresh_token, decode_token
from security.rbac import UserRole
from tools.account_tools import verify_identity
from observability.audit import log_audit_event

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    user_id: str
    pin: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest) -> TokenResponse:
    res = verify_identity(user_id=req.user_id, pin=req.pin)
    if res.get("status") != "success":
        log_audit_event(
            event_type="auth_failure",
            user_id=req.user_id,
            status="failure",
            details={"reason": res.get("message", "Invalid credentials")},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=res.get("message", "Invalid credentials or account locked"),
        )

    claims = {"sub": req.user_id, "role": UserRole.CUSTOMER.value}
    access_token = create_access_token(claims)
    refresh_token = create_refresh_token(claims)

    log_audit_event(event_type="auth_success", user_id=req.user_id, status="success")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=req.user_id,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(req: RefreshRequest) -> TokenResponse:
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid refresh token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token subject")

    claims = {"sub": user_id, "role": payload.get("role", UserRole.CUSTOMER.value)}
    access_token = create_access_token(claims)
    new_refresh = create_refresh_token(claims)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        user_id=user_id,
    )
