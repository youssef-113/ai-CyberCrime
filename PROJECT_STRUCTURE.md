# Cybercrime AI - Project Structure

## Microservices Architecture

```
ai-Cybercrime/
│
├── 📁 services/                      # 6 Microservices Pipeline
│   │
│   ├── 📁 api/                       # API Gateway (Port 8000)
│   │   ├── main.py                   # Main orchestrator + /analyze endpoint
│   │   ├── pipeline.py               # Calls all services in sequence
│   │   ├── models.py                 # Pydantic schemas
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── 📁 ocr/                       # STAGE 2: OCR (Port 8001)
│   │   ├── main.py                   # FastAPI + EasyOCR endpoint
│   │   ├── requirements.txt          # easyocr, Pillow, numpy
│   │   └── Dockerfile                # System deps for OCR
│   │
│   ├── 📁 classifier/                # STAGE 3a: Classification (Port 8002)
│   │   ├── main.py                   # LLM crime classification
│   │   ├── prompts.py                # Prompt templates
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── 📁 rag/                       # STAGE 3b: Legal RAG (Port 8003)
│   │   ├── main.py                   # ChromaDB + retrieval
│   │   ├── build_knowledge_base.py   # Index law articles
│   │   ├── parse_law.py              # Parse PDF to JSON
│   │   ├── requirements.txt          # chromadb, sentence-transformers
│   │   └── Dockerfile
│   │
│   ├── 📁 verification/              # STAGE 4: Multi-Agent (Port 8004)
│   │   ├── main.py                   # Attacker + Judge agents
│   │   ├── agents.py                 # LangGraph verification flow
│   │   ├── scoring.py                # Evidence score 0-100
│   │   ├── timeline.py               # Chronological builder
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   └── 📁 pdf_gen/                   # STAGE 5: PDF (Port 8005)
│       ├── main.py                   # Complaint PDF endpoint
│       ├── generate.py               # WeasyPrint generator
│       ├── templates/
│       │   ├── complaint_ar.html     # Arabic RTL template
│       │   └── complaint_en.html     # English template
│       ├── requirements.txt          # weasyprint, jinja2
│       └── Dockerfile                # System fonts
│
├── 📁 frontend/                      # React + Vite Frontend
│   ├── src/
│   │   ├── App.jsx                   # Router + providers
│   │   ├── main.jsx                  # Entry with Toaster
│   │   ├── index.css                 # Perspective Design tokens
│   │   ├── api/
│   │   │   ├── client.js             # Axios HTTP client
│   │   │   ├── endpoints.js          # API calls
│   │   │   └── hooks.js              # React Query hooks
│   │   ├── components/
│   │   │   ├── ui/                   # Button, Card, Input, etc.
│   │   │   ├── layout/               # Header, Sidebar, MainLayout
│   │   │   └── Scene3D.jsx           # Three.js background
│   │   ├── context/
│   │   │   ├── CaseContext.jsx       # Case state management
│   │   │   └── ThemeContext.jsx      # RTL + language
│   │   ├── pages/
│   │   │   ├── LandingPage.jsx       # Hero + features
│   │   │   ├── DashboardPage.jsx     # Stats + case list
│   │   │   ├── CaseAnalysisPage.jsx  # Upload + pipeline UI
│   │   │   ├── ChatbotPage.jsx       # Legal chat
│   │   │   └── SettingsPage.jsx      # Config + about
│   │   └── utils/
│   │       ├── constants.js          # Crime types, scores
│   │       ├── formatters.js         # Date, currency, etc.
│   │       └── validators.js         # File validation
│   ├── package.json                  # React + dependencies
│   ├── vite.config.js
│   ├── tailwind.config.js            # Design tokens
│   └── Dockerfile
│
├── 📁 data/                          # Shared data volumes
│   ├── law/
│   │   ├── raw/                      # Downloaded PDFs
│   │   └── parsed/
│   │       └── articles.json         # Structured articles
│   ├── law_db/                       # ChromaDB vector store
│   └── test_cases/                   # Synthetic test data
│
├── 📁 tests/                         # All tests
│   ├── test_ocr.py
│   ├── test_classifier.py
│   ├── test_rag.py
│   ├── test_verification.py
│   ├── test_pdf.py
│   └── test_pipeline_e2e.py
│
├── 📁 outputs/                       # Generated PDFs (gitignored)
│
├── 📁 images/                        # Logo + banners
│   ├── Gemini_Generated_Image_*.png
│   └── *.jpeg
│
├── docker-compose.yml                # All 8 services
├── .env.example                      # Environment template
└── PROJECT_STRUCTURE.md              # This file
```

## Pipeline Flow

```
User Upload → API Gateway → OCR (8001) → Classifier (8002)
                                           ↓
PDF (8005) ← Verification (8004) ← RAG (8003)
```

## Quick Start

```bash
# 1. Clone
git clone https://github.com/yourusername/ai-cybercrime.git
cd ai-cybercrime

# 2. Environment
cp .env.example .env
# Edit .env with your LLM_API_KEY

# 3. Start all services
docker-compose up --build

# 4. Access
# Frontend: http://localhost:3000
# API: http://localhost:8000
# Qdrant: http://localhost:6333
```

## Service Ports

| Service | Port | Purpose |
|---------|------|---------|
| API Gateway | 8000 | Main orchestrator |
| OCR | 8001 | Text extraction |
| Classifier | 8002 | Crime classification |
| RAG | 8003 | Law article retrieval |
| Verification | 8004 | Multi-agent verification |
| PDF Gen | 8005 | Complaint PDF |
| Frontend | 3000 | React UI |
| Qdrant | 6333 | Vector DB |

## API Endpoints

### Main Gateway (8000)
- `GET /health` - Check all services
- `POST /analyze` - Async analysis (returns case_id)
- `POST /analyze/json` - Sync analysis (returns full result)
- `GET /cases/{id}` - Get case status
- `GET /pdf/{id}` - Download PDF

### Individual Services
Each service has:
- `GET /health` - Service health check
- Service-specific endpoints (see service main.py)
