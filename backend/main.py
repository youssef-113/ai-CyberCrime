"""
ACEB Backend - Monolithic FastAPI Application
AI Cybercrime Evidence Builder - Production MVP Architecture
"""
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aceb.backend")

# Import all service modules
from services.api.main import app as api_app
from services.chat.main import app as chat_app
from services.classifier.main import app as classifier_app
from services.ocr.main import app as ocr_app
from services.rag.main import app as rag_app
from services.verification.main import app as verification_app
from services.pdf.main import app as pdf_app

# Initialize FastAPI app
app = FastAPI(
    title="ACEB Backend",
    description="AI Cybercrime Evidence Builder - Monolithic Backend",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all service routers
app.mount("/api", api_app)
app.mount("/chat", chat_app)
app.mount("/classifier", classifier_app)
app.mount("/ocr", ocr_app)
app.mount("/rag", rag_app)
app.mount("/verification", verification_app)
app.mount("/pdf", pdf_app)

# Health check
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "aceb-backend",
        "version": "2.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
