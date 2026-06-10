"""Supabase PostgreSQL Database Client"""
import os
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from supabase import create_client, Client
from .auth import hash_password, verify_password, decode_token
from .auth import (
    RegisterRequest, LoginRequest, TokenResponse, UserResponse,
    RefreshRequest, ChangePasswordRequest,
    create_access_token, create_refresh_token,
    validate_password_strength, ACCESS_TOKEN_EXPIRE_MINUTES,
)
from fastapi import HTTPException, status

logger = logging.getLogger("db")

# ── Supabase Client ──────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.warning("SUPABASE_URL or SUPABASE_KEY not set. Database features will be unavailable.")

supabase: Optional[Client] = None

def get_supabase() -> Client:
    """Get or initialize the Supabase client."""
    global supabase
    if supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not configured. Set SUPABASE_URL and SUPABASE_KEY."
            )
        key = SUPABASE_SERVICE_KEY or SUPABASE_KEY
        supabase = create_client(SUPABASE_URL, key)
    return supabase


# ── User Operations ─────────────────────────────────────────────────────────
async def register_user(req: RegisterRequest) -> TokenResponse:
    """Register a new user. Returns tokens on success."""
    db = get_supabase()

    # Check if email already exists
    existing = db.table("users").select("id").eq("email", req.email).execute()
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists"
        )

    # Hash password and insert user
    hashed_pw = hash_password(req.password)
    user_data = {
        "email": req.email,
        "hashed_password": hashed_pw,
        "full_name": req.full_name,
        "is_active": True,
        "is_verified": False,
        "role": "user",  # Default role for new users
        "language": "ar",
        "timezone": "Africa/Cairo",
        "notification_preferences": {},
        "mfa_enabled": False,
    }

    result = db.table("users").insert(user_data).execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account"
        )

    user = result.data[0]

    # Create tokens
    access_token = create_access_token(user["id"], user["email"])
    refresh_token = create_refresh_token(user["id"])

    # Store refresh token hash
    _store_refresh_token(db, user["id"], refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            full_name=user.get("full_name"),
            is_active=user["is_active"],
            is_verified=user["is_verified"],
            created_at=user["created_at"],
        ),
    )


async def login_user(req: LoginRequest) -> TokenResponse:
    """Authenticate user with email/password. Returns tokens on success."""
    db = get_supabase()

    # Look up user by email
    result = db.table("users").select("*").eq("email", req.email).execute()
    if not result.data:
        # Use generic message to prevent email enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    user = result.data[0]

    # Verify password
    if not verify_password(req.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Check if account is active
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact support."
        )

    # Create tokens
    access_token = create_access_token(user["id"], user["email"])
    refresh_token = create_refresh_token(user["id"])

    # Store refresh token
    _store_refresh_token(db, user["id"], refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            full_name=user.get("full_name"),
            is_active=user["is_active"],
            is_verified=user["is_verified"],
            created_at=user["created_at"],
        ),
    )


async def refresh_access_token(req: RefreshRequest) -> dict:
    """Exchange a valid refresh token for new access + refresh tokens."""
    db = get_supabase()

    # Decode the refresh token
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type"
        )

    user_id = payload.get("sub")

    # Check if this refresh token is still valid (not revoked)
    token_jti = payload.get("jti")
    db.table("refresh_tokens").update({"revoked_at": datetime.now(timezone.utc).isoformat()}).eq("user_id", user_id).eq("token_hash", token_jti).execute()

    # Get user
    user_result = db.table("users").select("*").eq("id", user_id).execute()
    if not user_result.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    user = user_result.data[0]
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    # Issue new tokens
    new_access = create_access_token(user["id"], user["email"])
    new_refresh = create_refresh_token(user["id"])

    _store_refresh_token(db, user["id"], new_refresh)

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


async def logout_user(user_id: str) -> None:
    """Revoke all refresh tokens for a user."""
    db = get_supabase()
    db.table("refresh_tokens").update({
        "revoked_at": datetime.now(timezone.utc).isoformat()
    }).eq("user_id", user_id).execute()


async def get_user_by_id(user_id: str) -> Optional[UserResponse]:
    """Fetch a user by ID."""
    db = get_supabase()
    result = db.table("users").select("*").eq("id", user_id).execute()
    if not result.data:
        return None
    user = result.data[0]
    return UserResponse(
        id=user["id"],
        email=user["email"],
        full_name=user.get("full_name"),
        is_active=user["is_active"],
        is_verified=user["is_verified"],
        created_at=user["created_at"],
    )


async def change_user_password(user_id: str, req: ChangePasswordRequest) -> None:
    """Change a user's password after verifying the current one."""
    db = get_supabase()

    result = db.table("users").select("hashed_password").eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not verify_password(req.current_password, result.data[0]["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )

    # Validate new password is different
    if req.current_password == req.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )

    new_hashed = hash_password(req.new_password)
    db.table("users").update({"hashed_password": new_hashed}).eq("id", user_id).execute()

    # Revoke all refresh tokens (force re-login on other devices)
    db.table("refresh_tokens").update({
        "revoked_at": datetime.now(timezone.utc).isoformat()
    }).eq("user_id", user_id).execute()


# ── Case Operations (User-Scoped) ──────────────────────────────────────────
async def create_case(user_id: str, case_id: str, files_count: int) -> dict:
    """Create a new case record for a user."""
    db = get_supabase()
    data = {
        "case_id": case_id,
        "user_id": user_id,
        "status": "processing",
        "files_count": files_count,
    }
    result = db.table("cases").insert(data).execute()
    return result.data[0] if result.data else None


async def update_case(case_id: str, status: str, result: Optional[dict] = None, error: Optional[str] = None) -> None:
    """Update case status and result."""
    db = get_supabase()
    update_data = {"status": status}
    if result is not None:
        update_data["result"] = json.dumps(result) if isinstance(result, dict) else result
    if error is not None:
        update_data["error"] = error
    db.table("cases").update(update_data).eq("case_id", case_id).execute()


async def get_user_cases(user_id: str) -> List[dict]:
    """Get all cases for a user."""
    db = get_supabase()
    result = db.table("cases").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return result.data


async def get_case_by_id(case_id: str, user_id: str) -> Optional[dict]:
    """Get a specific case, ensuring it belongs to the user."""
    db = get_supabase()
    result = db.table("cases").select("*").eq("case_id", case_id).eq("user_id", user_id).execute()
    return result.data[0] if result.data else None


# ── Chat Session Operations ────────────────────────────────────────────────
async def create_chat_session(user_id: str, session_id: str, title: Optional[str] = None, case_context: Optional[dict] = None, language: str = "ar") -> dict:
    """Create a new chat session."""
    db = get_supabase()
    data = {
        "session_id": session_id,
        "user_id": user_id,
        "title": title,
        "case_context": json.dumps(case_context) if case_context else None,
        "language": language,
    }
    result = db.table("chat_sessions").insert(data).execute()
    return result.data[0] if result.data else None


async def get_user_sessions(user_id: str) -> List[dict]:
    """Get all chat sessions for a user."""
    db = get_supabase()
    result = db.table("chat_sessions").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return result.data


async def save_chat_message(session_id: str, role: str, content: str, citations: Optional[list] = None, user_id: str = None) -> dict:
    """Save a chat message (with optional user_id for isolation)."""
    db = get_supabase()
    data = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "citations": json.dumps(citations) if citations else "[]",
    }
    # Add user_id if provided for better query optimization
    if user_id:
        data["user_id"] = user_id
    
    result = db.table("chat_messages").insert(data).execute()
    return result.data[0] if result.data else None


async def get_chat_history(session_id: str) -> List[dict]:
    """Get all messages for a chat session."""
    db = get_supabase()
    result = db.table("chat_messages").select("*").eq("session_id", session_id).order("created_at", asc=True).execute()
    return result.data


async def get_recent_chat_history(session_id: str, limit: int = 5) -> List[dict]:
    """Get the last N messages for a chat session (for context)."""
    db = get_supabase()
    result = db.table("chat_messages").select("*").eq("session_id", session_id).order("created_at", desc=True).limit(limit).execute()
    # Reverse to get chronological order
    return list(reversed(result.data))


async def save_session_upload(session_id: str, file_name: str, file_type: str, indexed_chunks: int = 0, metadata: Optional[dict] = None) -> dict:
    """Save a record of a file uploaded to a chat session."""
    db = get_supabase()
    data = {
        "session_id": session_id,
        "file_name": file_name,
        "file_type": file_type,
        "indexed_chunks": indexed_chunks,
        "metadata": json.dumps(metadata) if metadata else None,
    }
    result = db.table("session_uploads").insert(data).execute()
    return result.data[0] if result.data else None


async def get_session_uploads(session_id: str) -> List[dict]:
    """Get all files uploaded to a chat session."""
    db = get_supabase()
    result = db.table("session_uploads").select("*").eq("session_id", session_id).order("created_at", desc=True).execute()
    return result.data


# ── Internal Helpers ─────────────────────────────────────────────────────────
def _store_refresh_token(db: Client, user_id: str, token: str) -> None:
    """Store a refresh token's JTI in the database."""
    payload = decode_token(token)
    jti = payload.get("jti")
    expires = payload.get("exp")

    db.table("refresh_tokens").insert({
        "user_id": user_id,
        "token_hash": jti,
        "expires_at": datetime.fromtimestamp(expires, tz=timezone.utc).isoformat(),
    }).execute()
