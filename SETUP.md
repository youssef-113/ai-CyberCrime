# 🚀 Zero-to-Run Complete Guide

Complete setup guide for AI Cybercrime Evidence Builder - from fresh machine to running system.

---

## Prerequisites Check

Before starting, ensure you have:
- [ ] Git installed
- [ ] Docker & Docker Compose installed (for containerized setup)
- [ ] **OR** Conda installed (for local Python setup)
- [ ] 8GB+ RAM
- [ ] Ports 3000, 8000-8005, 6333 available

---

## Step 0: Install Conda (If Not Already Installed)

### Option A: Install Miniconda (Recommended - Lightweight)

**Linux/macOS:**
```bash
# Download Miniconda installer
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh

# Run installer
bash Miniconda3-latest-Linux-x86_64.sh

# Follow prompts:
# - Press ENTER to view license
# - Type 'yes' to accept
# - Press ENTER to confirm install location
# - Type 'yes' to initialize Miniconda3

# Restart terminal or run:
source ~/.bashrc

# Verify installation
conda --version
```

**Windows:**
1. Download: https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe
2. Run installer as Administrator
3. Check "Add Miniconda3 to my PATH" during installation
4. Open new Command Prompt and verify: `conda --version`

### Option B: Install Anaconda (Full Distribution)

**Linux:**
```bash
wget https://repo.anaconda.com/archive/Anaconda3-2024.02-1-Linux-x86_64.sh
bash Anaconda3-2024.02-1-Linux-x86_64.sh
source ~/.bashrc
conda --version
```

**macOS:**
```bash
# Intel Mac
wget https://repo.anaconda.com/archive/Anaconda3-2024.02-1-MacOSX-x86_64.sh

# M1/M2 Mac (Apple Silicon)
wget https://repo.anaconda.com/archive/Anaconda3-2024.02-1-MacOSX-arm64.sh

bash Anaconda3-2024.02-1-MacOSX-*.sh
source ~/.zshrc  # or ~/.bash_profile
conda --version
```

**Windows:**
Download from: https://www.anaconda.com/download

---

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

# Install law indexing dependencies (optional, for RAG)
pip install langchain langchain-community sentence-transformers
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
# OR
vim .env
```

**Required in `.env`:**
```env
# Get your API key from: https://console.anthropic.com/
LLM_API_KEY=sk-ant-your-actual-key-here
LLM_MODEL=claude-3-haiku-20240307

# Optional: OpenAI alternative
# OPENAI_API_KEY=sk-your-openai-key
```

---

## 6. Docker Setup (Recommended - Runs Everything)

### Install Docker (If Not Installed)

**Ubuntu/Debian:**
```bash
# Update package index
sudo apt-get update

# Install prerequisites
sudo apt-get install -y ca-certificates curl gnupg

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add repository
echo "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify
docker --version
docker compose version
```

**macOS:**
```bash
# Using Homebrew
brew install --cask docker

# Or download from: https://docs.docker.com/desktop/install/mac-install/
```

**Windows:**
Download Docker Desktop: https://docs.docker.com/desktop/install/windows-install/

### Run All Services with Docker

```bash
# Build and start ALL services (first time takes 10-15 min)
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

Use this for development - faster iteration without rebuilding containers.

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

### Install Node.js (If Not Installed)

**Via Conda (Recommended):**
```bash
conda install -c conda-forge nodejs=18
node --version  # Should show v18.x.x
```

**Or download from:** https://nodejs.org/

### Setup Frontend

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

## 9. Quick Start Script

Save as `start-all.sh` in project root:

```bash
#!/bin/bash

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Starting all services...${NC}"

# Activate conda
source ~/miniconda3/etc/profile.d/conda.sh  # Adjust path if needed
conda activate cybercrime

# Function to start service
start_service() {
    local name=$1
    local dir=$2
    local port=$3
    
    echo -e "${GREEN}Starting $name on port $port...${NC}"
    cd "$dir" && uvicorn main:app --host 0.0.0.0 --port "$port" --reload &
}

# Start all services
start_service "API Gateway" "services/api" "8000"
start_service "OCR" "services/ocr" "8001"
start_service "Classifier" "services/classifier" "8002"
start_service "RAG" "services/rag" "8003"
start_service "Verification" "services/verification" "8004"
start_service "PDF Gen" "services/pdf_gen" "8005"

sleep 3

echo ""
echo -e "${GREEN}All services started!${NC}"
echo ""
echo "Service URLs:"
echo "  API Gateway:   http://localhost:8000"
echo "  OCR:           http://localhost:8001"
echo "  Classifier:    http://localhost:8002"
echo "  RAG:           http://localhost:8003"
echo "  Verification:  http://localhost:8004"
echo "  PDF Gen:       http://localhost:8005"
echo ""
echo "To stop all services: pkill -f uvicorn"
```

Make executable and run:
```bash
chmod +x start-all.sh
./start-all.sh
```

---

## 10. Index Law Articles (For RAG)

```bash
# Activate environment
conda activate cybercrime

# Index Egyptian law articles into ChromaDB
python scripts/index_law.py

# Verify citations
python scripts/validate_citations.py --query "ابتزاز"
```

---

## 11. Test Everything Works

### Health Checks
```bash
# Run verification script
chmod +x scripts/verify-all.sh
./scripts/verify-all.sh

# Or test manually
curl http://localhost:8000/health  # API Gateway
curl http://localhost:8001/health  # OCR
curl http://localhost:8002/health  # Classifier
curl http://localhost:8003/health  # RAG
curl http://localhost:8004/health  # Verification
curl http://localhost:8005/health  # PDF Gen
curl http://localhost:6333/healthz # Qdrant
```

### Run E2E Tests
```bash
pip install pytest pytest-asyncio httpx
python scripts/test-end-to-end.py
```

---

## 🎯 Quick Start (Complete Flow)

```bash
# 1. Clone & enter repo
git clone https://github.com/youssef-113/ai-CyberCrime.git
cd ai-CyberCrime

# 2. Install conda (if needed) - see Step 0 above

# 3. Create environment
conda create -n cybercrime python=3.11 -y
conda activate cybercrime

# 4. Setup environment variables
cp .env.example .env
# Edit .env with your LLM_API_KEY

# 5. OPTION A: Docker (Easiest - runs everything)
docker-compose up --build

# 5. OPTION B: Local development (faster iteration)
# Install all dependencies
for req in services/*/requirements.txt; do pip install -r "$req"; done

# Start services
./start-all.sh

# 6. Start frontend (in new terminal)
cd frontend && npm install && npm run dev

# 7. Open browser
# Frontend: http://localhost:3000
# API:      http://localhost:8000/docs
```

---

## Troubleshooting

### Port Already in Use
```bash
# Find process using port 8000
sudo lsof -i :8000

# Kill it
kill -9 <PID>
```

### Docker Permission Denied (Linux)
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, then:
docker-compose up --build
```

### Conda Environment Not Found
```bash
# List all environments
conda env list

# If 'cybercrime' not found, recreate:
conda create -n cybercrime python=3.11 -y
```

### LLM API Key Not Working
```bash
# Test your key
curl -X POST https://api.anthropic.com/v1/messages \
  -H "x-api-key: $LLM_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-3-haiku-20240307","max_tokens":100,"messages":[{"role":"user","content":"Hi"}]}'
```

---

## Access URLs After Setup

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:3000 | React UI |
| API Docs | http://localhost:8000/docs | Swagger UI |
| API Gateway | http://localhost:8000 | Main orchestrator |
| OCR | http://localhost:8001 | Text extraction |
| Classifier | http://localhost:8002 | Crime classification |
| RAG | http://localhost:8003 | Law retrieval |
| Verification | http://localhost:8004 | Multi-agent check |
| PDF Gen | http://localhost:8005 | Report generation |
| Qdrant | http://localhost:6333 | Vector database |

---

## Useful Commands Reference

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
| Recreate env | `conda env create -f environment.yml` |
| **Docker** | |
| Build | `docker-compose up --build` |
| Start | `docker-compose up -d` |
| Stop | `docker-compose down` |
| View logs | `docker-compose logs -f [service]` |
| Rebuild one | `docker-compose up --build [service]` |
| **Python** | |
| Run service | `uvicorn main:app --host 0.0.0.0 --port 8000 --reload` |
| Install deps | `pip install -r requirements.txt` |
| Freeze | `pip freeze > requirements.txt` |
| **Frontend** | |
| Install | `npm install` |
| Dev | `npm run dev` |
| Build | `npm run build` |

---

## Need Help?

1. Check service logs: `docker-compose logs -f [service-name]`
2. Run health check: `./scripts/verify-all.sh`
3. Test individual service: `curl http://localhost:PORT/health`
4. Review error messages in terminal output
