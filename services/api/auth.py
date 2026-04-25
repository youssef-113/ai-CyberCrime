"""Authentication Module - JWT + bcrypt with Supabase PostgreSQL"""
import os
import re
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from pydantic import BaseModel, EmailStr, field_validator
from fastapi import HTTPException, status

logger = logging.getLogger("auth")

# ── Configuration ────────────────────────────────────────────────────────────
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production-use-strong-key")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# ── Password Validation ─────────────────────────────────────────────────────
MIN_PASSWORD_LENGTH = 8
PASSWORD_REQUIREMENTS = {
    "min_length": MIN_PASSWORD_LENGTH,
    "uppercase": True,
    "lowercase": True,
    "digit": True,
    "special": True,
}


def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    """Validate password against security requirements.
    Returns (is_valid, list_of_errors)."""
    errors = []

    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long")
    if len(password) > 128:
        errors.append("Password must not exceed 128 characters")

    if PASSWORD_REQUIREMENTS["uppercase"] and not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter")
    if PASSWORD_REQUIREMENTS["lowercase"] and not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter")
    if PASSWORD_REQUIREMENTS["digit"] and not re.search(r"\d", password):
        errors.append("Password must contain at least one digit")
    if PASSWORD_REQUIREMENTS["special"] and not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`]', password):
        errors.append("Password must contain at least one special character (!@#$%^&* etc.)")

    # Check for common weak passwords
    common_passwords = {
        "password", "password1", "password123", "12345678", "qwerty12",
        "abc12345", "admin123", "letmein1", "welcome1", "monkey123",
    }
    if password.lower() in common_passwords:
        errors.append("This password is too common. Choose a more unique password")

    return len(errors) == 0, errors


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with salt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


# ── JWT Token Management ────────────────────────────────────────────────────
def create_access_token(user_id: str, email: str) -> str:
    """Create a JWT access token."""
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "iat": now,
        "exp": expires,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """Create a JWT refresh token."""
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": expires,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises HTTPException on invalid/expired."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Pydantic Models ─────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        is_valid, errors = validate_password_strength(v)
        if not is_valid:
            raise ValueError("; ".join(errors))
        return v

    @field_validator("full_name")
    @classmethod
    def sanitize_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 255:
                raise ValueError("Full name must not exceed 255 characters")
            if v and not re.match(r"^[\w\s\-']+$", v):
                raise ValueError("Full name contains invalid characters")
        return v or None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: "UserResponse"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        is_valid, errors = validate_password_strength(v)
        if not is_valid:
            raise ValueError("; ".join(errors))
        return v
