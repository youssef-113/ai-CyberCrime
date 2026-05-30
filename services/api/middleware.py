"""Authentication Middleware - FastAPI Dependencies"""
import os
import logging
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .auth import decode_token
from .database import get_user_by_id
from .auth import UserResponse

logger = logging.getLogger("middleware")

# ── Bearer Token Scheme ──────────────────────────────────────────────────────
security = HTTPBearer(auto_error=False)

# ── Optional: Skip auth for development ──────────────────────────────────────
AUTH_DISABLED = os.getenv("AUTH_DISABLED", "false").lower() == "true"


def get_session_tenant(request: Request) -> dict:
    """Extract X-Session-ID and X-Tenant-ID from request headers."""
    session_id = request.headers.get("X-Session-ID", "")
    tenant_id = request.headers.get("X-Tenant-ID", "")
    return {"session_id": session_id, "tenant_id": tenant_id}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserResponse:
    """FastAPI dependency that extracts and validates the current user from JWT.
    Use this as a dependency in protected route handlers."""

    if AUTH_DISABLED:
        # Dev mode: return a mock user
        return UserResponse(
            id="00000000-0000-0000-0000-000000000000",
            email="dev@localhost",
            full_name="Development User",
            is_active=True,
            is_verified=True,
            created_at="2024-01-01T00:00:00Z",
        )

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_token(token)

    # Ensure it's an access token, not a refresh token
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Expected access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    return user


async def get_current_user_id(
    current_user: UserResponse = Depends(get_current_user),
) -> str:
    """Convenience dependency that returns just the user ID string."""
    return current_user.id


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserResponse | None:
    """Optional auth - returns user if token is valid, None otherwise.
    Use for endpoints that work for both authenticated and anonymous users."""
    if credentials is None:
        return None

    try:
        token = credentials.credentials
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        user = await get_user_by_id(user_id)
        return user
    except HTTPException:
        return None


def require_session(request: Request, user_id: str = Depends(get_current_user_id)) -> str:
    """Dependency that ensures a valid session ID is present.
    Returns the session_id from header or raises 400."""
    session_id = request.headers.get("X-Session-ID", "")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Session-ID header is required for this endpoint",
        )
    return session_id
