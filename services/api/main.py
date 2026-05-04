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
    get_recent_chat_history, save_session_upload, get_session_uploads,
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
async def verify_evidence(
    request: VerificationRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Run standalone verification with user scoping.
    Creates audit trail linked to user, case, and session.
    """
    import uuid as uuid_module
    
    # Generate verification case ID if not provided
    verification_case_id = request.case_id or f"v-{uuid_module.uuid4().hex[:8]}"
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{SERVICE_URLS['verification']}/verify",
                json={
                    "evidence_text": request.evidence_text,
                    "extracted_entities": request.extracted_entities,
                    "classification": request.classification,
                    "retrieved_articles": request.retrieved_articles,
                    "evidence_blocks": request.evidence_blocks,
                    "case_id": verification_case_id,
                    "user_id": user_id,
                    "source_case_id": request.case_id,  # Link to parent case if provided
                    "session_id": request.session_id,
                },
                timeout=90.0,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Verification service timeout")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Verification service error: {str(e)}")

@app.get("/verifications")
async def list_verifications(
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
):
    """List all verification cases for the current user."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{SERVICE_URLS['verification']}/cases",
                params={"limit": limit, "offset": offset, "user_id": user_id},
                timeout=10.0,
            )
            resp.raise_for_status()
            return {"verifications": resp.json()}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Verification service error: {str(e)}")

@app.get("/verifications/{verification_id}")
async def get_verification(
    verification_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get a specific verification case summary."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{SERVICE_URLS['verification']}/cases/{verification_id}",
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
            
            # Verify user ownership (or allow if user_id is null - service role created)
            if data.get("user_id") and data["user_id"] != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to view this verification")
            
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail="Verification not found")
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Verification service error: {str(e)}")

@app.get("/verifications/{verification_id}/rounds")
async def get_verification_rounds(
    verification_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get full round-by-round audit trail for a verification."""
    async with httpx.AsyncClient() as client:
        try:
            # First verify ownership
            summary_resp = await client.get(
                f"{SERVICE_URLS['verification']}/cases/{verification_id}",
                timeout=10.0,
            )
            summary_resp.raise_for_status()
            summary = summary_resp.json()
            
            if summary.get("user_id") and summary["user_id"] != user_id:
                raise HTTPException(status_code=403, detail="Not authorized to view this verification")
            
            # Get rounds
            rounds_resp = await client.get(
                f"{SERVICE_URLS['verification']}/cases/{verification_id}/rounds",
                timeout=10.0,
            )
            rounds_resp.raise_for_status()
            return {"verification_id": verification_id, "rounds": rounds_resp.json()}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail="Verification not found")
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Verification service error: {str(e)}")

@app.get("/verifications/{verification_id}/audit")
async def get_verification_audit(
    verification_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get comprehensive audit including case summary and all rounds."""
    async with httpx.AsyncClient() as client:
        try:
            # Get summary
            summary_resp = await client.get(
                f"{SERVICE_URLS['verification']}/cases/{verification_id}",
                timeout=10.0,
            )
            summary_resp.raise_for_status()
            summary = summary_resp.json()
            
            if summary.get("user_id") and summary["user_id"] != user_id:
                raise HTTPException(status_code=403, detail="Not authorized")
            
            # Get rounds
            rounds_resp = await client.get(
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
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Verification service error: {str(e)}")

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
    """Send a chat message - user-scoped with persistence and RAG-enhanced context."""
    import logging
    logger = logging.getLogger("api.chat")

    # Ensure session belongs to user
    sessions = await get_user_sessions(user_id)
    user_session_ids = [s["session_id"] for s in sessions]

    if session_id not in user_session_ids:
        # Auto-create session if it doesn't exist
        await create_chat_session(user_id, session_id, case_context=case_context)

    # Save user message
    await save_chat_message(session_id, "user", user_message)

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
        async with httpx.AsyncClient() as client:
            rag_resp = await client.post(
                f"{SERVICE_URLS['rag']}/retrieve",
                json={
                    "query": user_message,
                    "crime_type": case_context.get("classification", {}).get("crime_type", "") if case_context else "",
                    "top_k": 5,
                    "tenant_id": f"user_{user_id}",
                    "transform_strategy": "auto",
                },
                timeout=15.0,
            )
            if rag_resp.status_code == 200:
                rag_data = rag_resp.json()
                user_documents = rag_data.get("articles", [])
                logger.info(f"Retrieved {len(user_documents)} user documents for chat")
    except Exception as e:
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
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{SERVICE_URLS.get('chatbot', 'http://chatbot:8006')}/chat",
                json={
                    "session_id": session_id,
                    "user_message": user_message,
                    "case_context": enhanced_context,
                    "history": history_pairs,
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


@app.post("/chat/upload")
async def chat_upload_documents(
    files: List[UploadFile] = File(...),
    session_id: str = "",
    user_id: str = Depends(get_current_user_id),
):
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
    async with httpx.AsyncClient() as client:
        for file in files:
            file_bytes = await file.read()
            try:
                resp = await client.post(
                    f"{SERVICE_URLS['ocr']}/extract",
                    files={"file": (file.filename, file_bytes, file.content_type)},
                    timeout=60.0
                )
                resp.raise_for_status()
                ocr_data = resp.json()
                ocr_results.append(ocr_data)
            except Exception as e:
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

    return {
        "indexed": indexed_count,
        "files_processed": len(ocr_results),
        "session_id": session_id,
        "message": f"Uploaded {len(files)} file(s). {indexed_count} document chunks indexed for chat."
    }

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
        result = await run_pipeline(case_id, files, user_id)
        await update_case(case_id, "completed", result)
    except Exception as e:
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
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SERVICE_URLS['rag']}/index",
                json={
                    "articles": documents,
                    "tenant_id": f"user_{user_id}",
                    "async_ingest": False,
                },
                timeout=60.0
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"Indexed {result.get('indexed', 0)} user documents for user={user_id} case={case_id}")
            return result
    except Exception as e:
        logger.error(f"Failed to index user documents: {e}")
        return {"indexed": 0, "error": str(e)}


async def run_pipeline(case_id: str, files: List[UploadFile], user_id: str = "default") -> dict:
    """Execute full 6-stage pipeline with graceful degradation"""
    import logging
    logger = logging.getLogger("api.pipeline")

    # Track which stages completed successfully
    stages_completed = []
    errors = []

    async with httpx.AsyncClient() as client:
        # ── Stage 1: OCR & Entity Extraction ──────────────────────────
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
                resp.raise_for_status()
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
                classify_resp = await client.post(
                    f"{SERVICE_URLS['classifier']}/classify",
                    json={"text": combined_text, "entities": all_entities},
                    timeout=30.0
                )
                classify_resp.raise_for_status()
                classification = classify_resp.json()
                stages_completed.append("classify")
            except Exception as e:
                logger.error(f"Classification failed: {e}")
                errors.append({"stage": "classify", "error": str(e)})
        else:
            errors.append({"stage": "classify", "error": "No text extracted from OCR"})

        # ── Stage 3: RAG - Legal Retrieval ────────────────────────────
        articles = []
        rag_meta = {"cache_hit": False, "query_strategy": "none", "latency_ms": 0}
        if combined_text and classification.get("crime_type", "unknown") != "unknown":
            try:
                rag_resp = await client.post(
                    f"{SERVICE_URLS['rag']}/retrieve",
                    json={
                        "query": combined_text[:500],
                        "crime_type": classification.get("crime_type", ""),
                        "top_k": 5,
                        "tenant_id": user_id,
                        "transform_strategy": "auto",
                    },
                    timeout=30.0
                )
                rag_resp.raise_for_status()
                rag_data = rag_resp.json()
                articles = rag_data.get("articles", [])
                rag_meta = {
                    "cache_hit": rag_data.get("cache_hit", False),
                    "query_strategy": rag_data.get("query_strategy", "none"),
                    "latency_ms": rag_data.get("latency_ms", 0),
                }
                stages_completed.append("rag")
            except Exception as e:
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
        }
        if combined_text and articles:
            try:
                verify_resp = await client.post(
                    f"{SERVICE_URLS['verification']}/verify",
                    json={
                        "evidence_text": combined_text,
                        "extracted_entities": all_entities,
                        "classification": classification,
                        "retrieved_articles": articles,
                        "evidence_blocks": ocr_blocks,
                        "case_id": f"v-{case_id}",
                        "user_id": user_id,
                        "source_case_id": case_id,
                        "session_id": None,  # Could be linked to a chat session if triggered from chat
                    },
                    timeout=60.0
                )
                verify_resp.raise_for_status()
                verification = verify_resp.json()
                stages_completed.append("verify")
            except Exception as e:
                logger.error(f"Verification failed: {e}")
                errors.append({"stage": "verify", "error": str(e)})
        else:
            errors.append({"stage": "verify", "error": "Insufficient data for verification"})

        # ── Build Final Result ────────────────────────────────────────
        result = {
            "case_id": case_id,
            "classification": classification,
            "entities": all_entities,
            "articles": articles,
            "rag_meta": rag_meta,
            "verification": {
                "status": verification.get("status", "NEEDS_USER_REVIEW"),
                "rounds": verification.get("rounds", 0)
            },
            "score": {
                "total_score": verification.get("final_score", 0),
                "grade": verification.get("score_breakdown", {}).get("grade", "WEAK"),
                "breakdown": verification.get("score_breakdown", {})
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
