# Authentication Service — System Design

## Overview

The Authentication service manages user identity, JWT token lifecycle, password security, and session verification across the entire platform.

**Mount point:** Auth routes are mounted at `/api/auth` within the API Gateway
**Source:**
- `backend/services/auth/auth.py` — JWT, bcrypt, Pydantic models
- `backend/services/auth/middleware.py` — FastAPI dependency injection
- `backend/services/database/database.py` — Supabase persistence for auth operations

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Auth Token Flow                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  REGISTER                                                   │
│  ────────                                                   │
│  Client → POST /api/auth/register                           │
│     ├─ Validate password strength (8+ chars, upper, lower,  │
│     │   digit, special, not common)                         │
│     ├─ Hash password (bcrypt, 12 rounds)                    │
│     ├─ Check email uniqueness (Supabase)                    │
│     ├─ Insert user into `users` table                       │
│     ├─ Issue access_token (30 min) + refresh_token (7 days) │
│     ├─ Store refresh token JTI in `refresh_tokens` table    │
│     ├─ Log audit event: user.register                       │
│     └─ Return TokenResponse { access_token, refresh_token,  │
│                               expires_in, user }            │
│                                                             │
│  LOGIN                                                      │
│  ─────                                                      │
│  Client → POST /api/auth/login                              │
│     ├─ Look up user by email                                │
│     ├─ Verify password (bcrypt.checkpw)                     │
│     ├─ Check is_active flag                                 │
│     ├─ Issue new tokens                                     │
│     ├─ Store refresh token JTI                              │
│     ├─ Log audit event: user.login                          │
│     └─ Return TokenResponse                                 │
│                                                             │
│  REFRESH                                                    │
│  ───────                                                    │
│  Client → POST /api/auth/refresh                            │
│     ├─ Decode refresh token (validate type=refresh)         │
│     ├─ Revoke old refresh token (set revoked_at)            │
│     ├─ Verify user is still active                          │
│     ├─ Issue new access + refresh tokens                    │
│     ├─ Store new refresh token JTI                          │
│     └─ Return { access_token, refresh_token, expires_in }   │
│                                                             │
│  LOGOUT                                                     │
│  ──────                                                     │
│  Client → POST /api/auth/logout (Authorization: Bearer)     │
│     ├─ Extract user_id from JWT via middleware              │
│     ├─ Revoke ALL refresh tokens for user                   │
│     ├─ Log audit event: user.logout                         │
│     └─ Return { message: "Logged out successfully" }        │
│                                                             │
│  VERIFY                                                     │
│  ──────                                                     │
│  Client → POST /api/auth/verify (Authorization: Bearer)     │
│     ├─ Decode JWT, look up user                             │
│     ├─ Get or create active chat session                    │
│     ├─ Return { valid, user, tenant_id, session_id }        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Endpoints

### API Gateway Routes (`/api/auth`)

| Method | Path | Rate Limit | Description |
|--------|------|------------|-------------|
| POST | `/api/auth/register` | 5/min | Register new user |
| POST | `/api/auth/login` | 10/min | Login with email/password |
| POST | `/api/auth/refresh` | 10/min | Exchange refresh token |
| POST | `/api/auth/logout` | — | Revoke all refresh tokens |
| GET | `/api/auth/me` | — | Get current user profile |
| PUT | `/api/auth/password` | — | Change password |
| GET | `/api/auth/users` | — | List users (admin) |
| POST | `/api/auth/verify` | — | Verify session validity |

---

## JWT Token Design

### Access Token

| Claim | Value | Description |
|-------|-------|-------------|
| `sub` | `user_id` (UUID) | Subject — user identifier |
| `email` | user's email | For quick lookup |
| `type` | `"access"` | Prevents refresh token misuse |
| `iat` | timestamp | Issued at |
| `exp` | timestamp + 30 min | Expiration |
| `jti` | UUID v4 | Unique token ID |

### Refresh Token

| Claim | Value | Description |
|-------|-------|-------------|
| `sub` | `user_id` (UUID) | Subject |
| `type` | `"refresh"` | Differentiates from access tokens |
| `iat` | timestamp | Issued at |
| `exp` | timestamp + 7 days | Expiration |
| `jti` | UUID v4 | Unique token ID (stored in DB for revocation) |

### Algorithm

**HS256** (HMAC with SHA-256) symmetric signing using `JWT_SECRET_KEY`.

---

## Password Security

### Strength Requirements

| Requirement | Rule |
|-------------|------|
| Minimum length | 8 characters |
| Maximum length | 128 characters |
| Uppercase | At least 1 `[A-Z]` |
| Lowercase | At least 1 `[a-z]` |
| Digit | At least 1 `[0-9]` |
| Special | At least 1 `[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`]` |
| Common passwords | Blocklisted (password, 12345678, qwerty12, etc.) |

### Hashing

**Algorithm:** bcrypt
**Rounds:** 12 (configurable in `bcrypt.gensalt(rounds=12)`)
**Output:** `$2b$12$...` format string stored in `users.hashed_password`

### Password Change

1. Verify `current_password` matches stored hash
2. Validate `new_password` meets strength requirements
3. Ensure `new_password != current_password`
4. Hash new password, update `users.hashed_password`
5. Revoke ALL existing refresh tokens (forces re-login on all devices)

---

## Token Revocation

Refresh tokens are revocable — the `refresh_tokens` table stores each token's `jti` and `revoked_at` timestamp. Three operations trigger revocation:

| Operation | Scope |
|-----------|-------|
| Logout | ALL refresh tokens for the user |
| Password change | ALL refresh tokens for the user |
| Token refresh | The OLD refresh token only (rotated) |

---

## Database Tables

### users

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    full_name TEXT,
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### refresh_tokens

```sql
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## Middleware (`get_current_user`)

**File:** `backend/services/auth/middleware.py`

The `get_current_user` FastAPI dependency is used on all protected routes:

1. Extract `Authorization: Bearer {token}` header
2. Decode JWT using `decode_token()` (raises 401 on expired/invalid)
3. Verify token `type == "access"` (rejects refresh tokens)
4. Look up user by `sub` (user_id) in Supabase
5. Verify `is_active == true` (raises 403 if deactivated)
6. Return `UserResponse`

### Additional Dependencies

| Dependency | Return | Purpose |
|------------|--------|---------|
| `get_current_user` | `UserResponse` | Protected routes |
| `get_current_user_id` | `str` (user_id) | Convenience for user-scoped queries |
| `get_optional_user` | `UserResponse \| None` | Mixed public/protected endpoints |
| `require_session` | `str` (session_id) | Ensures X-Session-ID header present |
| `get_session_tenant` | `{session_id, tenant_id}` | Extracts headers |

### Dev Mode

Setting `AUTH_DISABLED=true` bypasses all auth checks and returns a mock user:
```python
UserResponse(
    id="00000000-0000-0000-0000-000000000000",
    email="dev@localhost",
    full_name="Development User",
    is_active=True,
    is_verified=True,
    ...
)
```

---

## Rate Limiting

All auth endpoints use `slowapi` with per-user rate limits (keyed by JWT sub claim):

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/auth/register` | 5 requests | 1 minute |
| `/auth/login` | 10 requests | 1 minute |
| `/auth/refresh` | 10 requests | 1 minute |

Rate limit key function extracts user ID from JWT, falling back to client IP for unauthenticated requests.

---

## Audit Logging

All auth operations log to the `audit_logs` table:

| Action | Event | Metadata |
|--------|-------|----------|
| Register | `user.register` | email |
| Login | `user.login` | email |
| Refresh | `user.refresh` | token_type |
| Logout | `user.logout` | — |

Audit events are fire-and-forget (async task, failures logged but non-critical).

---

## Data Models

### Request Models

```python
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str            # validated on input
    full_name: Optional[str] # sanitized, max 255 chars

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str        # validated on input
```

### Response Models

```python
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int          # seconds
    user: UserResponse

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    phone: Optional[str]
    language: str            # default "ar"
    timezone: str            # default "Africa/Cairo"
    notification_preferences: Dict
    mfa_enabled: bool
    role: str                # "user" | "admin"
    last_login_at: Optional[str]
    created_at: str
```

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| Password brute force | bcrypt (slow hash), rate limiting (10/min) |
| Token theft | 30-min expiry, revocable refresh tokens |
| Refresh token replay | Rotation on each refresh, JTI tracking |
| Email enumeration | Generic "Invalid email or password" error |
| XSS via full_name | Regex validation `^[\w\s\-']+$`, max 255 chars |
| Token type confusion | Separate `type` claim for access vs refresh |
| SQL injection | Supabase client uses parameterized queries |
| Insecure dev defaults | `AUTH_DISABLED` only for development |

---

## Row-Level Security (RLS)

Supabase RLS policies isolate user data:

- `users` — Service role only (users see own public profile)
- `refresh_tokens` — Service role only
- All other user-scoped tables (`cases`, `chat_sessions`, `chat_messages`, etc.) have RLS policies ensuring users can only access their own data
