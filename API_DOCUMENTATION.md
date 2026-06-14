# Cybercrime AI System — Complete API Documentation

## Overview

This document documents all API endpoints in the Cybercrime AI System. The backend is a single FastAPI monolith (port 8000). The frontend always targets the API Gateway at `/api` which is the only layer that enforces auth and persists to the database. Sub-app mounts (`/ocr`, `/chat`, etc.) bypass the auth layer and are called internally by the gateway.

**Routing:**
- Frontend → `http://backend:8000/api/*` (API Gateway)
- Gateway → `http://backend:8000/{mount}/*` (HTTP self-calls to sub-apps)

**Services:**
- **API Gateway** (`/api/*`) — Auth, cases, chat, verification proxies, admin
- **OCR Service** (`/ocr/*`) — Text extraction
- **Classifier Service** (`/classifier/*`) — Crime classification
- **RAG Service** (`/rag/*`) — Legal document retrieval
- **Verification Service** (`/verification/*`) — Multi-agent verification
- **PDF Generator** (`/pdf/*`) — PDF report generation
- **Chatbot Service** (`/chat/*`) — Legal chat assistant

---

## 1. API Gateway — `/api/*`

### 1.1 Public Endpoints (No Auth)

#### `GET /api/`
Service info and pipeline stages.

**Response (200):**
```json
{
  "service": "Cybercrime AI - API Gateway",
  "version": "2.0.0",
  "pipeline_stages": ["upload", "ocr", "classify", "rag", "verify", "pdf"],
  "auth_enabled": true
}
```

#### `GET /api/health`
Check all service health including Supabase connection.

**Response (200):**
```json
{
  "gateway": "healthy",
  "services": {
    "ocr": "healthy",
    "classifier": "healthy",
    "rag": "healthy",
    "verification": "healthy",
    "pdf": "healthy",
    "chatbot": "healthy"
  },
  "database": "connected",
  "supabase": "connected"
}
```

#### `GET /api/health/aggregate`
Aggregate health with LLM connectivity and active case count.

**Response (200):**
```json
{
  "gateway": "healthy",
  "services": { "...": "..." },
  "database": "connected",
  "supabase": "connected",
  "llm": { "groq": "healthy", "fallback": "not_configured" },
  "active_cases": 3
}
```

#### `GET /api/ready`
Readiness probe for deployment.

**Response (200):**
```json
{ "status": "ready", "services": { "ocr": "healthy", "..." } }
```

**Response (503):**
```json
{ "status": "unready", "database": "disconnected" }
```

#### `GET /api/metrics`
Lightweight service metrics.

**Response (200):**
```json
{
  "service": "api-gateway",
  "version": "2.0.0",
  "active_cases": 5,
  "database_counts": {
    "users": 100,
    "cases": 500,
    "sessions": 1000,
    "messages": 5000,
    "audit_events": 10000
  },
  "services": { "ocr": "healthy", "..." }
}
```

---

### 1.2 Authentication Endpoints

All auth endpoints are publicly accessible (no auth required, except `/auth/logout`, `/auth/me`, `/auth/password`).

#### `POST /api/auth/register`
Register a new user account.

**Rate Limit:** 5/minute

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "full_name": "John Doe"
}
```

**Response (201):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "John Doe",
    "is_active": true,
    "is_verified": false,
    "phone": null,
    "language": "ar",
    "timezone": "Africa/Cairo",
    "notification_preferences": {},
    "mfa_enabled": false,
    "role": "user",
    "last_login_at": null,
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

**Errors:**
- `409` — Account with this email already exists
- `422` — Password validation failed (8+ chars, upper, lower, digit, special)

---

#### `POST /api/auth/login`
Login with email and password.

**Rate Limit:** 10/minute

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "John Doe",
    "is_active": true,
    "is_verified": false,
    "role": "user",
    "last_login_at": "2024-01-01T00:00:00Z",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

**Errors:**
- `401` — Invalid credentials

---

#### `POST /api/auth/refresh`
Exchange a refresh token for new access + refresh tokens.

**Rate Limit:** 10/minute

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

---

#### `POST /api/auth/logout`
Logout — revokes all refresh tokens.

**Auth Required:** Yes

**Response (200):**
```json
{ "message": "Logged out successfully" }
```

---

#### `GET /api/auth/me`
Get the current authenticated user's profile.

**Auth Required:** Yes

**Response (200):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_active": true,
  "is_verified": false,
  "phone": null,
  "language": "ar",
  "timezone": "Africa/Cairo",
  "notification_preferences": {},
  "mfa_enabled": false,
  "role": "user",
  "last_login_at": "2024-01-01T00:00:00Z",
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

#### `PUT /api/auth/password`
Change the current user's password.

**Auth Required:** Yes

**Request Body:**
```json
{
  "current_password": "OldPassword123!",
  "new_password": "NewPassword123!"
}
```

**Response (200):**
```json
{ "message": "Password changed successfully. Please login again." }
```

---

#### `GET /api/auth/users`
List all users (admin feature — returns limited fields).

**Auth Required:** Yes

**Response (200):**
```json
{
  "users": [
    { "id": "uuid", "email": "user@example.com", "full_name": "John Doe", "is_active": true, "is_verified": false, "created_at": "..." }
  ]
}
```

---

#### `POST /api/auth/verify`
Verify current session is valid. Returns tenant_id and active session.

**Auth Required:** Yes

**Response (200):**
```json
{
  "valid": true,
  "user": { "...": "..." },
  "tenant_id": "user_{uuid}",
  "session_id": "session-uuid",
  "message": "Session is valid"
}
```

---

### 1.3 Session Management

#### `POST /api/sessions`
Create a new chat session.

**Auth Required:** Yes

**Request Body:**
```json
{
  "case_id": "optional-case-id",
  "title": "Session Title",
  "context": { "crime_type": "blackmail" },
  "language": "ar",
  "model_used": "qwen2.5:3b",
  "temperature": 0.3,
  "max_tokens": 800
}
```

**Response (201):**
```json
{
  "session_id": "uuid",
  "user_id": "uuid",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "case_id": "optional-case-id"
}
```

---

#### `GET /api/sessions/user/{user_id}`
List all chat sessions for a user (paginated).

**Auth Required:** Yes (must match user_id)

**Query Parameters:** `limit` (default 10), `offset` (default 0)

**Response (200):**
```json
{
  "sessions": [
    { "session_id": "uuid", "user_id": "uuid", "is_active": true, "created_at": "...", "case_id": null }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0
}
```

---

#### `GET /api/sessions/{session_id}`
Get session details.

**Auth Required:** Yes

**Response (200):**
```json
{
  "session_id": "uuid",
  "user_id": "uuid",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "case_id": null,
  "message_count": 5,
  "tenant_id": "user_{uuid}"
}
```

---

#### `GET /api/sessions/list`
List all chat sessions for the current user.

**Auth Required:** Yes

**Response (200):**
```json
{
  "sessions": [ { "session_id": "uuid", "..." } ]
}
```

---

### 1.4 Analysis Pipeline

#### `POST /api/analyze`
Start the analysis pipeline (async). Returns immediately with case_id. Background task runs OCR → Classify → RAG → Verify → Aggregate.

**Rate Limit:** 5/minute

**Auth Required:** Yes

**Request:** `multipart/form-data`
- `files`: File[] (max 5 × 10MB each)

**Response (200):**
```json
{
  "case_id": "CASE_XXXXXXXX",
  "status": "processing",
  "message": "Analysis started. Check /cases/{case_id} for results."
}
```

---

#### `POST /api/analyze/json`
Run full pipeline synchronously and return JSON result.

**Rate Limit:** 5/minute

**Auth Required:** Yes

**Request:** `multipart/form-data`
- `files`: File[] (max 5 × 10MB each)

**Response (200):**
```json
{
  "case_id": "CASE_XXXXXXXX",
  "classification": {
    "crime_type": "blackmail",
    "confidence": 0.92,
    "reasoning": "...",
    "suggested_articles": [{ "article_number": "25", "law": "Law 175/2018", "relevance": 0.95 }],
    "missing_evidence": ["Bank statements"]
  },
  "entities": { "phones": ["+201234567890"], "amounts": ["1000 EGP"] },
  "articles": [
    {
      "article_number": "25",
      "law": "Law 175/2018",
      "text": "Article text...",
      "relevance_score": 0.95,
      "penalty_ar": "العقوبة...",
      "summary": "...",
      "keywords": ["blackmail"],
      "chunk_type": "article",
      "parent_text": "..."
    }
  ],
  "rag_meta": { "cache_hit": false, "query_strategy": "hyde", "latency_ms": 150.5 },
  "verification": {
    "status": "APPROVED",
    "rounds": 2,
    "rounds_left": 1,
    "final_score": 85,
    "score_breakdown": { "evidence_strength": 30, "legal_accuracy": 25, "claim_support": 30, "grade": "STRONG" },
    "timeline": [],
    "round_details": [
      { "round": 1, "attacker_challenge": "...", "judge_decision": "...", "status": "APPROVED", "articles_cited": ["25"], "confidence": 0.9 }
    ],
    "missing_evidence": []
  },
  "score": { "total_score": 85, "grade": "STRONG", "breakdown": { "evidence_strength": 30, "..." } },
  "ocr": { "avg_confidence": 0.95, "evidence_blocks": [], "per_file": [] },
  "ocr_confidence": 0.95,
  "files_processed": 1,
  "pipeline_status": {
    "stages_completed": ["ocr", "classify", "rag", "verify"],
    "errors": [],
    "partial": false
  }
}
```

---

### 1.5 Case Management

#### `GET /api/cases`
List all cases for the current user.

**Auth Required:** Yes

**Response (200):**
```json
{
  "cases": [
    {
      "case_id": "CASE_XXXXXXXX",
      "user_id": "uuid",
      "status": "completed",
      "crime_type": "blackmail",
      "files_count": 1,
      "score": 85,
      "grade": "STRONG",
      "created_at": "2024-01-01T00:00:00Z",
      "completed_at": "2024-01-01T01:00:00Z",
      "result": { "evidence_summary": "...", "timeline": [], "law_articles": [] }
    }
  ]
}
```

---

#### `GET /api/cases/{case_id}`
Get case status and results.

**Auth Required:** Yes

**Response (200):**
```json
{
  "case_id": "CASE_XXXXXXXX",
  "user_id": "uuid",
  "status": "completed",
  "crime_type": "blackmail",
  "files_count": 1,
  "score": 85,
  "grade": "STRONG",
  "result": { "evidence_summary": "...", "timeline": [], "law_articles": [] },
  "created_at": "2024-01-01T00:00:00Z",
  "completed_at": "2024-01-01T01:00:00Z"
}
```

**Errors:**
- `404` — Case not found or access denied

---

#### `GET /api/cases/{case_id}/events`
Stream live case progress via Server-Sent Events.

**Auth Required:** Token via query param `?access_token=`

**Response:** `text/event-stream`
```
event: update
data: {"event": "stage_update", "stage": "ocr", "progress": 25, ...}

event: update
data: {"event": "stage_update", "stage": "classification", "progress": 40, ...}

event: done
data: {"status": "completed", "progress": 100, "result": {...}}
```

---

#### `GET /api/pdf/{case_id}`
Download generated PDF for a case.

**Auth Required:** Yes

**Response (200):** Binary PDF file
- `Content-Type: application/pdf`
- `Content-Disposition: attachment; filename={case_id}.pdf`

**Errors:**
- `400` — PDF not ready (case status != "completed")
- `404` — Case not found or PDF file not found

---

### 1.6 Chat Endpoints

#### `POST /api/chat`
Send a chat message. Persists to session history and retrieves RAG-enhanced context.

**Rate Limit:** 20/minute

**Auth Required:** Yes

**Request Body:**
```json
{
  "session_id": "session-uuid",
  "user_message": "What are the penalties for blackmail?",
  "case_context": { "crime_type": "blackmail", "articles": [], "score": {} },
  "language": "ar",
  "history": [{"user": "...", "assistant": "..."}]
}
```

**Response (200):**
```json
{
  "reply": "بموجب المادة 25 من قانون مكافحة جرائم تقنية المعلومات رقم 175 لسنة 2018...",
  "session_id": "session-uuid",
  "citations": ["law175_art25"],
  "confidence_score": null,
  "model_used": null,
  "tokens_used": null,
  "latency_ms": null
}
```

---

#### `POST /api/chat/upload`
Upload documents directly for chat (bypasses full analysis pipeline). OCRs files and indexes into user's RAG collection.

**Rate Limit:** 10/minute

**Auth Required:** Yes

**Request:** `multipart/form-data`
- `files`: File[] (max 5)
- `session_id` (query param, optional)

**Response (200):**
```json
{
  "indexed": 10,
  "files_processed": 2,
  "session_id": "session-uuid",
  "message": "Uploaded 2 file(s). 10 document chunks indexed for chat."
}
```

---

#### `POST /api/chat/pdf_trigger`
Trigger PDF generation from chat context.

**Auth Required:** Yes

**Request Body:**
```json
{ "session_id": "session-uuid" }
```

**Response (200):**
```json
{
  "status": "generated",
  "case_id": "case-uuid",
  "pdf_size": 102400,
  "message": "يمكنك تنزيل المحضر من صفحة تنزيل المحضر"
}
```

---

#### `POST /api/chat/reset`
Reset a chat session.

**Auth Required:** Yes

**Request Body:**
```json
{ "session_id": "session-uuid" }
```

**Response (200):**
```json
{ "message": "Chat session reset", "session_id": "session-uuid" }
```

---

#### `GET /api/chat/history`
Get chat history for a session.

**Auth Required:** Yes

**Query Parameters:** `session_id` (required)

**Response (200):**
```json
{
  "session_id": "session-uuid",
  "messages": [
    { "role": "user", "content": "User message", "citations": [], "created_at": "..." },
    { "role": "assistant", "content": "Assistant response", "citations": ["law175_art25"], "created_at": "..." }
  ]
}
```

---

### 1.7 Verification Endpoints

#### `POST /api/verify`
Run standalone multi-agent verification (not part of full pipeline).

**Rate Limit:** 20/minute

**Auth Required:** Yes

**Request Body:**
```json
{
  "evidence_text": "Evidence text with details...",
  "extracted_entities": { "phones": ["+201234567890"], "amounts": ["1000 EGP"] },
  "classification": { "crime_type": "blackmail", "confidence": 0.92 },
  "retrieved_articles": [
    { "article_number": "25", "law": "Law 175/2018", "text": "Article text..." }
  ],
  "evidence_blocks": [],
  "case_id": "optional-case-id",
  "session_id": "optional-session-id"
}
```

**Response (200):**
```json
{
  "case_id": "verification-uuid",
  "status": "APPROVED",
  "rounds": 2,
  "round_details": [
    {
      "round": 1,
      "attacker_challenge": "Challenge text",
      "judge_decision": "Decision text",
      "status": "APPROVED",
      "articles_cited": ["25"],
      "claims_to_drop": [],
      "confidence": 0.9,
      "latency_ms": 1200
    }
  ],
  "final_score": 85,
  "score_breakdown": { "evidence_strength": 30, "legal_accuracy": 25, "claim_support": 30, "grade": "STRONG" },
  "grade": "STRONG",
  "timeline": { "started_at": "...", "completed_at": "..." }
}
```

---

#### `GET /api/verifications`
List all verification cases for the current user.

**Auth Required:** Yes

**Query Parameters:** `limit` (default 50), `offset` (default 0)

**Response (200):**
```json
{
  "verifications": { /* passthrough from verification service */ }
}
```

---

#### `GET /api/verifications/{verification_id}`
Get a specific verification case summary.

**Auth Required:** Yes

**Response (200):**
```json
{
  "case_id": "verification-uuid",
  "user_id": "user-uuid",
  "source_case_id": "parent-case-id",
  "crime_type": "blackmail",
  "final_status": "APPROVED",
  "final_score": 85,
  "total_rounds": 2,
  "grade": "STRONG",
  "created_at": "...",
  "updated_at": "..."
}
```

**Errors:**
- `403` — Not authorized (verification belongs to another user)
- `404` — Verification not found

---

#### `GET /api/verifications/{verification_id}/rounds`
Get full round-by-round audit trail.

**Auth Required:** Yes

**Response (200):**
```json
{
  "verification_id": "uuid",
  "rounds": [ /* round data from verification service */ ]
}
```

---

#### `GET /api/verifications/{verification_id}/audit`
Get comprehensive audit including case summary and all rounds.

**Auth Required:** Yes

**Response (200):**
```json
{
  "verification": { "...": "..." },
  "rounds": [],
  "audit_summary": {
    "total_rounds": 2,
    "crime_type": "blackmail",
    "final_status": "APPROVED",
    "final_score": 85,
    "grade": "STRONG",
    "created_at": "..."
  }
}
```

---

### 1.8 OCR Proxy Endpoints (via Gateway)

#### `POST /api/ocr/extract`
Extract text and entities from a single file.

**Rate Limit:** 20/minute

**Auth Required:** Yes

**Request:** `multipart/form-data` — `file`: File

**Response (200):**
```json
{
  "evidence_blocks": [
    { "block_id": "E001", "file_name": "evidence.jpg", "raw_text": "...", "normalized_text": "...", "confidence": 0.95, "quality_flag": "OK", "ocr_source": "chandra", "bbox": null }
  ],
  "entities": { "phones": ["+201234567890"], "amounts": ["1000 EGP"] },
  "full_text": "Extracted text...",
  "normalized_text": "Normalized text...",
  "avg_confidence": 0.95,
  "language": "ar",
  "processing_metadata": {
    "processing_time_ms": 1500.5,
    "engine_used": "chandra",
    "fallback_triggered": false,
    "blocks_count": 3,
    "threat_indicators": [],
    "threat_score": 0,
    "confidence_score": { "average": 0.95, "minimum": 0.85, "weighted_average": 0.93, "status": "high" },
    "groq_entities": null
  }
}
```

#### `POST /api/ocr/extract/batch`
Batch extract from multiple files.

**Rate Limit:** 10/minute

**Auth Required:** Yes

**Request:** `multipart/form-data` — `files`: File[] (max 5)

#### `GET /api/ocr/engines/status`
Get OCR engine status.

**Auth Required:** Yes

#### `POST /api/ocr/jobs/upload`
Upload file and enqueue async OCR job via Celery.

**Rate Limit:** 10/minute

**Auth Required:** Yes

**Response (200):**
```json
{ "job_id": "celery-task-id", "status": "PENDING", "message": "Job enqueued" }
```

#### `GET /api/ocr/jobs/{job_id}/status`
Poll status of async OCR job.

#### `GET /api/ocr/jobs/{job_id}/result`
Retrieve result of a completed async OCR job.

#### `POST /api/ocr/jobs/{job_id}/retry`
Re-queue a failed OCR job.

**Rate Limit:** 5/minute

---

### 1.9 Classification Proxy

#### `POST /api/classify`
Classify crime type from text and entities.

**Rate Limit:** 20/minute

**Auth Required:** Yes

**Request Body:**
```json
{
  "text": "Threatening message text",
  "entities": { "phones": ["+201234567890"] }
}
```

**Response (200):**
```json
{
  "crime_type": "blackmail",
  "confidence": 0.92,
  "key_indicators": ["threat to publish", "demand for payment"],
  "claims": ["Defendant threatened to publish private photos unless complainant paid EGP 10,000"],
  "missing_evidence": ["Bank transfer receipts"],
  "classifier_notes": "Clear pattern of electronic blackmail under Article 25 of Law 175/2018",
  "suggested_articles": [
    { "article_number": "25", "law": "Law 175/2018", "law_ar": "قانون 175 لسنة 2018", "relevance": 0.95, "crime_types": ["blackmail", "threat"] }
  ]
}
```

---

### 1.10 RAG Proxy Endpoints

#### `POST /api/retrieve`
Retrieve relevant legal articles.

**Rate Limit:** 30/minute

**Auth Required:** Yes

**Request Body:**
```json
{
  "query": "What are the penalties for blackmail?",
  "crime_type": "blackmail",
  "top_k": 5,
  "tenant_id": "default",
  "transform_strategy": "auto"
}
```

**Response (200):**
```json
{
  "articles": [
    {
      "article_number": "25",
      "law": "Law 175/2018",
      "text": "Article text...",
      "relevance_score": 0.95,
      "penalty_ar": "العقوبة...",
      "summary": "Article summary",
      "keywords": ["blackmail", "penalty"],
      "chunk_type": "article",
      "parent_text": "Full article text"
    }
  ],
  "cache_hit": false,
  "cache_source": null,
  "query_strategy": "hyde",
  "latency_ms": 150.5,
  "citation_validation_status": {
    "valid": [],
    "invalid": [],
    "status": "PASSED",
    "validation_details": {}
  }
}
```

#### `POST /api/classify`
(Proxy — same as section 1.9)

#### `GET /api/stats`
Get RAG service statistics.

#### `POST /api/faithfulness`
Check faithfulness of generated output against citations.

#### `POST /api/index`
Index law articles into ChromaDB.

**Rate Limit:** 5/minute

#### `GET /api/tenants`
List tenant namespaces.

#### `GET /api/audit/events`
List audit events for current user.

---

### 1.11 Admin Endpoints

All admin endpoints require `role: "admin"` in user profile.

#### `GET /api/admin/users`
List all users with filtering.

**Query Parameters:** `limit` (50), `offset` (0), `role`, `is_active`

#### `GET /api/admin/users/{user_id}`
Get detailed user information.

#### `PUT /api/admin/users/{user_id}`
Update user information.

#### `DELETE /api/admin/users/{user_id}`
Deactivate user account (soft delete via `is_active = false`).

#### `GET /api/admin/stats`
Get system statistics (user counts, case counts, verification counts).

#### `GET /api/admin/cases`
List all cases with filtering.

**Query Parameters:** `limit`, `offset`, `status`

#### `GET /api/admin/security-events`
List security events.

**Query Parameters:** `limit`, `offset`, `severity`

#### `POST /api/admin/security-events/{event_id}/resolve`
Mark security event as resolved.

---

## 2. OCR Service — `/ocr/*`

#### `GET /ocr/health`
Liveness + readiness probe.

**Response (200):**
```json
{
  "status": "healthy",
  "service": "ocr",
  "version": "2.0.0",
  "engine_ready": true,
  "engines": {"chandra": true, "paddle": true, "groq": true},
  "redis": "connected",
  "celery": "connected",
  "limits": { "max_file_size_mb": 10, "max_image_px": 8000, "max_pdf_pages": 20, "ocr_timeout_s": 30 }
}
```

#### `GET /ocr/metrics`
OCR runtime metrics.

#### `GET /ocr/engines/status`
Per-engine availability and config.

#### `POST /ocr/extract`
Extract text + entities from single file (sync).

**Request:** `multipart/form-data` — `file`: File

**Response (200):** `OCRResponse`

#### `POST /ocr/extract/batch`
Batch-process multiple files (sync, parallel). Max 10 files.

#### `POST /ocr/api/v1/ocr/upload`
Upload file + enqueue async Celery job.

#### `POST /ocr/api/v1/ocr/process`
Process file synchronously (alias for sync).

#### `GET /ocr/api/v1/ocr/status/{job_id}`
Poll Celery job status.

#### `GET /ocr/api/v1/ocr/result/{job_id}`
Retrieve completed Celery job result.

#### `POST /ocr/api/v1/ocr/retry/{job_id}`
Re-queue a failed OCR job.

---

## 3. Classifier Service — `/classifier/*`

#### `GET /classifier/health`
**Response (200):**
```json
{
  "status": "healthy",
  "service": "classifier",
  "version": "1.0.0",
  "llm": "ok",
  "redis": "ok"
}
```

#### `GET /classifier/metrics`
Runtime metrics (classifications count, latency, success rate).

#### `POST /classifier/classify`
Classify crime type.

**Request Body:**
```json
{
  "text": "Threatening message text",
  "entities": { "phones": ["+201234567890"] },
  "user_id": "optional",
  "session_id": "optional"
}
```

**Response (200):** `ClassificationOutput` (same structure as `/api/classify`)

---

## 4. RAG Service — `/rag/*`

#### `GET /rag/health`
**Response (200):**
```json
{
  "status": "healthy",
  "service": "rag",
  "version": "2.0.0",
  "chroma": "ok",
  "redis": "ok",
  "celery": "ok",
  "metrics": { "...": "..." }
}
```

#### `GET /rag/stats`
Full service statistics including config, retriever, cache, metrics.

#### `POST /rag/retrieve`
Hybrid retrieval with query transformation, caching, reranking, and citation validation.

#### `POST /rag/index`
Index articles synchronously or via Celery task.

#### `POST /rag/index/document`
Index a single document.

#### `POST /rag/faithfulness`
Check faithfulness of answer against citations.

#### `GET /rag/tenants`
List tenant collections.

#### `POST /rag/validate-citations`
Validate cited articles exist in ChromaDB.

#### `DELETE /rag/collections/{tenant_id}`
Delete a tenant's collection (admin).

---

## 5. Verification Service — `/verification/*`

#### `GET /verification/health`
**Response (200):**
```json
{
  "status": "healthy",
  "service": "verification",
  "version": "2.0.0",
  "store": "supabase",
  "database": "ok",
  "llm": "ok"
}
```

#### `POST /verification/verify`
Run multi-agent verification via LangGraph with audit trail.

#### `GET /verification/cases`
List all verification cases. Query params: `limit`, `offset`, `user_id`.

#### `GET /verification/cases/{case_id}`
Get case-level summary.

#### `GET /verification/cases/{case_id}/rounds`
Get full round-by-round audit trail.

---

## 6. PDF Generator — `/pdf/*`

#### `GET /pdf/health`
**Response (200):**
```json
{
  "status": "healthy",
  "service": "pdf-gen",
  "version": "1.0.0",
  "outputs_dir": "/outputs",
  "outputs": "writable",
  "weasyprint": "ok"
}
```

#### `POST /pdf/generate`
Generate PDF report and return metadata + base64.

**Request Body:**
```json
{
  "case_id": "case-uuid",
  "crime_type": "blackmail",
  "evidence_summary": "Summary of evidence",
  "timeline": [{"date": "2024-01-01", "description": "Event description"}],
  "law_articles": [{ "article_number": "25", "law": "Law 175/2018", "text": "...", "penalty_ar": "..." }],
  "score": 85,
  "grade": "STRONG",
  "complainant_name": "John Doe",
  "language": "ar"
}
```

**Response (200):**
```json
{
  "status": "generated",
  "filename": "case-uuid_20240101_120000.pdf",
  "path": "/outputs/case-uuid_20240101_120000.pdf",
  "size_bytes": 102400,
  "pdf_base64": "base64-encoded-pdf"
}
```

#### `POST /pdf/generate-download`
Generate PDF and return as downloadable binary file.

---

## 7. Chatbot Service — `/chat/*`

#### `GET /chat/health`
**Response (200):**
```json
{
  "status": "healthy",
  "service": "chatbot",
  "version": "llm=ollama model=qwen2.5:3b ollama=ok sessions=5 max_history=20"
}
```

#### `POST /chat/chat`
Send a message to the legal chatbot. (Note: mounted at `/chat`, so full path is `/chat/chat`)

#### `POST /chat/chat/reset`
Clear session history.

#### `GET /chat/chat/history`
Get conversation history. Query param: `session_id`.

#### `GET /chat/sessions`
List all active sessions (admin/debug).

#### `POST /chat/chat/pdf_trigger`
Trigger PDF generation from chat context.

---

## 8. Standard Error Responses

All endpoints return errors in this format:

```json
{
  "error": {
    "code": 400,
    "message": "Error description",
    "request_id": "uuid"
  }
}
```

| Status | Code | Description                              |
|--------|------|------------------------------------------|
| 400    | 400  | Bad request — invalid input              |
| 401    | 401  | Unauthorized — missing/invalid token     |
| 403    | 403  | Forbidden — insufficient permissions     |
| 404    | 404  | Not found — resource not found           |
| 409    | 409  | Conflict — resource already exists       |
| 413    | 413  | Payload too large                        |
| 415    | 415  | Unsupported media type                   |
| 429    | 429  | Rate limit exceeded                      |
| 500    | 500  | Internal server error                    |
| 502    | 502  | Bad gateway — downstream service error   |
| 503    | 503  | Service unavailable                      |
| 504    | 504  | Gateway timeout                          |

---

## 9. Authentication Flow

```
Client → POST /api/auth/register
  ↓
API Gateway → Validate password, hash with bcrypt(12)
  ↓
Insert into users table in Supabase
  ↓
Create JWT access_token (30 min) + refresh_token (7 days)
  ↓
Log audit event
  ↓
Return tokens + user data

Protected routes:
  ↓
Client adds Authorization: Bearer {access_token}
  ↓
API Gateway decodes JWT, validates type=access, checks expiry
  ↓
Looks up user by sub (user_id), verifies is_active
  ↓
Returns user to handler
```

---

## 10. Rate Limits

| Endpoint                 | Limit     |
|--------------------------|-----------|
| `POST /auth/register`    | 5/minute  |
| `POST /auth/login`       | 10/minute |
| `POST /auth/refresh`     | 10/minute |
| `POST /analyze`          | 5/minute  |
| `POST /analyze/json`     | 5/minute  |
| `POST /chat`             | 20/minute |
| `POST /chat/upload`      | 10/minute |
| `POST /verify`           | 20/minute |
| `POST /classify`         | 20/minute |
| `POST /retrieve`         | 30/minute |
| `POST /index`            | 5/minute  |
| `POST /ocr/extract`      | 20/minute |
| `POST /ocr/extract/batch`| 10/minute |
| `POST /ocr/jobs/upload`  | 10/minute |
| `POST /ocr/jobs/retry`   | 5/minute  |
