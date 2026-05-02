"""API Gateway - Main Orchestrator (Port 8000)"""
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional
import httpx
import uuid
import os
from datetime import datetime

from auth import (
    RegisterRequest, LoginRequest, TokenResponse, RefreshRequest,
    ChangePasswordRequest, UserResponse,
)
from database import (
    register_user, login_user, refresh_access_token, logout_user,
    get_user_by_id, change_user_password, get_supabase,
    create_case, update_case, get_user_cases, get_case_by_id,
    create_chat_session, get_user_sessions, save_chat_message, get_chat_history,
)
from middleware import get_current_user, get_current_user_id

app = FastAPI(
    title="Cybercrime AI - API Gateway",
    description="Main orchestrator for the 6-stage AI pipeline with multi-user auth",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGIN", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Service URLs (from environment or defaults)
SERVICE_URLS = {
    "ocr": os.getenv("OCR_SERVICE_URL", "http://ocr:8001"),
    "classifier": os.getenv("CLASSIFIER_SERVICE_URL", "http://classifier:8002"),
    "rag": os.getenv("RAG_SERVICE_URL", "http://rag:8003"),
    "verification": os.getenv("VERIFICATION_SERVICE_URL", "http://verification:8004"),
    "pdf": os.getenv("PDF_SERVICE_URL", "http://pdf_gen:8005"),
    "chatbot": os.getenv("CHATBOT_SERVICE_URL", "http://chatbot:8006"),
}

class CaseStatus(BaseModel):
    case_id: str
    status: str  # processing, completed, failed
    created_at: str
    result: Optional[dict] = None


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

    async with httpx.AsyncClient() as client:
        for name, url in SERVICE_URLS.items():
            try:
                resp = await client.get(f"{url}/health", timeout=5.0)
                health_status["services"][name] = "healthy" if resp.status_code == 200 else "unhealthy"
            except:
                health_status["services"][name] = "unreachable"

    return health_status


# ══════════════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════

@app.post("/auth/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest):
    """Register a new user account."""
    return await register_user(req)


@app.post("/auth/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Login with email and password."""
    return await login_user(req)


@app.post("/auth/refresh")
async def refresh_token(req: RefreshRequest):
    """Exchange a refresh token for new access + refresh tokens."""
    return await refresh_access_token(req)


@app.post("/auth/logout")
async def logout(user_id: str = Depends(get_current_user_id)):
    """Logout - revokes all refresh tokens."""
    await logout_user(user_id)
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


# ══════════════════════════════════════════════════════════════════════════
#  PROTECTED ROUTES (auth required)
# ══════════════════════════════════════════════════════════════════════════

@app.post("/analyze")
async def analyze(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Start analysis pipeline (async) - user-scoped"""
    case_id = f"CASE_{uuid.uuid4().hex[:8].upper()}"

    # Store case in Supabase
    await create_case(user_id, case_id, len(files))

    # Process in background
    background_tasks.add_task(process_pipeline, case_id, files, user_id)

    return {
        "case_id": case_id,
        "status": "processing",
        "message": "Analysis started. Check /cases/{case_id} for results."
    }

@app.post("/analyze/json")
async def analyze_json(
    files: List[UploadFile] = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Run full pipeline and return JSON result (sync) - user-scoped"""
    case_id = f"CASE_{uuid.uuid4().hex[:8].upper()}"

    try:
        await create_case(user_id, case_id, len(files))
        result = await run_pipeline(case_id, files)
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
#  CHAT ROUTES (protected, user-scoped)
# ══════════════════════════════════════════════════════════════════════════

@app.get("/sessions")
async def list_sessions(user_id: str = Depends(get_current_user_id)):
    """List all chat sessions for the current user."""
    sessions = await get_user_sessions(user_id)
    return {"sessions": sessions}

@app.post("/chat")
async def chat(
    session_id: str,
    user_message: str,
    case_context: Optional[dict] = None,
    user_id: str = Depends(get_current_user_id),
):
    """Send a chat message - user-scoped with persistence."""
    # Ensure session belongs to user
    sessions = await get_user_sessions(user_id)
    user_session_ids = [s["session_id"] for s in sessions]

    if session_id not in user_session_ids:
        # Auto-create session if it doesn't exist
        await create_chat_session(user_id, session_id, case_context=case_context)

    # Save user message
    await save_chat_message(session_id, "user", user_message)

    # Forward to chatbot service
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{SERVICE_URLS.get('chatbot', 'http://chatbot:8006')}/chat",
                json={
                    "session_id": session_id,
                    "user_message": user_message,
                    "case_context": case_context,
                },
                timeout=60.0,
            )
            reply_data = resp.json()
        except Exception:
            reply_data = {"reply": "Sorry, the chatbot service is currently unavailable.", "citations": []}

    # Save assistant reply
    reply_text = reply_data.get("reply", "")
    citations = reply_data.get("citations", [])
    await save_chat_message(session_id, "assistant", reply_text, citations)

    return reply_data

@app.post("/chat/reset")
async def reset_chat(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Reset a chat session."""
    return {"message": "Chat session reset", "session_id": session_id}

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
async def ocr_extract(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Proxy to OCR service: extract text and entities from a single file."""
    import logging
    logger = logging.getLogger("api.ocr")

    file_bytes = await file.read()
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{SERVICE_URLS['ocr']}/extract",
                files={"file": (file.filename, file_bytes, file.content_type)},
                timeout=60.0,
            )
            result = resp.json()
            # Log confidence + failures
            conf = result.get("avg_confidence", 0)
            engine = result.get("processing_metadata", {}).get("engine_used", "unknown")
            fallback = result.get("processing_metadata", {}).get("fallback_triggered", False)
            logger.info(f"OCR extract: file={file.filename} engine={engine} confidence={conf} fallback={fallback}")
            return result
        except Exception as e:
            logger.error(f"OCR extract failed: file={file.filename} error={e}")
            raise HTTPException(status_code=503, detail=f"OCR service unavailable: {e}")


@app.post("/ocr/extract/batch")
async def ocr_extract_batch(
    files: List[UploadFile] = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Proxy to OCR service: batch extract from multiple files."""
    import logging
    logger = logging.getLogger("api.ocr")

    async with httpx.AsyncClient() as client:
        try:
            multipart_files = []
            for f in files:
                file_bytes = await f.read()
                multipart_files.append(("files", (f.filename, file_bytes, f.content_type)))

            resp = await client.post(
                f"{SERVICE_URLS['ocr']}/extract/batch",
                files=multipart_files,
                timeout=120.0,
            )
            result = resp.json()
            logger.info(f"OCR batch: files={len(files)} confidence={result.get('avg_confidence', 0)}")
            return result
        except Exception as e:
            logger.error(f"OCR batch failed: files={len(files)} error={e}")
            raise HTTPException(status_code=503, detail=f"OCR service unavailable: {e}")


@app.get("/ocr/engines/status")
async def ocr_engines_status(
    user_id: str = Depends(get_current_user_id),
):
    """Proxy to OCR service: get engine status."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{SERVICE_URLS['ocr']}/engines/status", timeout=10.0)
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"OCR service unavailable: {e}")


# ══════════════════════════════════════════════════════════════════════════
#  RAG PROXY ROUTES (protected, user-scoped)
# ══════════════════════════════════════════════════════════════════════════

@app.post("/retrieve")
async def retrieve_articles(
    query: str,
    crime_type: str = "",
    top_k: int = 5,
    tenant_id: str = "default",
    transform_strategy: str = "auto",
    user_id: str = Depends(get_current_user_id),
):
    """Proxy to RAG service: retrieve relevant law articles."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{SERVICE_URLS['rag']}/retrieve",
                json={
                    "query": query,
                    "crime_type": crime_type,
                    "top_k": top_k,
                    "tenant_id": tenant_id,
                    "transform_strategy": transform_strategy,
                },
                timeout=30.0,
            )
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"RAG service unavailable: {e}")


@app.get("/stats")
async def rag_stats(user_id: str = Depends(get_current_user_id)):
    """Proxy to RAG service: get service statistics."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{SERVICE_URLS['rag']}/stats", timeout=10.0)
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"RAG service unavailable: {e}")


@app.post("/faithfulness")
async def check_faithfulness(
    query: str,
    answer: str,
    citations: list = [],
    user_id: str = Depends(get_current_user_id),
):
    """Proxy to RAG service: check faithfulness of generated output."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{SERVICE_URLS['rag']}/faithfulness",
                json={"query": query, "answer": answer, "citations": citations},
                timeout=15.0,
            )
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"RAG service unavailable: {e}")


@app.post("/index")
async def index_articles(
    articles: list,
    tenant_id: str = "default",
    async_ingest: bool = False,
    user_id: str = Depends(get_current_user_id),
):
    """Proxy to RAG service: index law articles."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{SERVICE_URLS['rag']}/index",
                json={"articles": articles, "tenant_id": tenant_id, "async_ingest": async_ingest},
                timeout=60.0,
            )
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"RAG service unavailable: {e}")


@app.get("/tenants")
async def list_tenants(user_id: str = Depends(get_current_user_id)):
    """Proxy to RAG service: list tenant namespaces."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{SERVICE_URLS['rag']}/tenants", timeout=10.0)
            return resp.json()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"RAG service unavailable: {e}")


# ══════════════════════════════════════════════════════════════════════════
#  PIPELINE LOGIC
# ══════════════════════════════════════════════════════════════════════════

async def process_pipeline(case_id: str, files: List[UploadFile], user_id: str):
    """Background pipeline processing"""
    try:
        result = await run_pipeline(case_id, files)
        await update_case(case_id, "completed", result)
    except Exception as e:
        await update_case(case_id, "failed", error=str(e))

async def run_pipeline(case_id: str, files: List[UploadFile]) -> dict:
    """Execute full 6-stage pipeline"""
    import logging
    logger = logging.getLogger("api.pipeline")

    async with httpx.AsyncClient() as client:
        # Stage 1: OCR & Entity Extraction (through service layer)
        ocr_results = []
        ocr_blocks = []
        for file in files:
            file_bytes = await file.read()
            try:
                resp = await client.post(
                    f"{SERVICE_URLS['ocr']}/extract",
                    files={"file": (file.filename, file_bytes, file.content_type)},
                    timeout=60.0
                )
                ocr_data = resp.json()
                ocr_results.append(ocr_data)
                # Collect evidence blocks
                ocr_blocks.extend(ocr_data.get("evidence_blocks", []))
                # Log confidence + failures per file
                meta = ocr_data.get("processing_metadata", {})
                logger.info(
                    f"OCR: file={file.filename} engine={meta.get('engine_used')} "
                    f"confidence={ocr_data.get('avg_confidence', 0)} "
                    f"fallback={meta.get('fallback_triggered', False)} "
                    f"status={meta.get('confidence_score', {}).get('status', 'unknown')}"
                )
            except Exception as e:
                logger.error(f"OCR failed for {file.filename}: {e}")
                ocr_results.append({"full_text": "", "entities": {}, "avg_confidence": 0, "evidence_blocks": []})

        # Combine OCR results using structured fields
        combined_text = " ".join([r.get("full_text", "") or r.get("normalized_text", "") for r in ocr_results])
        all_entities = merge_entities([r.get("entities", {}) for r in ocr_results])
        avg_confidence = sum([r.get("avg_confidence", 0) for r in ocr_results]) / max(len(ocr_results), 1)

        # Collect OCR metadata for result
        ocr_metadata = {
            "avg_confidence": round(avg_confidence, 3),
            "evidence_blocks": ocr_blocks,
            "per_file": [{
                "file": r.get("evidence_blocks", [{}])[0].get("file_name", "unknown") if r.get("evidence_blocks") else "unknown",
                "engine": r.get("processing_metadata", {}).get("engine_used", "unknown"),
                "confidence": r.get("avg_confidence", 0),
                "fallback_triggered": r.get("processing_metadata", {}).get("fallback_triggered", False),
                "confidence_score": r.get("processing_metadata", {}).get("confidence_score"),
                "language": r.get("language", "unknown"),
            } for r in ocr_results],
        }

        # Stage 2: Classification
        classify_resp = await client.post(
            f"{SERVICE_URLS['classifier']}/classify",
            json={"text": combined_text, "entities": all_entities},
            timeout=30.0
        )
        classification = classify_resp.json()

        # Stage 3: RAG - Legal Retrieval (Production Pipeline)
        rag_resp = await client.post(
            f"{SERVICE_URLS['rag']}/retrieve",
            json={
                "query": combined_text[:500],
                "crime_type": classification["crime_type"],
                "top_k": 5,
                "tenant_id": user_id,
                "transform_strategy": "auto",
            },
            timeout=30.0
        )
        rag_data = rag_resp.json()
        articles = rag_data.get("articles", [])

        # Stage 4: Verification
        verify_resp = await client.post(
            f"{SERVICE_URLS['verification']}/verify",
            json={
                "evidence_text": combined_text,
                "extracted_entities": all_entities,
                "classification": classification,
                "retrieved_articles": articles
            },
            timeout=60.0
        )
        verification = verify_resp.json()

        # Stage 5: Build result
        result = {
            "case_id": case_id,
            "classification": classification,
            "entities": all_entities,
            "articles": articles,
            "rag_meta": {
                "cache_hit": rag_data.get("cache_hit", False),
                "query_strategy": rag_data.get("query_strategy", "none"),
                "latency_ms": rag_data.get("latency_ms", 0),
            },
            "verification": {
                "status": verification["status"],
                "rounds": verification["rounds"]
            },
            "score": {
                "total_score": verification["final_score"],
                "grade": verification["score_breakdown"].get("grade", "WEAK"),
                "breakdown": verification["score_breakdown"]
            },
            "timeline": verification["timeline"],
            "ocr": ocr_metadata,
            "ocr_confidence": round(avg_confidence, 3),
            "files_processed": len(files)
        }

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
