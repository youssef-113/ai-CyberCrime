#!/usr/bin/env bash
# ============================================================
# AI Cybercrime - Local Development Startup Script
# ============================================================
# Usage:  ./scripts/start-dev.sh
#
# Prerequisites:
#   - conda env "cybercrime" activated
#   - Supabase running (or SUPABASE_URL/KEY set in .env)
#   - ChromaDB running:  docker run -p 8003:8000 chromadb/chroma
#   - Ollama running:   ollama serve  (with qwen2.5:3b pulled)
# ============================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# Load .env if present
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
fi

# Default service URLs for local development (not Docker)
export OCR_SERVICE_URL=${OCR_SERVICE_URL:-"http://localhost:8001"}
export CLASSIFIER_SERVICE_URL=${CLASSIFIER_SERVICE_URL:-"http://localhost:8002"}
export RAG_SERVICE_URL=${RAG_SERVICE_URL:-"http://localhost:8003"}
export VERIFICATION_SERVICE_URL=${VERIFICATION_SERVICE_URL:-"http://localhost:8004"}
export PDF_SERVICE_URL=${PDF_SERVICE_URL:-"http://localhost:8005"}
export CHATBOT_SERVICE_URL=${CHATBOT_SERVICE_URL:-"http://localhost:8006"}
export CORS_ORIGINS=${CORS_ORIGINS:-"http://localhost:3000,http://127.0.0.1:3000"}

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       AI Cybercrime Evidence Builder - Dev Startup          ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Services will start on:"
echo "  API Gateway    → http://localhost:8000"
echo "  OCR            → http://localhost:8001"
echo "  Classifier     → http://localhost:8002"
echo "  RAG            → http://localhost:8003"
echo "  Verification   → http://localhost:8004"
echo "  PDF Generator  → http://localhost:8005"
echo "  Chatbot        → http://localhost:8006"
echo ""

# Start each service in background
echo "Starting services..."
uvicorn services.api.main:app --port 8000 --reload &
uvicorn services.ocr.main:app --port 8001 --reload &
uvicorn services.classifier.main:app --port 8002 --reload &
uvicorn services.rag.main:app --port 8003 --reload &
uvicorn services.verification.main:app --port 8004 --reload &
uvicorn services.pdf_gen.main:app --port 8005 --reload &
uvicorn services.chatbot.main:app --port 8006 --reload &

echo ""
echo "All services started. Press Ctrl+C to stop all."
echo ""

# Wait for all background processes
wait
