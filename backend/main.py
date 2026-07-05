"""
ACEB Backend - Monolithic FastAPI Application
AI Cybercrime Evidence Builder - Production MVP Architecture
"""
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import logging
import uuid

from slowapi.errors import RateLimitExceeded

from services.api.main import router as api_router, limiter as api_limiter
from services.chat.main import router as chat_router
from services.classifier.main import router as classifier_router
from services.ocr.main import router as ocr_router
from services.rag.main import router as rag_router
from services.verification.main import router as verification_router
from services.pdf.main import router as pdf_router

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
except Exception:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aceb.backend")

app = FastAPI(
    title="ACEB Backend",
    description="AI Cybercrime Evidence Builder - Monolithic Backend",
    version="2.0.0"
)

# ── Rate Limiter ────────────────────────────────────────────────────────
app.state.limiter = api_limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Try again later."},
    )

# ── CORS (Starlette built-in — innermost) ─────────────────────────────
_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,https://ai-cyber-crime.vercel.app,http://127.0.0.1:3000").split(",")
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global Exception Handlers ──────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server error")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# ── Logging / Request Context Middleware ───────────────────────────────
@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    logger.info(f"{request.method} {request.url.path} — request_id={request_id}")
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception("Unhandled request error")
        raise
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), payment=()"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    response.headers["X-Download-Options"] = "noopen"
    response.headers["Cache-Control"] = "no-store"
    return response

# ── CORS Preflight Middleware (outermost — added last, runs first) ─────
@app.middleware("http")
async def cors_preflight_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        origin = request.headers.get("origin")
        if origin:
            allowed = [
                o.strip()
                for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,https://ai-cyber-crime.vercel.app,http://127.0.0.1:3000").split(",")
            ]
            if origin in allowed or "*" in allowed:
                response = Response(status_code=200)
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Request-ID, X-Session-ID, X-Tenant-ID, X-CSRF-Token"
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Max-Age"] = "600"
                return response
        response = Response(status_code=204)
        return response
    return await call_next(request)

# ── Startup Warmup ──────────────────────────────────────────────────────
@app.on_event("startup")
async def warmup_models():
    logger.info("Warming up embedding model...")
    try:
        import asyncio
        from sentence_transformers import SentenceTransformer
        model_name = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: SentenceTransformer(model_name))
        logger.info(f"Embedding model warmed up: {model_name}")
    except Exception as e:
        logger.warning(f"Model warmup failed (will load on first request): {e}")

# ── Include All Routers ────────────────────────────────────────────────
app.include_router(api_router)
app.include_router(chat_router)
app.include_router(classifier_router)
app.include_router(ocr_router)
app.include_router(rag_router)
app.include_router(verification_router)
app.include_router(pdf_router)      

# ── Health Check ───────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "aceb-backend",
        "version": "2.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
