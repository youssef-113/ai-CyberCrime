# AI Cybercrime Evidence Builder
### Smart Legal Evidence Structuring System (Egyptian Law)

---

## Project Overview

**AI Cybercrime Evidence Builder** is an AI-powered legal-tech system that helps victims of online crimes in Egypt automatically structure, verify, and prepare legally supported complaint reports.

Users upload digital evidence (chat screenshots, PDFs, images). The system extracts key information using AI OCR, organizes everything into a structured timeline, links it to relevant Egyptian legal articles, runs multi-agent verification, and generates a ready-to-submit official complaint report.

---

## Features

- **Multi-format Evidence Upload** — Images (PNG/JPEG/WebP/TIFF), PDFs, TXT files
- **AI-Powered OCR** — Chandra OCR 2 (primary) + PaddleOCR (fallback) + Groq understanding layer
- **Arabic Text Normalization** — Diacritic removal, Alef unification, OCR error correction
- **Entity Extraction** — Phone numbers, financial amounts, dates, emails, URLs, IBANs
- **Automated Crime Classification** — LLM-based detection of blackmail, scam, threat, defamation
- **RAG Legal Retrieval** — Hybrid BM25 + vector search in ChromaDB for Egyptian law articles (Law 175/2018)
- **Multi-Agent Verification** — Attacker + Judge agents (LangGraph) validate claims against evidence and law
- **Evidence Scoring** — Quantifies proof strength (0–100%) with STRONG/MEDIUM/WEAK grading
- **PDF Report Generation** — Complaint-ready documents with WeasyPrint (Arabic RTL support)
- **Legal Chatbot** — Case-aware Q&A assistant with Ollama + Groq
- **User Authentication** — JWT-based with bcrypt password hashing
- **Case History** — Track and manage previous submissions
- **Admin Dashboard** — User management, system stats, security events

---

## Architecture

**Monolithic FastAPI Backend** — All service modules are mounted as sub-applications in a single process:

```
backend/main.py (port 8000)
├── /api         → API Gateway (auth, cases, chat, admin)
├── /chat        → Legal Chatbot
├── /classifier  → Crime Classification
├── /ocr         → OCR & Entity Extraction
├── /rag         → Legal Article Retrieval
├── /verification→ Multi-Agent Verification
└── /pdf         → PDF Report Generation
```

Infrastructure: Redis (cache + Celery broker), Ollama (local LLM), Docker Compose.

---

## Tech Stack

| Component     | Technology                                     |
|---------------|------------------------------------------------|
| Frontend      | React 18, Vite 5, Tailwind CSS 3, Axios        |
| Backend       | Python 3.11, FastAPI, Celery                    |
| Database      | Supabase PostgreSQL (primary), ChromaDB (vector)|
| LLM           | Ollama (qwen2.5:3b — primary), Groq (cloud fallback) |
| OCR           | Chandra OCR 2 (primary), PaddleOCR (fallback)   |
| Cache/Queue   | Redis (cache DB 0, Celery broker DB 1, backend DB 2) |
| PDF           | WeasyPrint + Jinja2 (Arabic RTL support)        |
| Container     | Docker + Docker Compose                         |

---

## Installation

### Prerequisites
- Python 3.11
- Node.js 18+
- Docker & Docker Compose (recommended)

### Quick Start with Docker

```bash
git clone https://github.com/youssef-113/ai-CyberCrime.git
cd ai-CyberCrime

cp .env.example .env
# Edit .env with your API keys (GROQ_API_KEY, SUPABASE_URL, etc.)

docker-compose up --build -d
```

### Manual Setup

See [SETUP.md](SETUP.md) for detailed manual installation instructions.

---

## Environment Variables

| Variable                      | Description                          | Required |
|-------------------------------|--------------------------------------|----------|
| `SUPABASE_URL`                | Supabase project URL                 | Yes      |
| `SUPABASE_KEY`                | Supabase anon key                    | Yes      |
| `SUPABASE_SERVICE_KEY`        | Supabase service role key            | Yes      |
| `GROQ_API_KEY`                | Groq API key (LLM)                   | Yes      |
| `JWT_SECRET_KEY`              | JWT signing secret                   | Yes      |
| `OLLAMA_BASE_URL`             | Ollama server URL                    | Yes      |
| `REDIS_URL`                   | Redis connection string              | Yes      |
| `VITE_API_URL`                | Frontend API base URL                | Yes      |

Full list with defaults in `.env.example`.

---

## Deployment

### Vercel (Frontend)
```bash
cd frontend
npm install
npm run build
# Deploy the dist/ folder to Vercel
```

### Railway (Backend)
- Deploy the `backend/` directory as a Docker service
- Set all environment variables in Railway dashboard
- Add a managed Redis instance
- Add a worker service running the Celery command

### Supabase (Database)
- Create a Supabase project
- Run `scripts/supabase_schema.sql` in SQL Editor
- Copy the project URL and API keys to `.env`

---

## Current Pipeline Flow

```
Upload (images, PDFs, TXT)
  ↓
Chandra OCR 2 (primary OCR engine)
  ↓
PaddleOCR (fallback on low confidence)
  ↓
Groq AI Understanding Layer
  ↓
Arabic Text Normalization
  ↓
Entity Extraction (phones, amounts, dates, emails, URLs, IBANs)
  ↓
Groq LLM Crime Classification
  ↓
RAG Retrieval (Hybrid BM25 + Vector → ChromaDB)
  ↓
Multi-Agent Verification (Attacker + Judge, max 3 rounds)
  ↓
Evidence Scoring (0–100, STRONG/MEDIUM/WEAK)
  ↓
PDF Report Generation (WeasyPrint)

→ Results available via API
→ Chatbot assistant with case context
```

---

## API Documentation

Full API documentation is available in [API_DOCUMENTATION.md](API_DOCUMENTATION.md).

Key endpoints:
- `POST /api/auth/register` — Create account
- `POST /api/auth/login` — Login
- `POST /api/analyze` — Start evidence analysis
- `GET /api/cases` — List cases
- `POST /api/chat` — Chat with legal assistant
- `POST /api/verify` — Run verification
- `GET /api/pdf/{case_id}` — Download PDF

---

## Team

- Youssef Bassiony — AI & System Architecture
- Youssef Rifat — AI & System Architecture
- Youstina Samy — AI & System Architecture
- Hager Soliman — AI & System Architecture
