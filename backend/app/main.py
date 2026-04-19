from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List

app = FastAPI(title="AI Cybercrime Evidence Builder", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Cybercrime AI Backend Running", "version": "1.0.0"}

@app.get("/health")
def health():
    return {"status": "healthy", "service": "api-gateway"}

@app.post("/analyze")
async def analyze(files: List[UploadFile] = File(...)):
    return {"status": "processing", "files_received": len(files)}

@app.post("/analyze/json")
async def analyze_json(files: List[UploadFile] = File(...)):
    return {
        "case_id": "CASE_001",
        "classification": {"crime_type": "blackmail", "confidence": 0.92},
        "entities": {"phones": [], "amounts": [], "dates": [], "accounts": []},
        "score": {"total_score": 85, "grade": "STRONG"},
        "verification": {"status": "APPROVED", "rounds": 2},
        "articles": []
    }
