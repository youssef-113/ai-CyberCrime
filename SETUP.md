# Zero-to-Run Complete Setup Guide

Complete setup guide for AI Cybercrime Evidence Builder — from fresh machine to running system.

---

## Prerequisites

- [ ] Git
- [ ] Docker & Docker Compose (for containerized setup)
- [ ] **OR** Python 3.11 + Node.js 18+ (for local setup)
- [ ] 8GB+ RAM
- [ ] Ports 3000, 8000, 6379, 11434 available

---

## 1. Clone Repository

```bash
git clone https://github.com/youssef-113/ai-CyberCrime.git
cd ai-CyberCrime
```

---

## 2. Environment Variables

```bash
cp .env.example .env
# Edit .env with your API keys
```

**Required:**
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key-here
SUPABASE_SERVICE_KEY=your-service-role-key-here
GROQ_API_KEY=gsk_your_groq_key_here
JWT_SECRET_KEY=generate-a-strong-random-key
```

---

## 3. Docker Setup (Recommended)

```bash
# Build and start all services
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop all
docker-compose down
```

This starts:
- **backend** — FastAPI monolith (port 8000)
- **backend-worker** — Celery worker for async OCR tasks
- **frontend** — React + Vite (port 3000)
- **redis** — Cache + Celery broker (port 6379)
- **ollama** — Local LLM (port 11434)

---

## 4. Database Setup

1. Create a Supabase project at https://supabase.com
2. Go to SQL Editor
3. Run the contents of `scripts/supabase_schema.sql`
4. Copy your project URL and API keys to `.env`

---

## 5. Setup Without Docker (Development)

### Backend

```bash
pip install -r backend/requirements.txt

# Run FastAPI monolith
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Celery Worker

```bash
# In a separate terminal
cd backend
celery -A services.common.celery_app worker --loglevel=info --concurrency=2 -Q ocr,rag,classifier,default
```

### Redis

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### Ollama

```bash
docker run -d -p 11434:11434 ollama/ollama:latest
# Pull the model
docker exec -it <container_id> ollama pull qwen2.5:3b
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## 6. Verify Setup

```bash
curl https://cyber-crime-production.up.railway.app//health
curl https://cyber-crime-production.up.railway.app//api/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "aceb-backend",
  "version": "2.0.0"
}
```

---

## Access URLs

| Service      | URL                           | Purpose                   |
|--------------|-------------------------------|---------------------------|
| Frontend     | http://localhost:3000          | React UI                  |
| API Docs     | https://cyber-crime-production.up.railway.app//api/docs | Swagger UI                |
| API Gateway  | https://cyber-crime-production.up.railway.app//api      | Main orchestrator         |
| OCR          | https://cyber-crime-production.up.railway.app//ocr      | Text extraction           |
| Classifier   | https://cyber-crime-production.up.railway.app//classifier| Crime classification      |
| RAG          | https://cyber-crime-production.up.railway.app//rag      | Law retrieval             |
| Verification | https://cyber-crime-production.up.railway.app//verification| Multi-agent check       |
| PDF Gen      | https://cyber-crime-production.up.railway.app//pdf      | Report generation         |
| Chatbot      | https://cyber-crime-production.up.railway.app//chat     | Legal assistant           |

---

## Architecture Note

The backend is a **single FastAPI monolith** (not microservices). All service modules are mounted as sub-applications in-process under `backend/main.py`. The API Gateway at `/api` is the primary entry point for the frontend.

```
backend/main.py
├── /api         → Gateway (auth, cases, chat, admin)
├── /chat        → Legal chatbot
├── /classifier  → Crime classification
├── /ocr         → OCR engine
├── /rag         → Legal retrieval
├── /verification→ Multi-agent verification
└── /pdf         → PDF generation
```

---

## Useful Commands

| Task                        | Command                                                      |
|-----------------------------|--------------------------------------------------------------|
| Check status                | `git status`                                                 |
| Build Docker                | `docker-compose up --build -d`                               |
| View logs                   | `docker-compose logs -f [service]`                           |
| Stop all                    | `docker-compose down`                                        |
| Run backend dev             | `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`       |
| Run Celery worker           | `celery -A services.common.celery_app worker --loglevel=info`|
| Install backend deps        | `pip install -r backend/requirements.txt`                    |
| Install frontend deps       | `npm install`                                                |
| Run frontend dev            | `npm run dev`                                                |
| Build frontend              | `npm run build`                                              |
