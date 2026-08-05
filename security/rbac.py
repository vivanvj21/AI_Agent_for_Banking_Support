"""
Role-Based Access Control (RBAC) definitions and FastAPI authorization dependencies.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from security.jwt import decode_token


class UserRole(str, Enum):
    CUSTOMER = "customer"
    SUPPORT_AGENT = "support_agent"
    ADMIN = "admin"


security_scheme = HTTPBearer(auto_error=False)


def require_roles(allowed_roles: List[UserRole]) -> Callable:
    def dependency(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
        if not credentials:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
        payload = decode_token(credentials.credentials)
        role = payload.get("role", UserRole.CUSTOMER.value)
        if role not in [r.value for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' is insufficient for this resource",
            )
        return payload

    return dependency
