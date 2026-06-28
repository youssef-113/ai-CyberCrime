# ACEB Backend API Reference

Base URL: `{host}:8000/api` (all frontend-accessible endpoints)

The frontend Axios client (`client.js`) constructs `baseURL = {VITE_API_URL || window.location.origin || https://cyber-crime-production.up.railway.app/}/api`.

All service routes are included in-process via `app.include_router()`, so every endpoint appears in `/docs` and `/openapi.json`.

---

## 1. Auth Endpoints (`/api/auth/*`)

| Method | Path                | Auth     | Rate Limit  | Description                        |
|--------|---------------------|----------|-------------|------------------------------------|
| POST   | `/api/auth/register`| No       | 5/min       | Register new user                  |
| POST   | `/api/auth/login`   | No       | 10/min      | Login with email/password          |
| POST   | `/api/auth/refresh` | No       | 10/min      | Exchange refresh token for new pair|
| POST   | `/api/auth/logout`  | Yes      | —           | Revoke all refresh tokens          |
| POST   | `/api/auth/verify`  | Yes      | —           | Verify session validity            |
| GET    | `/api/auth/me`      | Yes      | —           | Get current user profile           |
| PUT    | `/api/auth/password`| Yes      | —           | Change password                    |
| GET    | `/api/auth/users`   | Yes      | —           | List all users (limited fields)    |

**Frontend sources:** `auth.js`, `client.js` (auto-refresh interceptor), `AuthContext.jsx`

---

## 2. Session Endpoints (`/api/sessions/*`)

| Method | Path                       | Auth | Description                         |
|--------|----------------------------|------|-------------------------------------|
| POST   | `/api/sessions`            | Yes  | Create new chat session             |
| GET    | `/api/sessions/list`       | Yes  | List all user sessions              |
| GET    | `/api/sessions/user/{id}`  | Yes  | List user sessions (paginated)       |
| GET    | `/api/sessions/{id}`       | Yes  | Get session details + message count |

**Frontend sources:** `auth.js`, `endpoints.js`

---

## 3. Analysis Pipeline (`/api/analyze`, `/api/cases`, `/api/pdf`)

| Method | Path                    | Auth | Rate Limit | Description                            |
|--------|-------------------------|------|------------|----------------------------------------|
| POST   | `/api/analyze`          | Yes  | 5/min      | Start analysis pipeline (async)        |
| POST   | `/api/analyze/json`     | Yes  | 5/min      | Run full pipeline, return JSON (sync)  |
| GET    | `/api/cases`            | Yes  | —          | List all user cases                    |
| GET    | `/api/cases/{id}`       | Yes  | —          | Get case status + result               |
| GET    | `/api/cases/{id}/events`| Token | —         | SSE stream for live pipeline progress  |
| GET    | `/api/pdf/{id}`         | Yes  | —          | Download generated PDF for case        |

**Pipeline stages:** upload → OCR → classify → RAG retrieve → verify → PDF

**Frontend sources:** `endpoints.js`, `hooks.js`

---

## 4. Chat Endpoints (`/api/chat/*`)

| Method | Path                     | Auth | Rate Limit | Description                            |
|--------|--------------------------|------|------------|----------------------------------------|
| POST   | `/api/chat`              | Yes  | 20/min     | Send chat message, get LLM reply       |
| POST   | `/api/chat/reset`        | Yes  | —          | Reset chat session history             |
| GET    | `/api/chat/history`      | Yes  | —          | Get full chat history (query: session_id, limit) |
| POST   | `/api/chat/pdf_trigger`  | Yes  | —          | Trigger PDF generation from chat       |
| POST   | `/api/chat/upload`       | Yes  | 10/min     | Upload documents into chat session     |

**Frontend sources:** `endpoints.js`, `auth.js`, `ChatbotPage.jsx`

---

## 5. OCR Endpoints (`/api/ocr/*`)

| Method | Path                           | Auth | Rate Limit | Description                    |
|--------|--------------------------------|------|------------|--------------------------------|
| POST   | `/api/ocr/extract`             | Yes  | 20/min     | Sync OCR on single file        |
| POST   | `/api/ocr/extract/batch`       | Yes  | 10/min     | Sync OCR on multiple files     |
| GET    | `/api/ocr/engines/status`      | Yes  | —          | Per-engine availability status |
| POST   | `/api/ocr/jobs/upload`         | Yes  | 10/min     | Upload file, enqueue async job |
| GET    | `/api/ocr/jobs/{id}/status`    | Yes  | —          | Poll async OCR job status      |
| GET    | `/api/ocr/jobs/{id}/result`    | Yes  | —          | Retrieve completed OCR result  |
| POST   | `/api/ocr/jobs/{id}/retry`     | Yes  | 5/min      | Re-queue failed OCR job        |

**Frontend sources:** `endpoints.js`

---

## 6. Classification Endpoint (`/api/classify`)

| Method | Path             | Auth | Rate Limit | Description                           |
|--------|------------------|------|------------|---------------------------------------|
| POST   | `/api/classify`  | Yes  | 20/min     | Classify extracted text into crime type|

**Body:** `{ text, entities }`

**Frontend source:** `endpoints.js`

---

## 7. RAG / Retrieval Endpoints (`/api/retrieve`, `/api/index`, `/api/faithfulness`, `/api/stats`)

| Method | Path                  | Auth | Rate Limit | Description                         |
|--------|-----------------------|------|------------|-------------------------------------|
| POST   | `/api/retrieve`       | Yes  | 30/min     | Retrieve relevant law articles      |
| POST   | `/api/index`          | Yes  | 5/min      | Index law articles into ChromaDB    |
| POST   | `/api/faithfulness`   | Yes  | 20/min     | Check faithfulness of generated output |
| GET    | `/api/stats`          | Yes  | —          | RAG service statistics              |
| GET    | `/api/tenants`        | Yes  | —          | List tenant namespaces              |

**Frontend sources:** `endpoints.js`

---

## 8. Verification Endpoints (`/api/verify`, `/api/verifications/*`)

| Method | Path                                 | Auth | Rate Limit | Description                           |
|--------|--------------------------------------|------|------------|---------------------------------------|
| POST   | `/api/verify`                        | Yes  | 20/min     | Run multi-agent verification          |
| GET    | `/api/verifications`                 | Yes  | —          | List verification cases (paginated)   |
| GET    | `/api/verifications/{id}`            | Yes  | —          | Get verification case summary         |
| GET    | `/api/verifications/{id}/rounds`     | Yes  | —          | Round-by-round audit trail            |
| GET    | `/api/verifications/{id}/audit`      | Yes  | —          | Comprehensive audit (summary + rounds)|

**Frontend sources:** `endpoints.js`, `VerificationsList.jsx`, `VerificationAudit.jsx`, `VerificationsPage.jsx`

---

## 9. Admin Endpoints (`/api/admin/*`) — Role: `admin` required

| Method | Path                                      | Auth | Description                    |
|--------|-------------------------------------------|------|--------------------------------|
| GET    | `/api/admin/users`                        | Admin| List all users (filtered)      |
| GET    | `/api/admin/users/{id}`                   | Admin| Get detailed user info         |
| PUT    | `/api/admin/users/{id}`                   | Admin| Update user                    |
| DELETE | `/api/admin/users/{id}`                   | Admin| Soft-delete (deactivate) user  |
| GET    | `/api/admin/stats`                        | Admin| System statistics              |
| GET    | `/api/admin/cases`                        | Admin| List all cases (filtered)      |
| GET    | `/api/admin/security-events`              | Admin| List security events           |
| POST   | `/api/admin/security-events/{id}/resolve` | Admin| Mark security event resolved   |

**Frontend source:** `admin.js`

---

## 10. Health & Observability (`/api/health*`, `/api/ready`, `/api/metrics`, `/api/audit`)

| Method | Path                   | Auth | Description                              |
|--------|------------------------|------|------------------------------------------|
| GET    | `/api/health`          | No   | Gateway health + all sub-service health  |
| GET    | `/api/health/aggregate`| No   | Health + LLM status + active case count  |
| GET    | `/api/ready`           | No   | Readiness probe (returns 503 if DB down)  |
| GET    | `/api/metrics`         | No   | Lightweight DB counts + service health   |
| GET    | `/api/audit/events`    | Yes  | User-scoped audit event log              |
| GET    | `/api/`                | No   | Service info root                        |

**Frontend sources:** `endpoints.js`, `useHealth.js`

---

## In-Process Service Routes (internal, not frontend-facing)

These routes exist on the same FastAPI `app` but are called internally by the API gateway via `call_microservice()` over HTTP to `localhost:8000`.

### Chat Service (`/chat`)
| Method | Path                     | Description                     |
|--------|--------------------------|---------------------------------|
| GET    | `/chat/health`           | LLM reachability + session count|
| POST   | `/chat/chat`             | Generate LLM reply              |
| POST   | `/chat/chat/reset`       | Clear in-memory session history |
| GET    | `/chat/chat/history`     | Get in-memory conversation      |
| GET    | `/chat/sessions`         | List active in-memory sessions  |
| POST   | `/chat/chat/pdf_trigger` | Trigger PDF from chat context   |

### Classifier Service (`/classifier`)
| Method | Path                     | Description                     |
|--------|--------------------------|---------------------------------|
| GET    | `/classifier/health`     | LLM + Redis status              |
| GET    | `/classifier/metrics`    | Runtime metrics                 |
| POST   | `/classifier/classify`   | Classify text into crime type   |

### OCR Service (`/ocr`)
| Method | Path                              | Description                     |
|--------|-----------------------------------|---------------------------------|
| GET    | `/ocr/health`                     | Engine + Redis + Celery status  |
| GET    | `/ocr/metrics`                    | Runtime OCR metrics             |
| GET    | `/ocr/engines/status`             | Per-engine details              |
| POST   | `/ocr/extract`                    | Sync single-file OCR            |
| POST   | `/ocr/extract/batch`              | Sync multi-file OCR             |
| POST   | `/ocr/api/v1/ocr/upload`          | Async job upload                |
| POST   | `/ocr/api/v1/ocr/process`         | Sync (alias for `/extract`)     |
| GET    | `/ocr/api/v1/ocr/status/{id}`     | Poll async job status           |
| GET    | `/ocr/api/v1/ocr/result/{id}`     | Get async job result            |
| POST   | `/ocr/api/v1/ocr/retry/{id}`      | Re-queue failed job             |

### RAG Service (`/rag`)
| Method | Path                              | Description                     |
|--------|-----------------------------------|---------------------------------|
| GET    | `/rag/health`                     | ChromaDB + Redis + Celery       |
| GET    | `/rag/stats`                      | Full config + retriever stats   |
| POST   | `/rag/retrieve`                   | Hybrid retrieval + reranking    |
| POST   | `/rag/index`                      | Batch index articles            |
| POST   | `/rag/index/document`             | Index single document           |
| POST   | `/rag/faithfulness`               | Check answer faithfulness       |
| GET    | `/rag/tenants`                    | List tenant collections         |
| DELETE | `/rag/collections/{id}`           | Delete tenant collection        |
| POST   | `/rag/validate-citations`         | Validate article citations      |

### Verification Service (`/verification`)
| Method | Path                              | Description                     |
|--------|-----------------------------------|---------------------------------|
| GET    | `/verification/health`            | Database + LLM status           |
| POST   | `/verification/verify`            | Run Attacker+Judge LangGraph    |
| GET    | `/verification/cases`             | List verification cases         |
| GET    | `/verification/cases/{id}`        | Get case summary                |
| GET    | `/verification/cases/{id}/rounds` | Get round-by-round audit trail  |

### PDF Service (`/pdf`)
| Method | Path                              | Description                     |
|--------|-----------------------------------|---------------------------------|
| GET    | `/pdf/health`                     | WeasyPrint + output dir status  |
| POST   | `/pdf/generate`                   | Generate PDF, return base64     |
| POST   | `/pdf/generate-download`          | Generate PDF, stream download   |

---

## Authentication

### Token-based Auth
- **Access token** (JWT, 15min expiry) — sent as `Authorization: Bearer <token>`
- **Refresh token** (JWT, 7 day expiry) — exchanged at `/api/auth/refresh`
- Auto-refresh: 401 responses trigger the Axios interceptor in `client.js` to call `/api/auth/refresh` with the stored refresh token, then retry the original request.

### SSE Auth
`GET /api/cases/{id}/events?access_token=<token>` — token passed as query param (SSE cannot set headers).

### Admin Auth
Routes under `/api/admin/*` require `role: "admin"` in the user profile.

---

## Common Request/Response Patterns

### Error Responses
```json
{ "detail": "Error description" }
```

### Rate Limit Exceeded (429)
```json
{ "detail": "Rate limit exceeded. Try again later." }
```

### Pagination
List endpoints accept `limit` (default 50) and `offset` (default 0) query parameters.

### SSE (Server-Sent Events)
`/api/cases/{id}/events` streams `event: update` and `event: done` payloads for live pipeline progress.

---

## Environment Variables

| Variable               | Default                    | Description                        |
|------------------------|----------------------------|------------------------------------|
| `CORS_ORIGINS`         | `http://localhost:3000,...` | Comma-separated allowed origins   |
| `MONOLITH_BASE_URL`    | `https://cyber-crime-production.up.railway.app/`     | Internal self-proxy URL           |
| `AUTH_DISABLED`        | `false`                    | Skip auth checks when `true`      |
| `SUPABASE_URL`         | —                          | Supabase project URL              |
| `SUPABASE_KEY`         | —                          | Supabase anon key                 |
| `SUPABASE_SERVICE_KEY` | —                          | Supabase service role key         |
| `ANTHROPIC_API_KEY`    | —                          | Claude API key (chat)             |
| `GEMINI_API_KEY`       | —                          | Gemini API key (chat)             |
| `GROQ_API_KEY`         | —                          | Groq API key (classifier + verify)|
| `LLM_MODEL`            | `llama-3.1-70b-versatile`  | LLM model identifier              |
| `OLLAMA_BASE_URL`      | `http://localhost:11434`   | Ollama endpoint                   |
| `OLLAMA_MODEL`         | `qwen2.5:3b`               | Ollama model name                 |
