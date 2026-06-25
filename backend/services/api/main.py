"""API Gateway - Main Orchestrator (Port 8000)"""
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Depends, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, validator
from typing import Any, Dict, List, Optional
import httpx
import uuid
import os
import json
import logging
import asyncio
from datetime import datetime, timezone

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from services.common.logging import configure_structured_logging, set_request_context, clear_request_context

from services.security.security import (
    MAX_UPLOAD_FILES,
    validate_upload_file,
    sanitize_payload,
    sanitize_string,
    validate_input,
    get_client_ip,
    is_ip_blocked,
    record_failed_attempt,
    reset_failed_attempts,
    check_rate_limit,
    get_rate_limit_headers,
    get_security_headers,
    log_security_event,
    generate_csrf_token,
    validate_csrf_token,
    validate_ocr_text,
    validate_chat_message,
    MAX_REQUEST_SIZE_BYTES,
    sanitize_text_for_llm,
    MAX_OCR_PAGES,
    MAX_OCR_TIMEOUT,
)

from services.auth.auth import (
    RegisterRequest, LoginRequest, TokenResponse, RefreshRequest,
    ChangePasswordRequest, UserResponse, decode_token,
)
from services.database.database import (
    register_user, login_user, refresh_access_token, logout_user,
    get_user_by_id, change_user_password, get_supabase,
    create_case, update_case, get_user_cases, get_case_by_id,
    create_chat_session, get_user_sessions, save_chat_message, get_chat_history,
    get_recent_chat_history, save_session_upload, get_session_uploads,
    log_audit_event, get_audit_events,
)
from services.auth.middleware import get_current_user, get_current_user_id, get_session_tenant, require_session, get_optional_user
from .resilience import retry_with_backoff, get_retry_config_for_service, ServiceCallError
from .pipeline import check_service_health
from services.common.llm_client import get_llm_status

logger = logging.getLogger("api.gateway")

case_progress_store = {}


def get_rate_limit_key(request: Request) -> str:
    token = request.headers.get("Authorization", "")
    if token.lower().startswith("bearer "):
        try:
            payload = decode_token(token.split(" ", 1)[1])
            if payload.get("sub"):
                return f"user:{payload.get('sub')}"
        except Exception:
            pass
    return get_remote_address(request)


async def call_microservice(
    service_name: str,
    method: str,
    url: str,
    params: Optional[dict] = None,
    json_payload: Optional[dict] = None,
    files: Optional[Any] = None,
    timeout: Optional[float] = None,
) -> httpx.Response:
    config = get_retry_config_for_service(service_name)
    timeout = timeout or config.get("timeout", 30.0)

    async def _request() -> httpx.Response:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                url,
                params=params,
                json=json_payload,
                files=files,
                timeout=timeout,
            )
            response.raise_for_status()
            return response

    try:
        return await retry_with_backoff(
            _request,
            max_retries=config.get("max_retries", 2),
            initial_delay=config.get("initial_delay", 1.0),
            max_delay=config.get("max_delay", 30.0),
            exponential_base=config.get("exponential_base", 2.0),
            jitter=True,
        )
    except Exception as exc:
        raise ServiceCallError(service=service_name, error=str(exc)) from exc


def audit_action(
    user_id: Optional[str],
    action: str,
    resource_type: str = "",
    resource_id: str = "",
    metadata: Optional[dict] = None,
) -> None:
    if not action:
        return
    try:
        asyncio.create_task(log_audit_event(
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata or {},
        ))
    except Exception:
        logger.warning("Audit log failed", exc_info=True)


def publish_case_progress(case_id: str, event_type: str, data: dict):
    now = datetime.utcnow().isoformat() + "Z"
    progress = case_progress_store.setdefault(case_id, {
        "case_id": case_id,
        "status": "processing",
        "progress": 0,
        "stage": "started",
        "updated_at": now,
        "events": [],
    })
    progress.update(data)
    progress["status"] = data.get("status", progress["status"])
    progress["stage"] = data.get("stage", progress["stage"])
    progress["updated_at"] = now
    progress["events"].append({"event": event_type, "timestamp": now, **data})


def get_case_progress(case_id: str) -> dict:
    return case_progress_store.get(case_id, {})


async def verify_access_token(access_token: Optional[str] = Query(None)):
    if os.getenv("AUTH_DISABLED", "false").lower() == "true":
        return None
    if not access_token:
        raise HTTPException(status_code=401, detail="Missing access token for case event stream")
    payload = decode_token(access_token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

app = FastAPI(
    title="Cybercrime AI - API Gateway",
    description="Main orchestrator for the 6-stage AI pipeline with multi-user auth",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*", "X-Session-ID", "X-Tenant-ID"],
    allow_credentials=True,
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=os.getenv("TRUSTED_HOSTS", "localhost,127.0.0.1").split(","),
)


# Security middleware
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Apply security checks to all requests"""
    # Get client IP
    client_ip = get_client_ip(request)
    
    # Log incoming request
    logger.info(f"Request: {request.method} {request.url.path} from {client_ip}")
    
    # Check if IP is blocked
    if is_ip_blocked(client_ip):
        log_security_event("blocked_ip_access", {"path": request.url.path}, client_ip)
        return JSONResponse(
            status_code=403,
            content={"detail": "Access denied"}
        )
    
    # Check request size
    content_length = request.headers.get("content-length")
    if content_length:
        content_length = int(content_length)
        if content_length > MAX_REQUEST_SIZE_BYTES:
            log_security_event("request_too_large", {"size": content_length, "path": request.url.path}, client_ip)
            return JSONResponse(
                status_code=413,
                content={"detail": f"Request too large. Maximum is {MAX_REQUEST_SIZE_BYTES} bytes"}
            )
    
    # Rate limiting
    rate_limit_key = get_rate_limit_key(request)
    limit_type = "auth" if "/auth/" in request.url.path else "default"
    
    if not check_rate_limit(rate_limit_key, limit_type):
        log_security_event("rate_limit_exceeded", {"path": request.url.path, "limit_type": limit_type}, client_ip)
        headers = get_rate_limit_headers(rate_limit_key, limit_type)
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers=headers
        )
    
    # JWT verification for protected routes (except auth endpoints)
    if not request.url.path.startswith("/auth/"):
        auth_header = request.headers.get("Authorization", "")
        if auth_header:
            try:
                token = auth_header.split(" ", 1)[1] if auth_header.lower().startswith("bearer ") else auth_header
                payload = decode_token(token)
                # Add user info to request state for downstream use
                request.state.user_id = payload.get("sub")
                request.state.user_email = payload.get("email")
            except Exception as e:
                logger.warning(f"JWT verification failed: {str(e)}")
                # Don't block request, just log it - let individual endpoints handle auth
        else:
            logger.debug("No Authorization header provided")
    
    # Request validation for POST/PUT/PATCH
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            # Validate request body if present
            if request.headers.get("content-type", "").startswith("application/json"):
                body = await request.json()
                # Validate input
                validated_body = validate_input(body, "request_body")
                # Store validated body in request state
                request.state.validated_body = validated_body
        except Exception as e:
            logger.error(f"Request validation failed: {str(e)}")
            log_security_event("request_validation_failed", {"path": request.url.path, "error": str(e)}, client_ip)
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid request body"}
            )
    
    # Process request
    response = await call_next(request)
    
    # Add security headers
    security_headers = get_security_headers()
    for key, value in security_headers.items():
        response.headers[key] = value
    
    # Add rate limit headers
    rate_limit_headers = get_rate_limit_headers(rate_limit_key, limit_type)
    for key, value in rate_limit_headers.items():
        response.headers[key] = value
    
    # Log response
    logger.info(f"Response: {response.status_code} for {request.method} {request.url.path}")
    
    return response

@app.on_event("startup")
async def startup_event():
    configure_structured_logging()
    logger.info("API gateway starting", service="api.gateway")


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    user_id = None
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        try:
            user_payload = decode_token(authorization.split(" ", 1)[1])
            user_id = user_payload.get("sub")
        except Exception:
            user_id = None

    set_request_context(
        request_id=request_id,
        user_id=user_id,
        path=str(request.url.path),
        method=request.method,
    )

    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception("Unhandled request error")
        raise
    finally:
        clear_request_context()

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), payment=()"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    response.headers["X-Download-Options"] = "noopen"
    response.headers["Cache-Control"] = "no-store"
    return response

# ── Rate Limiting ──────────────────────────────────────────────────
limiter = Limiter(key_func=get_rate_limit_key)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    """Handle rate limit exceeded errors"""
    logger.warning("Rate limit exceeded", extra={"path": str(request.url.path), "method": request.method})
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": 429,
                "message": "Rate limit exceeded. Try again later.",
                "request_id": request.state.request_id if hasattr(request.state, "request_id") else None,
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(
        "HTTP exception raised",
        extra={"status_code": exc.status_code, "detail": exc.detail},
        exc_info=exc if exc.status_code >= 500 else None,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "request_id": request.state.request_id if hasattr(request.state, "request_id") else None,
            }
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unexpected server error")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error",
                "request_id": request.state.request_id if hasattr(request.state, "request_id") else None,
            }
        },
    )

# Service URLs (from environment or defaults).
# The backend is deployed as a single monolith (backend/main.py) that mounts
# every sub-service in-process: /ocr, /classifier, /rag, /verification, /pdf,
# /chat. The gateway therefore proxies to itself over HTTP. Defaults below
# target the local monolith; docker-compose overrides them to the `backend`
# service host so the celery worker (separate container) can reach the API too.
_SELF = os.getenv("MONOLITH_BASE_URL", "http://localhost:8000")
SERVICE_URLS = {
    "ocr": os.getenv("OCR_SERVICE_URL", f"{_SELF}/ocr"),
    "classifier": os.getenv("CLASSIFIER_SERVICE_URL", f"{_SELF}/classifier"),
    "rag": os.getenv("RAG_SERVICE_URL", f"{_SELF}/rag"),
    "verification": os.getenv("VERIFICATION_SERVICE_URL", f"{_SELF}/verification"),
    "pdf": os.getenv("PDF_SERVICE_URL", f"{_SELF}/pdf"),
    "chatbot": os.getenv("CHATBOT_SERVICE_URL", f"{_SELF}/chat"),
}

class CaseStatus(BaseModel):
    case_id: str
    user_id: str
    status: str  # processing, completed, failed, pending
    crime_type: Optional[str] = None
    priority: str = "normal"  # low, normal, urgent, critical
    score: Optional[int] = None
    grade: Optional[str] = None  # STRONG, MEDIUM, WEAK (from verification scoring)
    files_count: int = 0
    verification_case_id: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    result: Optional[dict] = None


class ClassifyRequest(BaseModel):
    text: str
    entities: Optional[dict] = {}


class RetrieveRequest(BaseModel):
    query: str
    crime_type: str = ""
    top_k: int = 5
    tenant_id: str = "default"
    transform_strategy: str = "auto"


class FaithfulnessRequest(BaseModel):
    query: str
    answer: str
    citations: List[dict] = []


class IndexRequest(BaseModel):
    articles: List[dict]
    tenant_id: str = "default"
    async_ingest: bool = False


class ChatPdfTriggerRequest(BaseModel):
    session_id: str


# ══════════════════════════════════════════════════════════════════════════
#  PUBLIC ROUTES (no auth required)
# ══════════════════════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {
        "service": "Cybercrime AI - API Gateway",
        "version": "2.0.0",
        "pipeline_stages": ["upload", "ocr", "classify", "rag", "verify", "pdf"],
        "auth_enabled": True,
    }

@app.get("/health")
async def health():
    """Check all service health including Supabase connection"""
    health_status = {"gateway": "healthy", "services": {}, "database": "unknown"}

    # Check Supabase connection
    try:
        db = get_supabase()
        # Try a simple query to verify connection
        result = db.table("users").select("count", count="exact").limit(1).execute()
        health_status["database"] = "connected"
        health_status["supabase"] = "connected"
    except Exception as e:
        health_status["database"] = "disconnected"
        health_status["supabase"] = f"error: {str(e)}"

    for name, url in SERVICE_URLS.items():
        try:
            resp = await call_microservice(name, "GET", f"{url}/health", timeout=5.0)
            health_status["services"][name] = "healthy" if resp.status_code == 200 else "unhealthy"
        except ServiceCallError:
            health_status["services"][name] = "unreachable"

    return health_status


@app.get("/health/aggregate")
async def health_aggregate():
    """Aggregate API gateway health with LLM connectivity and current active progress."""
    base_health = await health()
    llm_status = await get_llm_status()
    base_health["llm"] = llm_status
    base_health["active_cases"] = len(case_progress_store)
    return base_health


@app.get("/ready")
async def ready():
    """Readiness probe for orchestration and deployment."""
    health_status = await health()
    if health_status["database"] != "connected":
        return JSONResponse(status_code=503, content={"status": "unready", "database": health_status["database"]})
    return {"status": "ready", "services": health_status["services"]}


@app.get("/metrics")
async def metrics():
    """Expose lightweight service metrics for monitoring."""
    counts = {}
    try:
        db = get_supabase()
        counts["users"] = db.table("users").select("*", count="exact").limit(1).execute().count or 0
        counts["cases"] = db.table("cases").select("*", count="exact").limit(1).execute().count or 0
        counts["sessions"] = db.table("chat_sessions").select("*", count="exact").limit(1).execute().count or 0
        counts["messages"] = db.table("chat_messages").select("*", count="exact").limit(1).execute().count or 0
        counts["audit_events"] = db.table("audit_logs").select("*", count="exact").limit(1).execute().count or 0
    except Exception as e:
        logger.warning(f"Metrics query failed: {e}")

    service_health = await check_service_health(SERVICE_URLS)
    return {
        "service": "api-gateway",
        "version": "2.0.0",
        "active_cases": len(case_progress_store),
        "database_counts": counts,
        "services": service_health,
    }


@app.get("/audit/events")
async def list_audit_events(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    """Return audit events for the current authenticated user."""
    events = await get_audit_events(current_user.id, limit=limit, offset=offset)
    return {"audit_events": events, "limit": limit, "offset": offset}


@app.get("/cases/{case_id}/events")
async def case_events(
    case_id: str,
    user: Optional[dict] = Depends(verify_access_token),
):
    """Stream live case progress updates via Server-Sent Events."""
    if user:
        case = await get_case_by_id(case_id, user.id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found or access denied")

    progress = get_case_progress(case_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Case not found or no live progress available")

    async def event_generator():
        last_sent = 0
        while True:
            progress = get_case_progress(case_id)
            if not progress:
                break
            events = progress.get("events", [])
            if last_sent < len(events):
                for event in events[last_sent:]:
                    last_sent = len(events)
                    yield f"event: update\ndata: {json.dumps(event)}\n\n"
            if progress.get("status") in ("completed", "failed"):
                yield f"event: done\ndata: {json.dumps(progress)}\n\n"
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ══════════════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════

@app.post("/auth/register", response_model=TokenResponse, status_code=201)
@limiter.limit("5/minute")
async def register(request: Request, req: RegisterRequest):
    """Register a new user account."""
    response = await register_user(req)
    audit_action(
        user_id=response.user.id,
        action="user.register",
        resource_type="user",
        resource_id=response.user.id,
        metadata={"email": response.user.email},
    )
    return response


@app.post("/auth/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, req: LoginRequest):
    """Login with email and password."""
    response = await login_user(req)
    audit_action(
        user_id=response.user.id,
        action="user.login",
        resource_type="user",
        resource_id=response.user.id,
        metadata={"email": response.user.email},
    )
    return response


@app.post("/auth/refresh")
@limiter.limit("10/minute")
async def refresh_token(request: Request, req: RefreshRequest):
    """Exchange a refresh token for new access + refresh tokens."""
    payload = decode_token(req.refresh_token)
    user_id = payload.get("sub")
    response = await refresh_access_token(req)
    audit_action(
        user_id=user_id,
        action="user.refresh",
        resource_type="user",
        resource_id=user_id or "",
        metadata={"token_type": "refresh"},
    )
    return response


@app.post("/auth/logout")
async def logout(user_id: str = Depends(get_current_user_id)):
    """Logout - revokes all refresh tokens."""
    await logout_user(user_id)
    audit_action(
        user_id=user_id,
        action="user.logout",
        resource_type="user",
        resource_id=user_id,
    )
    return {"message": "Logged out successfully"}


@app.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: UserResponse = Depends(get_current_user)):
    """Get the current authenticated user's profile."""
    return current_user


@app.put("/auth/password")
async def change_password(
    req: ChangePasswordRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Change the current user's password."""
    await change_user_password(user_id, req)
    return {"message": "Password changed successfully. Please login again."}


@app.get("/auth/users")
async def list_users(current_user: UserResponse = Depends(get_current_user)):
    """List all users (admin feature - returns limited fields)."""
    db = get_supabase()
    result = db.table("users").select("id, email, full_name, is_active, is_verified, created_at").execute()
    return {"users": result.data or []}


@app.post("/auth/verify")
async def verify_session(current_user: UserResponse = Depends(get_current_user)):
    """Verify current session is valid. Returns tenant_id and active sessions."""
    tenant_id = f"user_{current_user.id}"

    # Get or create an active session for the user
    sessions = await get_user_sessions(current_user.id)
    active_session = None
    for s in sessions:
        if s.get("is_active", False):
            active_session = s
            break

    if not active_session:
        session_id = str(uuid.uuid4())
        session_data = await create_chat_session(current_user.id, session_id)
        active_session = session_data or {"session_id": session_id}

    return {
        "valid": True,
        "user": current_user,
        "tenant_id": tenant_id,
        "session_id": active_session.get("session_id", ""),
        "message": "Session is valid",
    }


# ══════════════════════════════════════════════════════════════════════════
#  SESSION MANAGEMENT ROUTES (auth required)
# ══════════════════════════════════════════════════════════════════════════

class CreateSessionRequest(BaseModel):
    case_id: Optional[str] = None
    linked_case_id: Optional[str] = None  # Links to cases.case_id
    title: Optional[str] = None
    context: Optional[dict] = None
    language: str = "ar"
    model_used: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 800


@app.post("/sessions")
async def create_session(
    request: CreateSessionRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Create a new chat session for the user"""
    session_id = str(uuid.uuid4())
    session_data = await create_chat_session(
        user_id=user_id,
        session_id=session_id,
        case_context=request.context
    )
    
    if not session_data:
        raise HTTPException(status_code=500, detail="Failed to create session")
    
    return {
        "session_id": session_data.get("session_id") or session_id,
        "user_id": session_data.get("user_id") or user_id,
        "is_active": session_data.get("is_active", True),
        "created_at": session_data.get("created_at", datetime.utcnow().isoformat()),
        "case_id": session_data.get("case_id") or request.case_id
    }


@app.get("/sessions/user/{user_id}")
async def list_user_sessions(
    user_id: str = Depends(get_current_user_id),
    limit: int = 10,
    offset: int = 0,
):
    """List all user's chat sessions (paginated)"""
    db = get_supabase()
    
    # Get total count
    count_result = db.table("chat_sessions")\
        .select("*", count="exact")\
        .eq("user_id", user_id)\
        .execute()
    total = count_result.count or 0
    
    # Get paginated results
    result = db.table("chat_sessions")\
        .select("*")\
        .eq("user_id", user_id)\
        .order("created_at", desc=True)\
        .range(offset, offset + limit - 1)\
        .execute()
    
    sessions = [
        {
            "session_id": s["session_id"],
            "user_id": s["user_id"],
            "is_active": s["is_active"],
            "created_at": s["created_at"],
            "case_id": s.get("case_id")
        }
        for s in result.data
    ]
    
    return {"sessions": sessions, "total": total, "limit": limit, "offset": offset}


@app.get("/sessions/{session_id}")
async def get_session_details(
    session_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Get session details (verify ownership)"""
    db = get_supabase()
    
    result = db.table("chat_sessions")\
        .select("*")\
        .eq("session_id", session_id)\
        .eq("user_id", user_id)\
        .execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = result.data[0]
    
    # Get message count
    messages_result = db.table("chat_messages")\
        .select("*", count="exact")\
        .eq("session_id", session_id)\
        .execute()
    
    return {
        "session_id": session["session_id"],
        "user_id": session["user_id"],
        "is_active": session["is_active"],
        "created_at": session["created_at"],
        "updated_at": session.get("updated_at"),
        "case_id": session.get("case_id"),
        "message_count": messages_result.count or 0,
        "tenant_id": f"user_{user_id}"
    }


# ══════════════════════════════════════════════════════════════════════════
#  PROTECTED ROUTES (auth required)
# ══════════════════════════════════════════════════════════════════════════

@app.post("/analyze")
@limiter.limit("5/minute")
async def analyze(
    request: Request,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Start analysis pipeline (async) - user-scoped"""
    if len(files) > MAX_UPLOAD_FILES:
        raise HTTPException(status_code=400, detail=f"Too many files. Maximum is {MAX_UPLOAD_FILES}.")

    for file in files:
        await validate_upload_file(file)

    case_id = f"CASE_{uuid.uuid4().hex[:8].upper()}"

    await create_case(user_id, case_id, len(files))
    audit_action(
        user_id=user_id,
        action="case.analysis.start",
        resource_type="case",
        resource_id=case_id,
        metadata={"files_count": len(files)},
    )
    background_tasks.add_task(process_pipeline, case_id, files, user_id)

    return {
        "case_id": case_id,
        "status": "processing",
        "message": "Analysis started. Check /cases/{case_id} for results."
    }

@app.post("/analyze/json")
@limiter.limit("5/minute")
async def analyze_json(
    request: Request,
    files: List[UploadFile] = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Run full pipeline and return JSON result (sync) - user-scoped"""
    if len(files) > MAX_UPLOAD_FILES:
        raise HTTPException(status_code=400, detail=f"Too many files. Maximum is {MAX_UPLOAD_FILES}.")

    for file in files:
        await validate_upload_file(file)

    case_id = f"CASE_{uuid.uuid4().hex[:8].upper()}"

    try:
        await create_case(user_id, case_id, len(files))
        audit_action(
            user_id=user_id,
            action="case.analysis.sync",
            resource_type="case",
            resource_id=case_id,
            metadata={"files_count": len(files)},
        )
        result = await run_pipeline(case_id, files, user_id)
        await update_case(case_id, "completed", result)
        return result
    except Exception as e:
        await update_case(case_id, "failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cases/{case_id}")
async def get_case(
    case_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get case status and results - user-scoped"""
    case = await get_case_by_id(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    progress = get_case_progress(case_id)
    if progress:
        case["status"] = progress.get("status", case.get("status"))
        case["progress"] = progress.get("progress", case.get("progress"))
        case["stage"] = progress.get("stage", case.get("stage"))
        case["result"] = progress.get("result", case.get("result"))
        case["updated_at"] = progress.get("updated_at", case.get("updated_at"))
    return case

@app.get("/cases")
async def list_cases(user_id: str = Depends(get_current_user_id)):
    """List all cases for the current user"""
    return await get_user_cases(user_id)

@app.get("/pdf/{case_id}")
async def download_pdf(
    case_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Download generated PDF for case - user-scoped"""
    case = await get_case_by_id(case_id, user_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if case.get("status") != "completed":
        raise HTTPException(status_code=400, detail="PDF not ready yet")

    pdf_path = f"/outputs/{case_id}.pdf"
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, media_type="application/pdf")

    raise HTTPException(status_code=404, detail="PDF not found")


# ══════════════════════════════════════════════════════════════════════════
#  VERIFICATION ROUTES (protected, user-scoped, linked to cases/sessions)
# ═══════════════════════════════════════════════════════════════════════════

class VerificationRequest(BaseModel):
    """Request body for standalone verification (not part of full pipeline)"""
    evidence_text: str
    extracted_entities: dict
    classification: dict
    retrieved_articles: List[dict]
    evidence_blocks: Optional[List[dict]] = []
    case_id: Optional[str] = None
    session_id: Optional[str] = None

@app.post("/verify")
@limiter.limit("20/minute")
async def verify_evidence(
    request: Request,
    body: VerificationRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Run standalone verification with user scoping.
    Creates audit trail linked to user, case, and session.
    """
    import uuid as uuid_module
    
    verification_case_id = body.case_id or f"v-{uuid_module.uuid4().hex[:8]}"
    sanitized_evidence_text = sanitize_string(body.evidence_text, max_length=16000)
    sanitized_request = {
        "extracted_entities": sanitize_payload(body.extracted_entities),
        "classification": sanitize_payload(body.classification),
        "retrieved_articles": sanitize_payload(body.retrieved_articles),
        "evidence_blocks": sanitize_payload(body.evidence_blocks or []),
    }

    audit_action(
        user_id=user_id,
        action="verification.request",
        resource_type="verification_case",
        resource_id=verification_case_id,
        metadata={
            "source_case_id": body.case_id,
            "session_id": body.session_id,
            "crime_type": sanitized_request["classification"].get("crime_type", "unknown"),
        },
    )
    try:
        resp = await call_microservice(
            "verification",
            "POST",
            f"{SERVICE_URLS['verification']}/verify",
            json_payload={
                "evidence_text": sanitized_evidence_text,
                "extracted_entities": sanitized_request["extracted_entities"],
                "classification": sanitized_request["classification"],
                "retrieved_articles": sanitized_request["retrieved_articles"],
                "evidence_blocks": sanitized_request["evidence_blocks"],
                "case_id": verification_case_id,
                "user_id": user_id,
                "source_case_id": body.case_id,
                "session_id": body.session_id,
            },
            timeout=90.0,
        )
        return resp.json()
    except ServiceCallError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Verification service timeout")

@app.get("/verifications")
async def list_verifications(
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
):
    """List all verification cases for the current user."""
    try:
        resp = await call_microservice(
            "verification",
            "GET",
            f"{SERVICE_URLS['verification']}/cases",
            params={"limit": limit, "offset": offset, "user_id": user_id},
            timeout=10.0,
        )
        return {"verifications": resp.json()}
    except ServiceCallError as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/verifications/{verification_id}")
async def get_verification(
    verification_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get a specific verification case summary."""
    try:
        resp = await call_microservice(
            "verification",
            "GET",
            f"{SERVICE_URLS['verification']}/cases/{verification_id}",
            timeout=10.0,
        )
        data = resp.json()

        # Verify user ownership (or allow if user_id is null - service role created)
        if data.get("user_id") and data["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to view this verification")

        return data
    except ServiceCallError as e:
        if "404" in str(e):
            raise HTTPException(status_code=404, detail="Verification not found")
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/verifications/{verification_id}/rounds")
async def get_verification_rounds(
    verification_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get full round-by-round audit trail for a verification."""
    try:
        summary_resp = await call_microservice(
            "verification",
            "GET",
            f"{SERVICE_URLS['verification']}/cases/{verification_id}",
            timeout=10.0,
        )
        summary = summary_resp.json()
        if summary.get("user_id") and summary["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to view this verification")

        rounds_resp = await call_microservice(
            "verification",
            "GET",
            f"{SERVICE_URLS['verification']}/cases/{verification_id}/rounds",
            timeout=10.0,
        )
        return {"verification_id": verification_id, "rounds": rounds_resp.json()}
    except ServiceCallError as e:
        if "404" in str(e):
            raise HTTPException(status_code=404, detail="Verification not found")
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/verifications/{verification_id}/audit")
async def get_verification_audit(
    verification_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get comprehensive audit including case summary and all rounds."""
    try:
        summary_resp = await call_microservice(
            "verification",
            "GET",
            f"{SERVICE_URLS['verification']}/cases/{verification_id}",
            timeout=10.0,
        )
        summary = summary_resp.json()
        if summary.get("user_id") and summary["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        rounds_resp = await call_microservice(
            "verification",
            "GET",
            f"{SERVICE_URLS['verification']}/cases/{verification_id}/rounds",
            timeout=10.0,
        )
        rounds = rounds_resp.json() if rounds_resp.status_code == 200 else []

        return {
            "verification": summary,
            "rounds": rounds,
            "audit_summary": {
                "total_rounds": len(rounds),
                "crime_type": summary.get("crime_type"),
                "final_status": summary.get("final_status"),
                "final_score": summary.get("final_score"),
                "grade": summary.get("grade"),
                "created_at": summary.get("created_at"),
            }
        }
    except ServiceCallError as e:
        raise HTTPException(status_code=502, detail=str(e))

# ══════════════════════════════════════════════════════════════════════════
#  CHAT ROUTES (protected, user-scoped)
# ══════════════════════════════════════════════════════════════════════════

@app.get("/sessions/list")
async def list_sessions(user_id: str = Depends(get_current_user_id)):
    """List all chat sessions for the current user."""
    sessions = await get_user_sessions(user_id)
    return {"sessions": sessions}

class ChatRequest(BaseModel):
    session_id: str
    user_message: str
    case_context: Optional[dict] = None
    language: str = "ar"  # "ar" for Arabic, "en" for English
    history: Optional[List[dict]] = None  # Recent conversation history for context


@app.post("/chat")
@limiter.limit("20/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Send a chat message - user-scoped with persistence and RAG-enhanced context."""
    import logging
    logger = logging.getLogger("api.chat")

    session_id = body.session_id
    user_message = sanitize_string(body.user_message, max_length=2000)
    case_context = sanitize_payload(body.case_context or {})

    audit_action(
        user_id=user_id,
        action="chat.message",
        resource_type="session",
        resource_id=session_id,
        metadata={"message_length": len(user_message)},
    )

    # Ensure session belongs to user
    sessions = await get_user_sessions(user_id)
    user_session_ids = [s["session_id"] for s in sessions]

    if session_id not in user_session_ids:
        # Auto-create session if it doesn't exist
        await create_chat_session(user_id, session_id, case_context=case_context)

    # Save user message
    await save_chat_message(session_id, "user", user_message, user_id=user_id)

    # ── Retrieve Recent Chat History (last 5 messages for context) ─────────────────
    recent_history = await get_recent_chat_history(session_id, limit=5)
    history_pairs = []
    for i in range(0, len(recent_history) - 1, 2):
        user_msg = recent_history[i] if recent_history[i].get("role") == "user" else None
        assistant_msg = recent_history[i + 1] if recent_history[i + 1].get("role") == "assistant" else None
        if user_msg and assistant_msg:
            history_pairs.append({
                "user": user_msg.get("content", ""),
                "assistant": assistant_msg.get("content", ""),
            })

    # ── Retrieve from User's Personal RAG Collection ─────────────────
    user_documents = []
    try:
        rag_resp = await call_microservice(
            "rag",
            "POST",
            f"{SERVICE_URLS['rag']}/retrieve",
            json_payload={
                "query": user_message,
                "crime_type": case_context.get("classification", {}).get("crime_type", "") if case_context else "",
                "top_k": 5,
                "tenant_id": f"user_{user_id}",
                "transform_strategy": "auto",
            },
            timeout=15.0,
        )
        rag_data = rag_resp.json()
        user_documents = rag_data.get("articles", [])
        logger.info(f"Retrieved {len(user_documents)} user documents for chat")
    except ServiceCallError as e:
        logger.warning(f"User RAG retrieval failed (non-critical): {e}")

    # ── Get Session Uploads for additional context ─────────────────
    try:
        session_uploads = await get_session_uploads(session_id)
        logger.info(f"Retrieved {len(session_uploads)} session uploads for chat")
    except Exception as e:
        logger.warning(f"Failed to get session uploads (non-critical): {e}")
        session_uploads = []

    # Merge user documents into case_context for chatbot
    enhanced_context = case_context or {}
    if user_documents:
        if "user_documents" not in enhanced_context:
            enhanced_context["user_documents"] = []
        enhanced_context["user_documents"].extend([
            {
                "text": doc.get("text", ""),
                "source": doc.get("metadata", {}).get("file_name", "uploaded_file"),
                "relevance_score": doc.get("relevance_score", 0),
            }
            for doc in user_documents
        ])

    # Add session uploads to context
    if session_uploads:
        enhanced_context["session_uploads"] = [
            {
                "file_name": u.get("file_name", ""),
                "file_type": u.get("file_type", ""),
                "indexed_chunks": u.get("indexed_chunks", 0),
            }
            for u in session_uploads
        ]

    # Forward to chatbot service with history
    try:
        resp = await call_microservice(
            "chatbot",
            "POST",
            f"{SERVICE_URLS.get('chatbot', f'{_SELF}/chat')}/chat",
            json_payload={
                "session_id": session_id,
                "user_message": user_message,
                "case_context": enhanced_context,
                "language": body.language,
                "history": history_pairs,
            },
            timeout=60.0,
        )
        reply_data = resp.json()
    except ServiceCallError as e:
        logger.error(f"Chatbot proxy error: {e}")
        reply_data = {"reply": "Sorry, the chatbot service is currently unavailable.", "citations": []}

    # Save assistant reply
    reply_text = reply_data.get("reply", "")
    citations = reply_data.get("citations", [])
    await save_chat_message(session_id, "assistant", reply_text, citations, user_id=user_id)

    return reply_data


@app.post("/chat/upload")
@limiter.limit("10/minute")
async def chat_upload_documents(
    request: Request,
    files: List[UploadFile] = File(...),
    session_id: str = "",
    user_id: str = Depends(get_current_user_id),
):
    session_id = sanitize_string(session_id, max_length=100)
    if len(files) > MAX_UPLOAD_FILES:
        raise HTTPException(status_code=400, detail=f"Too many files. Maximum is {MAX_UPLOAD_FILES}.")
    validated_files = []
    for file in files:
        await validate_upload_file(file)
        validated_files.append(file)

    files = validated_files
    """Upload documents directly for chat (bypasses full analysis pipeline)."""
    import logging
    logger = logging.getLogger("api.chat")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    # Ensure session exists
    if session_id:
        sessions = await get_user_sessions(user_id)
        user_session_ids = [s["session_id"] for s in sessions]
        if session_id not in user_session_ids:
            await create_chat_session(user_id, session_id)

    # Process files with OCR
    ocr_results = []
    for file in files:
        file_bytes = await file.read()
        try:
            resp = await call_microservice(
                "ocr",
                "POST",
                f"{SERVICE_URLS['ocr']}/extract",
                files={"file": (file.filename, file_bytes, file.content_type)},
                timeout=60.0,
            )
            ocr_results.append(resp.json())
        except ServiceCallError as e:
            logger.error(f"OCR failed for {file.filename}: {e}")

    # Index into user's RAG collection
    indexed_count = 0
    if ocr_results:
        index_result = await index_user_documents(
            ocr_results,
            user_id,
            session_id or f"chat_upload_{uuid.uuid4().hex[:8]}"
        )
        indexed_count = index_result.get("indexed", 0)

    # Save upload records to session (if session_id provided)
    if session_id:
        for i, file in enumerate(files):
            ocr_data = ocr_results[i] if i < len(ocr_results) else {}
            await save_session_upload(
                session_id=session_id,
                file_name=file.filename,
                file_type=file.content_type or "application/octet-stream",
                indexed_chunks=indexed_count,
                metadata={
                    "ocr_text_length": len(ocr_data.get("text", "")) if isinstance(ocr_data, dict) else 0,
                    "ocr_entities_count": len(ocr_data.get("entities", [])) if isinstance(ocr_data, dict) else 0,
                }
            )

    audit_action(
        user_id=user_id,
        action="chat.upload_documents",
        resource_type="session",
        resource_id=session_id,
        metadata={"files": len(files), "indexed_chunks": indexed_count},
    )

    return {
        "indexed": indexed_count,
        "files_processed": len(ocr_results),
        "session_id": session_id,
        "message": f"Uploaded {len(files)} file(s). {indexed_count} document chunks indexed for chat."
    }


@app.post("/chat/pdf_trigger")
async def chat_pdf_trigger(
    request: ChatPdfTriggerRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Proxy to chatbot service for PDF generation from chat context."""
    audit_action(
        user_id=user_id,
        action="chat.pdf_trigger",
        resource_type="session",
        resource_id=request.session_id,
    )
    try:
        resp = await call_microservice(
            "chatbot",
            "POST",
            f"{SERVICE_URLS.get('chatbot', f'{_SELF}/chat')}/chat/pdf_trigger",
            json_payload={"session_id": request.session_id},
            timeout=90.0,
        )
        return resp.json()
    except ServiceCallError as e:
        raise HTTPException(status_code=503, detail=str(e))


class SessionRequest(BaseModel):
    session_id: str


@app.post("/chat/reset")
async def reset_chat(
    request: SessionRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Reset a chat session."""
    # Verify session belongs to user
    sessions = await get_user_sessions(user_id)
    user_session_ids = [s["session_id"] for s in sessions]
    if request.session_id not in user_session_ids:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Chat session reset", "session_id": request.session_id}


@app.get("/chat/history")
async def chat_history(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get chat history for a session - user-scoped."""
    # Verify session belongs to user
    sessions = await get_user_sessions(user_id)
    user_session_ids = [s["session_id"] for s in sessions]
    if session_id not in user_session_ids:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = await get_chat_history(session_id)
    return {"session_id": session_id, "messages": messages}


# ══════════════════════════════════════════════════════════════════════════
#  OCR PROXY ROUTES (protected, user-scoped)
# ══════════════════════════════════════════════════════════════════════════

@app.post("/ocr/extract")
@limiter.limit("20/minute")
async def ocr_extract(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    await validate_upload_file(file)
    """Proxy to OCR service: extract text and entities from a single file."""
    import logging
    logger = logging.getLogger("api.ocr")

    file_bytes = await file.read()
    try:
        resp = await call_microservice(
            "ocr",
            "POST",
            f"{SERVICE_URLS['ocr']}/extract",
            files={"file": (file.filename, file_bytes, file.content_type)},
            timeout=60.0,
        )
        result = resp.json()
        conf    = result.get("avg_confidence", 0)
        engine  = result.get("processing_metadata", {}).get("engine_used", "unknown")
        fallback = result.get("processing_metadata", {}).get("fallback_triggered", False)
        logger.info(f"OCR extract: file={file.filename} engine={engine} confidence={conf} fallback={fallback}")
        return result
    except ServiceCallError as e:
        logger.error(f"OCR extract failed: file={file.filename} error={e}")
        raise HTTPException(status_code=503, detail=f"OCR service unavailable: {e}")


@app.post("/ocr/extract/batch")
@limiter.limit("10/minute")
async def ocr_extract_batch(
    request: Request,
    files: List[UploadFile] = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Proxy to OCR service: batch extract from multiple files."""
    import logging
    logger = logging.getLogger("api.ocr")

    if len(files) > MAX_UPLOAD_FILES:
        raise HTTPException(status_code=400, detail=f"Too many files. Maximum is {MAX_UPLOAD_FILES}.")

    try:
        multipart_files = []
        for f in files:
            await validate_upload_file(f)
            file_bytes = await f.read()
            multipart_files.append(("files", (f.filename, file_bytes, f.content_type)))

        resp = await call_microservice(
            "ocr",
            "POST",
            f"{SERVICE_URLS['ocr']}/extract/batch",
            files=multipart_files,
            timeout=120.0,
        )
        result = resp.json()
        logger.info(f"OCR batch: files={len(files)} confidence={result.get('avg_confidence', 0)}")
        return result
    except ServiceCallError as e:
        logger.error(f"OCR batch failed: files={len(files)} error={e}")
        raise HTTPException(status_code=503, detail=f"OCR service unavailable: {e}")


@app.get("/ocr/engines/status")
async def ocr_engines_status(
    user_id: str = Depends(get_current_user_id),
):
    """Proxy to OCR service: get engine status."""
    try:
        resp = await call_microservice(
            "ocr",
            "GET",
            f"{SERVICE_URLS['ocr']}/engines/status",
            timeout=10.0,
        )
        return resp.json()
    except ServiceCallError as e:
        raise HTTPException(status_code=503, detail=f"OCR service unavailable: {e}")


# ── Async OCR job proxy routes ─────────────────────────────────────────────

@app.post("/ocr/jobs/upload")
@limiter.limit("10/minute")
async def ocr_job_upload(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Proxy: upload file and enqueue async OCR job, returns job_id."""
    await validate_upload_file(file)
    file_bytes = await file.read()
    try:
        resp = await call_microservice(
            "ocr",
            "POST",
            f"{SERVICE_URLS['ocr']}/api/v1/ocr/upload",
            files={"file": (file.filename, file_bytes, file.content_type)},
            timeout=30.0,
        )
        return resp.json()
    except ServiceCallError as e:
        raise HTTPException(status_code=503, detail=f"OCR service unavailable: {e}")


@app.get("/ocr/jobs/{job_id}/status")
async def ocr_job_status(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Proxy: poll status of an async OCR job."""
    try:
        resp = await call_microservice(
            "ocr",
            "GET",
            f"{SERVICE_URLS['ocr']}/api/v1/ocr/status/{job_id}",
            timeout=10.0,
        )
        return resp.json()
    except ServiceCallError as e:
        raise HTTPException(status_code=503, detail=f"OCR service unavailable: {e}")


@app.get("/ocr/jobs/{job_id}/result")
async def ocr_job_result(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Proxy: retrieve result of a completed async OCR job."""
    try:
        resp = await call_microservice(
            "ocr",
            "GET",
            f"{SERVICE_URLS['ocr']}/api/v1/ocr/result/{job_id}",
            timeout=10.0,
        )
        return resp.json()
    except ServiceCallError as e:
        raise HTTPException(status_code=503, detail=f"OCR service unavailable: {e}")


@app.post("/ocr/jobs/{job_id}/retry")
@limiter.limit("5/minute")
async def ocr_job_retry(
    request: Request,
    job_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Proxy: re-queue a failed async OCR job."""
    try:
        resp = await call_microservice(
            "ocr",
            "POST",
            f"{SERVICE_URLS['ocr']}/api/v1/ocr/retry/{job_id}",
            timeout=15.0,
        )
        return resp.json()
    except ServiceCallError as e:
        raise HTTPException(status_code=503, detail=f"OCR service unavailable: {e}")


# ══════════════════════════════════════════════════════════════════════════
#  RAG PROXY ROUTES (protected, user-scoped)
# ══════════════════════════════════════════════════════════════════════════

@app.post("/retrieve")
@limiter.limit("30/minute")
async def retrieve_articles(
    request: Request,
    body: RetrieveRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Proxy to RAG service: retrieve relevant law articles."""
    safe_query = sanitize_string(body.query, max_length=2000)
    safe_crime_type = sanitize_string(body.crime_type, max_length=100)
    safe_transform_strategy = sanitize_string(body.transform_strategy, max_length=50)
    safe_tenant_id = sanitize_string(body.tenant_id, max_length=100)
    top_k = max(1, min(body.top_k, 20))

    try:
        resp = await call_microservice(
            "rag",
            "POST",
            f"{SERVICE_URLS['rag']}/retrieve",
            json_payload={
                "query": safe_query,
                "crime_type": safe_crime_type,
                "top_k": top_k,
                "tenant_id": safe_tenant_id,
                "transform_strategy": safe_transform_strategy,
            },
            timeout=30.0,
        )
        return resp.json()
    except ServiceCallError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/classify")
@limiter.limit("20/minute")
async def classify_text(
    request: Request,
    body: ClassifyRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Proxy to classifier service: classify extracted case text."""
    safe_text = sanitize_string(body.text, max_length=20000)
    safe_entities = sanitize_payload(body.entities)

    try:
        resp = await call_microservice(
            "classifier",
            "POST",
            f"{SERVICE_URLS['classifier']}/classify",
            json_payload={"text": safe_text, "entities": safe_entities},
            timeout=30.0,
        )
        return resp.json()
    except ServiceCallError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/stats")
async def rag_stats(user_id: str = Depends(get_current_user_id)):
    """Proxy to RAG service: get service statistics."""
    try:
        resp = await call_microservice(
            "rag",
            "GET",
            f"{SERVICE_URLS['rag']}/stats",
            timeout=10.0,
        )
        return resp.json()
    except ServiceCallError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/faithfulness")
@limiter.limit("20/minute")
async def check_faithfulness(
    request: Request,
    body: FaithfulnessRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Proxy to RAG service: check faithfulness of generated output."""
    safe_query = sanitize_string(body.query, max_length=2000)
    safe_answer = sanitize_string(body.answer, max_length=2000)
    safe_citations = sanitize_payload(body.citations)

    try:
        resp = await call_microservice(
            "rag",
            "POST",
            f"{SERVICE_URLS['rag']}/faithfulness",
            json_payload={"query": safe_query, "answer": safe_answer, "citations": safe_citations},
            timeout=15.0,
        )
        return resp.json()
    except ServiceCallError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/index")
@limiter.limit("5/minute")
async def index_articles(
    request: Request,
    body: IndexRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Proxy to RAG service: index law articles."""
    safe_tenant_id = sanitize_string(body.tenant_id, max_length=100)
    safe_articles = sanitize_payload(body.articles)
    if not isinstance(safe_articles, list):
        raise HTTPException(status_code=400, detail="Articles payload must be a list")
    if len(safe_articles) > 100:
        raise HTTPException(status_code=400, detail="Too many articles in one request. Maximum is 100.")

    try:
        resp = await call_microservice(
            "rag",
            "POST",
            f"{SERVICE_URLS['rag']}/index",
            json_payload={"articles": safe_articles, "tenant_id": safe_tenant_id, "async_ingest": request.async_ingest},
            timeout=60.0,
        )
        return resp.json()
    except ServiceCallError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/tenants")
async def list_tenants(user_id: str = Depends(get_current_user_id)):
    """Proxy to RAG service: list tenant namespaces."""
    try:
        resp = await call_microservice(
            "rag",
            "GET",
            f"{SERVICE_URLS['rag']}/tenants",
            timeout=10.0,
        )
        return resp.json()
    except ServiceCallError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ══════════════════════════════════════════════════════════════════════════
#  PIPELINE LOGIC
# ══════════════════════════════════════════════════════════════════════════

async def process_pipeline(case_id: str, files: List[UploadFile], user_id: str):
    """Background pipeline processing"""
    try:
        result = await run_pipeline(case_id, files, user_id)
        await update_case(case_id, "completed", result)
    except Exception as e:
        publish_case_progress(case_id, "pipeline_failed", {
            "status": "failed",
            "progress": 100,
            "stage": "failed",
            "result": {"error": str(e)},
        })
        await update_case(case_id, "failed", error=str(e))

async def index_user_documents(ocr_results: list, user_id: str, case_id: str) -> dict:
    """Index OCR'd user documents into RAG for chatbot retrieval."""
    import logging
    logger = logging.getLogger("api.pipeline")

    if not ocr_results or not user_id:
        return {"indexed": 0, "error": "No documents or user_id"}

    documents = []
    for i, ocr in enumerate(ocr_results):
        text = ocr.get("full_text", "") or ocr.get("normalized_text", "")
        if not text:
            continue

        # Create document chunks from evidence blocks
        blocks = ocr.get("evidence_blocks", [])
        for block in blocks:
            block_text = block.get("normalized_text", "") or block.get("raw_text", "")
            if block_text:
                documents.append({
                    "text": block_text,
                    "metadata": {
                        "source": "user_upload",
                        "case_id": case_id,
                        "file_name": block.get("file_name", f"file_{i}"),
                        "block_id": block.get("block_id", f"block_{i}"),
                        "doc_type": "evidence",
                        "user_id": user_id,
                    }
                })

        # Also index full text as a document
        if text and len(text) > 50:
            documents.append({
                "text": text[:3000],  # Limit chunk size
                "metadata": {
                    "source": "user_upload",
                    "case_id": case_id,
                    "file_name": blocks[0].get("file_name", f"file_{i}") if blocks else f"file_{i}",
                    "doc_type": "full_text",
                    "user_id": user_id,
                }
            })

    if not documents:
        return {"indexed": 0, "error": "No valid documents to index"}

    try:
        resp = await call_microservice(
            "rag",
            "POST",
            f"{SERVICE_URLS['rag']}/index",
            json_payload={
                "articles": documents,
                "tenant_id": f"user_{user_id}",
                "async_ingest": False,
            },
            timeout=60.0,
        )
        result = resp.json()
        logger.info(f"Indexed {result.get('indexed', 0)} user documents for user={user_id} case={case_id}")
        return result
    except ServiceCallError as e:
        logger.error(f"Failed to index user documents: {e}")
        return {"indexed": 0, "error": str(e)}


async def run_pipeline(case_id: str, files: List[UploadFile], user_id: str = "default") -> dict:
    """Execute full 6-stage pipeline with graceful degradation"""
    import logging
    logger = logging.getLogger("api.pipeline")

    # Track which stages completed successfully
    stages_completed = []
    errors = []

    publish_case_progress(case_id, "pipeline_started", {
        "status": "processing",
        "stage": "ocr",
        "progress": 10,
        "result": {"case_id": case_id},
    })

    # ── Stage 1: OCR & Entity Extraction ──────────────────────────
    ocr_results = []
    ocr_blocks = []
    for file in files:
        file_bytes = await file.read()
        try:
            resp = await call_microservice(
                "ocr",
                "POST",
                f"{SERVICE_URLS['ocr']}/extract",
                files={"file": (file.filename, file_bytes, file.content_type)},
                timeout=60.0,
            )
            ocr_data = resp.json()
            ocr_results.append(ocr_data)
            ocr_blocks.extend(ocr_data.get("evidence_blocks", []))
            meta = ocr_data.get("processing_metadata", {})
            logger.info(
                f"OCR: file={file.filename} engine={meta.get('engine_used')} "
                f"confidence={ocr_data.get('avg_confidence', 0)} "
                f"fallback={meta.get('fallback_triggered', False)} "
                f"status={meta.get('confidence_score', {}).get('status', 'unknown')}"
            )
        except Exception as e:
            logger.error(f"OCR failed for {file.filename}: {e}")
            errors.append({"stage": "ocr", "file": file.filename, "error": str(e)})
            ocr_results.append({"full_text": "", "normalized_text": "", "entities": {}, "avg_confidence": 0, "evidence_blocks": [], "processing_metadata": {}, "language": "unknown"})

    # Combine OCR results
    combined_text = " ".join([r.get("full_text", "") or r.get("normalized_text", "") for r in ocr_results]).strip()
    all_entities = merge_entities([r.get("entities", {}) for r in ocr_results])
    avg_confidence = sum([r.get("avg_confidence", 0) for r in ocr_results]) / max(len(ocr_results), 1)

    # ── Stage 1b: Index User Documents for RAG ───────────────────
    if combined_text and user_id:
        try:
            index_result = await index_user_documents(ocr_results, user_id, case_id)
            if index_result.get("indexed", 0) > 0:
                stages_completed.append("index_user_docs")
                logger.info(f"Indexed {index_result.get('indexed')} user documents into RAG")
        except Exception as e:
            logger.warning(f"User document indexing failed (non-critical): {e}")
            errors.append({"stage": "index_user_docs", "error": str(e)})

    ocr_metadata = {
        "avg_confidence": round(avg_confidence, 3),
        "evidence_blocks": ocr_blocks,
        "per_file": [{
            "file": (r.get("evidence_blocks") or [{}])[0].get("file_name", "unknown") if r.get("evidence_blocks") else "unknown",
            "engine": r.get("processing_metadata", {}).get("engine_used", "unknown"),
            "confidence": r.get("avg_confidence", 0),
            "fallback_triggered": r.get("processing_metadata", {}).get("fallback_triggered", False),
            "confidence_score": r.get("processing_metadata", {}).get("confidence_score"),
            "language": r.get("language", "unknown"),
        } for r in ocr_results],
    }

    if combined_text:
        stages_completed.append("ocr")
        publish_case_progress(case_id, "stage_update", {
            "stage": "classification",
            "progress": 25,
            "result": {"ocr": ocr_metadata, "ocr_confidence": round(avg_confidence, 3)},
        })

    # ── Stage 2: Classification ───────────────────────────────────
    classification = {
        "crime_type": "unknown",
        "confidence": 0.0,
        "reasoning": "Classification service unavailable",
        "suggested_articles": [],
        "missing_evidence": [],
    }
    if combined_text:
        try:
            classify_resp = await call_microservice(
                "classifier",
                "POST",
                f"{SERVICE_URLS['classifier']}/classify",
                json_payload={"text": combined_text, "entities": all_entities},
                timeout=30.0,
            )
            classification = classify_resp.json()
            stages_completed.append("classify")
            publish_case_progress(case_id, "stage_update", {
                "stage": "rag",
                "progress": 40,
                "result": {"classification": classification},
            })
        except ServiceCallError as e:
            logger.error(f"Classification failed: {e}")
            errors.append({"stage": "classify", "error": str(e)})
    else:
        errors.append({"stage": "classify", "error": "No text extracted from OCR"})

    # ── Stage 3: RAG - Legal Retrieval ────────────────────────────
    articles = []
    rag_meta = {"cache_hit": False, "query_strategy": "none", "latency_ms": 0}
    if combined_text and classification.get("crime_type", "unknown") != "unknown":
        try:
            rag_resp = await call_microservice(
                "rag",
                "POST",
                f"{SERVICE_URLS['rag']}/retrieve",
                json_payload={
                    "query": combined_text[:500],
                    "crime_type": classification.get("crime_type", ""),
                    "top_k": 5,
                    "tenant_id": f"user_{user_id}",
                    "transform_strategy": "auto",
                },
                timeout=30.0,
            )
            rag_data = rag_resp.json()
            articles = rag_data.get("articles", [])
            rag_meta = {
                "cache_hit": rag_data.get("cache_hit", False),
                "query_strategy": rag_data.get("query_strategy", "none"),
                "latency_ms": rag_data.get("latency_ms", 0),
            }
            stages_completed.append("rag")
            publish_case_progress(case_id, "stage_update", {
                "stage": "verification",
                "progress": 60,
                "result": {"articles": articles, "rag_meta": rag_meta},
            })
        except ServiceCallError as e:
            logger.error(f"RAG retrieval failed: {e}")
            errors.append({"stage": "rag", "error": str(e)})
    else:
        errors.append({"stage": "rag", "error": "No text or unknown crime type"})

    # ── Stage 4: Verification ─────────────────────────────────────
    verification = {
        "status": "NEEDS_USER_REVIEW",
        "rounds": 0,
        "final_score": 0,
        "score_breakdown": {"grade": "WEAK"},
        "timeline": [],
        "details": [],
        "missing_evidence": classification.get("missing_evidence", []),
    }
    if combined_text and articles:
        try:
            publish_case_progress(case_id, "stage_update", {
                "stage": "verification",
                "progress": 70,
                "result": {"verification": verification},
            })
            verify_resp = await call_microservice(
                "verification",
                "POST",
                f"{SERVICE_URLS['verification']}/verify",
                json_payload={
                    "evidence_text": combined_text,
                    "extracted_entities": all_entities,
                    "classification": classification,
                    "retrieved_articles": articles,
                    "evidence_blocks": ocr_blocks,
                    "case_id": f"v-{case_id}",
                    "user_id": user_id,
                    "source_case_id": case_id,
                    "session_id": None,
                },
                timeout=60.0,
            )
            verification = verify_resp.json()
            stages_completed.append("verify")
        except ServiceCallError as e:
            logger.error(f"Verification failed: {e}")
            errors.append({"stage": "verify", "error": str(e)})
    else:
        errors.append({"stage": "verify", "error": "Insufficient data for verification"})

    result = {
        "case_id": case_id,
        "classification": classification,
        "entities": all_entities,
        "articles": articles,
        "rag_meta": rag_meta,
        "verification": {
            "status": verification.get("status", "NEEDS_USER_REVIEW"),
            "rounds": verification.get("rounds", 0),
            "rounds_left": max(0, 3 - verification.get("rounds", 0)),
            "final_score": verification.get("final_score", 0),
            "score_breakdown": verification.get("score_breakdown", {}),
            "timeline": verification.get("timeline", []),
            "round_details": verification.get("details", []),
            "missing_evidence": verification.get("missing_evidence", classification.get("missing_evidence", [])),
        },
        "score": {
            "total_score": verification.get("final_score", 0),
            "grade": verification.get("score_breakdown", {}).get("grade", "WEAK"),
            "breakdown": verification.get("score_breakdown", {}),
        },
        "timeline": verification.get("timeline", []),
        "ocr": ocr_metadata,
        "ocr_confidence": round(avg_confidence, 3),
        "files_processed": len(files),
        "pipeline_status": {
            "stages_completed": stages_completed,
            "errors": errors,
            "partial": len(errors) > 0,
        }
    }

    publish_case_progress(case_id, "stage_update", {
        "stage": "completed",
        "progress": 100,
        "status": "completed",
        "result": result,
    })

    return result

def merge_entities(entities_list: list) -> dict:
    """Merge entities from multiple files"""
    merged = {"phones": [], "amounts": [], "dates": [], "accounts": [], "emails": [], "urls": [], "ibans": []}

    for entities in entities_list:
        for key in merged:
            if key in entities:
                existing = {e.get("value", e) if isinstance(e, dict) else e for e in merged[key]}
                for e in entities[key]:
                    val = e.get("value", e) if isinstance(e, dict) else e
                    if val not in existing:
                        merged[key].append(e)

    return merged


# ==================== ADMIN ENDPOINTS ====================

# Admin dependency to check if user has admin role
async def get_current_admin(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
    """Dependency to verify user has admin role"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@app.get("/admin/users")
async def admin_list_users(
    limit: int = 50,
    offset: int = 0,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_admin: UserResponse = Depends(get_current_admin)
):
    """List all users with filtering (admin only)"""
    db = get_supabase()
    
    query = db.table("users").select("*")
    
    if role:
        query = query.eq("role", role)
    if is_active is not None:
        query = query.eq("is_active", is_active)
    
    result = query.range(offset, offset + limit - 1).order("created_at", desc=True).execute()
    
    return {
        "users": result.data or [],
        "total": len(result.data or []),
        "limit": limit,
        "offset": offset
    }


@app.get("/admin/users/{user_id}")
async def admin_get_user(user_id: str, current_admin: UserResponse = Depends(get_current_admin)):
    """Get detailed user information (admin only)"""
    db = get_supabase()
    
    result = db.table("users").select("*").eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    return result.data[0]


@app.put("/admin/users/{user_id}")
async def admin_update_user(
    user_id: str,
    update_data: dict,
    current_admin: UserResponse = Depends(get_current_admin)
):
    """Update user information (admin only)"""
    db = get_supabase()
    
    # Prevent changing role (only admins can be admins)
    if "role" in update_data and update_data["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admin role is allowed"
        )
    
    result = db.table("users").update(update_data).eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    return result.data[0]


@app.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, current_admin: UserResponse = Depends(get_current_admin)):
    """Deactivate user account (admin only)"""
    db = get_supabase()
    
    # Prevent deleting admin accounts
    user_result = db.table("users").select("*").eq("id", user_id).execute()
    if not user_result.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = user_result.data[0]
    if user.get("role") == "admin":
        raise HTTPException(
            status_code=403,
            detail="Cannot delete admin accounts"
        )
    
    # Soft delete by setting is_active to False
    result = db.table("users").update({"is_active": False, "deleted_at": datetime.now(timezone.utc).isoformat()}).eq("id", user_id).execute()
    
    return {"message": "User deactivated successfully"}


@app.get("/admin/stats")
async def admin_get_stats(current_admin: UserResponse = Depends(get_current_admin)):
    """Get system statistics (admin only)"""
    db = get_supabase()
    
    # Get user counts
    users_result = db.table("users").select("role, is_active").execute()
    users = users_result.data or []
    
    total_users = len(users)
    active_users = len([u for u in users if u.get("is_active")])
    admin_count = len([u for u in users if u.get("role") == "admin"])
    
    # Get case counts
    cases_result = db.table("cases").select("status").execute()
    cases = cases_result.data or []
    
    total_cases = len(cases)
    processing_cases = len([c for c in cases if c.get("status") == "processing"])
    completed_cases = len([c for c in cases if c.get("status") == "completed"])
    
    # Get verification counts
    verification_result = db.table("verification_cases").select("final_status").execute()
    verifications = verification_result.data or []
    
    total_verifications = len(verifications)
    approved_verifications = len([v for v in verifications if v.get("final_status") == "APPROVED"])
    
    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "inactive": total_users - active_users,
            "admins": admin_count
        },
        "cases": {
            "total": total_cases,
            "processing": processing_cases,
            "completed": completed_cases,
            "other": total_cases - processing_cases - completed_cases
        },
        "verifications": {
            "total": total_verifications,
            "approved": approved_verifications,
            "pending": total_verifications - approved_verifications
        }
    }


@app.get("/admin/cases")
async def admin_list_cases(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    current_admin: UserResponse = Depends(get_current_admin)
):
    """List all cases with filtering (admin only)"""
    db = get_supabase()
    
    query = db.table("cases").select("*")
    
    if status:
        query = query.eq("status", status)
    
    result = query.range(offset, offset + limit - 1).order("created_at", desc=True).execute()
    
    return {
        "cases": result.data or [],
        "total": len(result.data or []),
        "limit": limit,
        "offset": offset
    }


@app.get("/admin/security-events")
async def admin_list_security_events(
    limit: int = 50,
    offset: int = 0,
    severity: Optional[str] = None,
    current_admin: UserResponse = Depends(get_current_admin)
):
    """List security events (admin only)"""
    db = get_supabase()
    
    query = db.table("security_events").select("*")
    
    if severity:
        query = query.eq("severity", severity)
    
    result = query.range(offset, offset + limit - 1).order("created_at", desc=True).execute()
    
    return {
        "events": result.data or [],
        "total": len(result.data or []),
        "limit": limit,
        "offset": offset
    }


@app.post("/admin/security-events/{event_id}/resolve")
async def admin_resolve_security_event(
    event_id: str,
    current_admin: UserResponse = Depends(get_current_admin)
):
    """Mark security event as resolved (admin only)"""
    db = get_supabase()
    
    result = db.table("security_events").update({"resolved": True}).eq("id", event_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Security event not found")
    
    return {"message": "Security event resolved"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
