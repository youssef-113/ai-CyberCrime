OCR Service
EasyOCR runs on Arabic screenshots

Google Vision used as fallback when confidence <55%

Entity extraction for phones, amounts, and dates

Arabic text normalization applied

🎯 LLM Classification
Crime type classification: blackmail, scam, threat, defamation

Citation‑forcing prompt ensures 0 claims without block_id

Confidence score returned

Missing‑evidence list generated

🔍 Multi‑Agent Verification
Attacker agent identifies unsupported claims

Judge agent outputs: APPROVED / NEEDS REVISION

Unsupported claims auto‑removed

Maximum of 3 revision rounds enforced

📄 Arabic PDF
WeasyPrint + Amiri font functioning

Arabic RTL text renders correctly

All 6 PDF sections generated

Score badge + verification stamp included

🐳 Docker + CI/CD
docker-compose up launches all 8 services

All service health checks pass

GitHub Actions CI pipeline green

End‑to‑end pytest suite passes

📚 Legal Knowledge Base
Law 175/2018 (45 articles) indexed in ChromaDB

Egyptian Penal Code (Articles 302–336) indexed

Multilingual embeddings loaded

Citation validator operational

🔎 RAG Retrieval
Hard filter by crime_type functioning

Top‑5 articles returned per query

Citations validated before output

Full article text included in responses

📊 Evidence Scoring
Score calculated on a 0–100% scale

Grades assigned: STRONG / MEDIUM / WEAK

Category‑level breakdown returned

Missing‑evidence list accurate

🤖 Legal Chatbot
Answers in Arabic with law citations

Case‑aware: uses uploaded evidence

Zero invented article numbers

Session memory functioning






///////////////////
# 🚀 Zero-to-Run Complete Guide

## 1. Clone Repository

```bash
git clone https://github.com/youssef-113/ai-CyberCrime.git
cd ai-CyberCrime
```

---

## 2. Conda Environment Setup

```bash
# Create environment (Python 3.11)
conda create -n cybercrime python=3.11 -y

# Activate
conda activate cybercrime

# Install base tools
pip install --upgrade pip setuptools wheel
```

---

## 3. Install All Service Dependencies

```bash
# Install API Gateway
pip install -r services/api/requirements.txt

# Install OCR Service
pip install -r services/ocr/requirements.txt

# Install Classifier Service
pip install -r services/classifier/requirements.txt

# Install RAG Service
pip install -r services/rag/requirements.txt

# Install Verification Service
pip install -r services/verification/requirements.txt

# Install PDF Generation Service
pip install -r services/pdf_gen/requirements.txt
```

---

## 4. Freeze Environment (Save Exact Versions)

```bash
# Save all installed packages
pip freeze > requirements-all.txt

# Or use conda
conda env export > environment.yml
```

---

## 5. Environment Variables

```bash
# Copy example
cp .env.example .env

# Edit with your API keys
nano .env
```

**Required in `.env`:**
```env
LLM_API_KEY=sk-ant-your-anthropic-key
LLM_MODEL=claude-3-haiku-20240307
```

---

## 6. Docker Setup (Recommended - Runs Everything)

```bash
# Build and start ALL services
docker-compose up --build

# Run in background
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop all
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Individual Service Docker Commands:
```bash
# API Gateway only
docker build -t api-gateway services/api
docker run -p 8000:8000 --env-file .env api-gateway

# OCR Service only
docker build -t ocr-service services/ocr
docker run -p 8001:8001 ocr-service
```

---

## 7. Manual Run (Without Docker)

### Terminal 1 - API Gateway (Port 8000)
```bash
conda activate cybercrime
cd services/api
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 2 - OCR Service (Port 8001)
```bash
conda activate cybercrime
cd services/ocr
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Terminal 3 - Classifier Service (Port 8002)
```bash
conda activate cybercrime
cd services/classifier
uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

### Terminal 4 - RAG Service (Port 8003)
```bash
conda activate cybercrime
cd services/rag
uvicorn main:app --host 0.0.0.0 --port 8003 --reload
```

### Terminal 5 - Verification Service (Port 8004)
```bash
conda activate cybercrime
cd services/verification
uvicorn main:app --host 0.0.0.0 --port 8004 --reload
```

### Terminal 6 - PDF Service (Port 8005)
```bash
conda activate cybercrime
cd services/pdf_gen
uvicorn main:app --host 0.0.0.0 --port 8005 --reload
```

---

## 8. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run dev server (Port 3000)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

---

## 9. Quick Start Script (Save as `start-all.sh`)

```bash
#!/bin/bash

# Activate conda
source ~/anaconda3/etc/profile.d/conda.sh
conda activate cybercrime

# Start all services in background
cd services/api && uvicorn main:app --host 0.0.0.0 --port 8000 &
cd services/ocr && uvicorn main:app --host 0.0.0.0 --port 8001 &
cd services/classifier && uvicorn main:app --host 0.0.0.0 --port 8002 &
cd services/rag && uvicorn main:app --host 0.0.0.0 --port 8003 &
cd services/verification && uvicorn main:app --host 0.0.0.0 --port 8004 &
cd services/pdf_gen && uvicorn main:app --host 0.0.0.0 --port 8005 &

echo "All services started!"
echo "API: http://localhost:8000"
echo "OCR: http://localhost:8001"
echo "Classifier: http://localhost:8002"
echo "RAG: http://localhost:8003"
echo "Verification: http://localhost:8004"
echo "PDF: http://localhost:8005"
```

Make executable:
```bash
chmod +x start-all.sh
./start-all.sh
```

---

## 10. Useful Commands Reference

| Task | Command |
|------|---------|
| **Git** | |
| Check status | `git status` |
| Add files | `git add .` |
| Commit | `git commit -m "message"` |
| Push | `git push origin main` |
| Pull | `git pull origin main` |
| **Conda** | |
| Activate | `conda activate cybercrime` |
| Deactivate | `conda deactivate` |
| List envs | `conda env list` |
| Export env | `conda env export > environment.yml` |
| **Docker** | |
| Build | `docker-compose up --build` |
| Start | `docker-compose up -d` |
| Stop | `docker-compose down` |
| View logs | `docker-compose logs -f api-gateway` |
| Rebuild one | `docker-compose up --build ocr` |
| **Python** | |
| Run service | `uvicorn main:app --host 0.0.0.0 --port 8000 --reload` |
| Install deps | `pip install -r requirements.txt` |
| Freeze | `pip freeze > requirements.txt` |
| **Frontend** | |
| Install | `npm install` |
| Dev | `npm run dev` |
| Build | `npm run build` |

---

## 11. Test Everything Works

```bash
# Test API Gateway
curl http://localhost:8000/health

# Test OCR
curl http://localhost:8001/health

# Test Frontend (open in browser)
open http://localhost:3000
```

---

## 🎯 Recommended Flow (Easiest)

```bash
# 1. Clone & setup
git clone https://github.com/youssef-113/ai-CyberCrime.git
cd ai-CyberCrime

# 2. Environment
conda create -n cybercrime python=3.11 -y
conda activate cybercrime

# 3. Copy env file & add your API key
cp .env.example .env
# (edit .env with nano/vim)

# 4. Start everything with Docker (SIMPLEST)
docker-compose up --build

# 5. In another terminal, start frontend
cd frontend && npm install && npm run dev
```

**Access:**
- Frontend: http://localhost:3000
- API: http://localhost:8000
- Qdrant: http://localhost:6333


┌─────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                                    │
│                    User uploads evidence / asks question                      │
└───────────────────────────────┬───────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         API SERVICE (main backend)                          │
│  @/home/youssef/projects/ai-Cybercrime/services/api/                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  Auth (JWT)     │  │  Case mgmt      │  │  Chat           │             │
│  │  users table    │  │  cases table    │  │  sessions       │             │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘             │
│           │                    │                    │                       │
│           └────────────────────┼────────────────────┘                       │
│                                │                                            │
│                    POST /verify (proxied or direct)                        │
│                    with user_id, session_id, case_id                       │
└───────────────────────────────┼────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VERIFICATION SERVICE (standalone)                        │
│  @/home/youssef/projects/ai-Cybercrime/services/verification/                │
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │  /verify    │───▶│  LangGraph  │───▶│  Supabase   │ ──┐                 │
│  │  endpoint   │    │  State Mach │    │  (cloud)    │   │                 │
│  └─────────────┘    └──────┬──────┘    └─────────────┘   │  Dual-write     │
│                            │                             │                 │
│                            ▼                             │                 │
│                    ┌──────────────┐                      │                 │
│                    │ attacker_node│                      │                 │
│                    │  (challenges)│                      │                 │
│                    └──────┬───────┘                      │                 │
│                           │                              │                 │
│                           ▼                              │                 │
│                    ┌──────────────┐                      │                 │
│                    │  judge_node  │                      │                 │
│                    │  (verdict)   │                      │                 │
│                    └──────┬───────┘                      │                 │
│                           │                              │                 │
│                    ┌──────┴───────┐                      │                 │
│                    │ should_cont? │                      │                 │
│                    └──────┬───────┘                      │                 │
│                           │                              │                 │
│              ┌────────────┴────────────┐                 │                 │
│              │  APPROVED / max rounds   │───────────────▶│                 │
│              │  NEEDS_REVISION ────────┼─(loop back)     │                 │
│              └─────────────────────────┘                 │                 │
│                                                           │                 │
│  ┌───────────────────────────────────────────────────────┘                 │
│  │  ┌─────────────────┐    ┌─────────────────┐                             │
│  └──│  SQLite (local)│    │  Supabase (cloud)│◄──┐                         │
│     │  verification.db│    │  PostgreSQL      │   │  verification_cases    │
│     │  (fallback/cache)│  │  verification_rounds│   │                         │
│     └─────────────────┘    └─────────────────┘   │                         │
│                      Data saved to BOTH          │                         │
└──────────────────────────────────────────────────┼─────────────────────────┘
                                                   │
                                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SUPABASE (Shared Database)                            │
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   users     │    │    cases    │    │chat_sessions│    │chat_messages│  │
│  │   (auth)    │◄───┤  (parent)   │◄───┤  (context)  │◄───┤ (triggers)  │  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │
│         │                   │                   │                   │      │
│         │                   │                   │                   │      │
│  ┌──────┴───────────────────┴───────────────────┴───────────────────┴──────┐  │
│  │                    verification_cases                               │  │
│  │  ─ user_id (FK → users.id)                                          │  │
│  │  ─ source_case_id (FK → cases.case_id)                             │  │
│  │  ─ session_id (FK → chat_sessions.session_id)                        │  │
│  └────────────────────────────────┬─────────────────────────────────────┘  │
│                                   │                                         │
│  ┌────────────────────────────────┴─────────────────────────────────────┐  │
│  │                    verification_rounds                               │  │
│  │  ─ case_id (FK → verification_cases.case_id)                        │  │
│  │  ─ chat_message_id (FK → chat_messages.id)                         │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  VIEW: verification_audit_trail (joins all tables for admin dashboard)      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         VERIFICATION GRAPH FLOW                               │
│                                                                              │
│  POST /verify with:                                                          │
│  • evidence_text (the raw evidence)                                           │
│  • extracted_entities (people, dates, amounts)                                │
│  • classification (crime_type: "blackmail", confidence: 0.9)                  │
│  • retrieved_articles (law articles from RAG)                                │
│  • user_id, source_case_id, session_id (from auth context)                    │
│                                                                              │
│  STEP 1: INITIALIZE                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  store.create_case(case_id, crime_type, user_id, source_case_id,      │ │
│  │                    session_id)                                         │ │
│  │                                                                         │ │
│  │  ──▶ Supabase.verification_cases (cloud)                               │ │
│  │  ──▶ SQLite.verification_cases (local cache)                           │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                              │                                               │
│                              ▼                                               │
│  STEP 2: ATTACKER NODE                                                       │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  attacker_agent()                                                       │ │
│  │                                                                         │ │
│  │  1. Pick strategy based on crime_type:                                   │ │
│  │     • BlackmailAttacker → check for threats, demands                     │ │
│  │     • FinancialFraudAttacker → check for transactions, invoices          │ │
│  │     • ForgeryAttacker → check for document inconsistencies                 │ │
│  │                                                                         │ │
│  │  2. Generate structured challenges (keyword-based rules)                 │ │
│  │     Example: "No explicit threat found in evidence"                      │ │
│  │                                                                         │ │
│  │  3. Call Groq LLM (llama-3.3-70b) for additional challenges              │ │
│  │                                                                         │ │
│  │  Output: {                                                                │ │
│  │    combined_text: "structured + LLM challenges",                         │ │
│  │    structured_challenges: ["list", "of", "challenges"]                   │ │
│  │  }                                                                        │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                              │                                               │
│                              ▼                                               │
│  STEP 3: JUDGE NODE                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  judge_agent()                                                          │ │
│  │                                                                         │ │
│  │  1. Build timeline from evidence (dates extracted)                       │ │
│  │                                                                         │ │
│  │  2. Format prompt with:                                                │ │
│  │     • Law articles (legal grounding)                                     │ │
│  │     • Attacker challenges (what to verify)                               │ │
│  │     • Evidence claims (what the user asserts)                              │ │
│  │                                                                         │ │
│  │  3. Call Groq LLM → expects JSON response:                               │ │
│  │     {                                                                     │ │
│  │       "decision": "detailed explanation",                                 │ │
│  │       "status": "APPROVED|NEEDS_REVISION|NEEDS_USER_REVIEW",            │ │
│  │       "articles_cited": ["Law 123", "Article 45"],                       │ │
│  │       "claims_to_drop": ["unsupported claim 1"],                           │ │
│  │       "confidence": 0.85                                                  │ │
│  │     }                                                                     │ │
│  │                                                                         │ │
│  │  4. Validate confidence (clamp 0.0-1.0, default 0.5)                     │ │
│  │                                                                         │ │
│  │  5. Persist round: store.save_round()                                    │ │
│  │     ──▶ Supabase.verification_rounds (with chat_message_id if provided)  │ │
│  │     ──▶ SQLite.verification_rounds (local cache)                         │ │
│  │                                                                         │ │
│  │  6. Drop unsupported claims from claim list                              │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                              │                                               │
│                              ▼                                               │
│  STEP 4: DECISION                                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  should_continue():                                                      │ │
│  │                                                                         │ │
│  │  IF status == "APPROVED" → END (success)                                 │ │
│  │  IF status == "NEEDS_REVISION" AND round < max_rounds → LOOP (step 2)     │ │
│  │  IF max rounds reached → END (NEEDS_USER_REVIEW)                          │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                              │                                               │
│                              ▼                                               │
│  STEP 5: FINALIZE                                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │  calculate_score():                                                     │ │
│  │    • Evidence strength (0-100)                                          │ │
│  │    • Article alignment (0-20)                                           │ │
│  │    • Confidence bonus (0-10)                                            │ │
│  │    • Cap score based on final_status:                                    │ │
│  │      APPROVED = 100 cap, NEEDS_REVISION = 65 cap, else 40 cap           │ │
│  │    • Grade: STRONG (75+), MEDIUM (45+), WEAK (<45)                       │ │
│  │                                                                         │ │
│  │  build_validated_timeline():                                            │ │
│  │    • Extract dates from evidence                                         │ │
│  │    • Detect gaps between events                                          │ │
│  │    • Calculate date_coverage %                                          │ │
│  │                                                                         │ │
│  │  store.update_case_status():                                            │ │
│  │    ──▶ Supabase.verification_cases (final_status, final_score, grade)    │ │
│  │    ──▶ SQLite.verification_cases (local cache)                           │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                              │                                               │
│                              ▼                                               │
│  RESPONSE:                                                                    │
│  {                                                                           │
│    "case_id": "uuid",                                                        │
│    "status": "APPROVED|NEEDS_REVISION|NEEDS_USER_REVIEW",                     │
│    "rounds": 3,                                                              │
│    "round_details": [...],                                                   │
│    "final_score": 87,                                                        │
│    "score_breakdown": {...},                                                 │
│    "grade": "STRONG",                                                         │
│    "timeline": {"events": [...], "gaps": [...], "date_coverage": 0.8}        │
│  }                                                                            │
└─────────────────────────────────────────────────────────────────────────────┘