# Definition of Done - Setup Checklist

## Pre-Setup Requirements

- [ ] Git installed (version 2.30+)
- [ ] Docker installed (version 20.10+)
- [ ] Docker Compose installed (version 2.0+)
- [ ] 8GB+ RAM available
- [ ] Ports 3000, 8000-8005, 6333 are free

## Team Setup (All 4 Members)

### 1. Clone Repository
```bash
git clone https://github.com/youssef-113/ai-CyberCrime.git
cd ai-CyberCrime
```

### 2. Environment Setup
```bash
# Copy environment template
cp .env.example .env

# Edit with your API key
nano .env
# Add: LLM_API_KEY=sk-ant-your-actual-key
```

### 3. Docker Build & Start
```bash
# Build all services (first time takes 5-10 minutes)
docker-compose up --build

# Or run in background
docker-compose up --build -d
```

### 4. Verify All Services
```bash
# Run verification script
chmod +x scripts/verify-all.sh
./scripts/verify-all.sh

# Or run Python E2E tests
python scripts/test-end-to-end.py
```

## Definition of Done Verification

### [ ] GitHub Repo Live with Correct Branch Structure
```bash
# Verify branches exist
git branch -a

# Should show:
# * main
#   develop
#   Frontend
#   remotes/origin/main
#   remotes/origin/develop
#   remotes/origin/Frontend
```

### [ ] Docker Compose Starts All 8 Services
```bash
# Check all containers are running
docker-compose ps

# Should show 8 services:
# - ai-cybercrime_api-gateway_1
# - ai-cybercrime_ocr_1
# - ai-cybercrime_classifier_1
# - ai-cybercrime_rag_1
# - ai-cybercrime_verification_1
# - ai-cybercrime_pdf-gen_1
# - ai-cybercrime_frontend_1
# - ai-cybercrime_qdrant_1
```

### [ ] All 8 Services Return {"status":"ok"} on /health
```bash
# Quick manual check
curl http://localhost:8000/health  # API Gateway
curl http://localhost:8001/health  # OCR
curl http://localhost:8002/health  # Classifier
curl http://localhost:8003/health  # RAG
curl http://localhost:8004/health  # Verification
curl http://localhost:8005/health  # PDF Gen
curl http://localhost:6333/healthz # Qdrant
```

**Expected Response:**
```json
{"status": "healthy", "service": "service-name"}
```

### [ ] Unified JSON Schema Documented
- [ ] Read `docs/SCHEMA.md`
- [ ] All team members understand the 6 service schemas
- [ ] Agreed on error response format
- [ ] Agreed on grade classification (STRONG/MEDIUM/WEAK)

### [ ] .env.example Contains All Required Variables
- [ ] LLM_API_KEY
- [ ] LLM_MODEL
- [ ] All 5 service URLs
- [ ] VITE_API_URL
- [ ] QDRANT_URL
- [ ] DEBUG and LOG_LEVEL

### [ ] GitHub Actions CI Runs Automatically
- [ ] Push to `develop` branch triggers CI
- [ ] CI runs tests on all services
- [ ] CI builds Docker images
- [ ] CI verifies health endpoints

## Service Ports Reference

| Service | Port | Health Endpoint |
|---------|------|-----------------|
| API Gateway | 8000 | GET /health |
| OCR | 8001 | GET /health |
| Classifier | 8002 | GET /health |
| RAG | 8003 | GET /health |
| Verification | 8004 | GET /health |
| PDF Gen | 8005 | GET /health |
| Frontend | 3000 | GET / (returns HTML) |
| Qdrant | 6333 | GET /healthz |

## Troubleshooting

### Service won't start
```bash
# Check logs
docker-compose logs -f [service-name]

# Rebuild specific service
docker-compose up --build [service-name]
```

### Port already in use
```bash
# Find what's using port 8000
sudo lsof -i :8000

# Kill process or change port in docker-compose.yml
```

### Health check fails
```bash
# Test manually
curl -v http://localhost:8000/health

# Check if service is actually running
docker-compose ps
```

## Sign-Off

Each team member must verify and sign off:

| Member | Machine | Date | Signature |
|--------|---------|------|-----------|
| Member 1 | | | |
| Member 2 | | | |
| Member 3 | | | |
| Member 4 | | | |

**When all boxes are checked for all 4 members, the Definition of Done is achieved!**
