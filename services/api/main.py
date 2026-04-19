"""API Gateway - Main Orchestrator (Port 8000)"""
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional
import httpx
import uuid
import os
from datetime import datetime

app = FastAPI(
    title="Cybercrime AI - API Gateway",
    description="Main orchestrator for the 6-stage AI pipeline",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service URLs (from environment or defaults)
SERVICE_URLS = {
    "ocr": os.getenv("OCR_SERVICE_URL", "http://ocr:8001"),
    "classifier": os.getenv("CLASSIFIER_SERVICE_URL", "http://classifier:8002"),
    "rag": os.getenv("RAG_SERVICE_URL", "http://rag:8003"),
    "verification": os.getenv("VERIFICATION_SERVICE_URL", "http://verification:8004"),
    "pdf": os.getenv("PDF_SERVICE_URL", "http://pdf_gen:8005"),
}

# In-memory case storage (replace with Redis/DB in production)
cases_db = {}

class CaseStatus(BaseModel):
    case_id: str
    status: str  # processing, completed, failed
    created_at: str
    result: Optional[dict] = None

@app.get("/")
def root():
    return {
        "service": "Cybercrime AI - API Gateway",
        "version": "1.0.0",
        "pipeline_stages": ["upload", "ocr", "classify", "rag", "verify", "pdf"]
    }

@app.get("/health")
async def health():
    """Check all service health"""
    health_status = {"gateway": "healthy", "services": {}}
    
    async with httpx.AsyncClient() as client:
        for name, url in SERVICE_URLS.items():
            try:
                resp = await client.get(f"{url}/health", timeout=5.0)
                health_status["services"][name] = "healthy" if resp.status_code == 200 else "unhealthy"
            except:
                health_status["services"][name] = "unreachable"
    
    return health_status

@app.post("/analyze")
async def analyze(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...)
):
    """Start analysis pipeline (async)"""
    case_id = f"CASE_{uuid.uuid4().hex[:8].upper()}"
    
    cases_db[case_id] = {
        "case_id": case_id,
        "status": "processing",
        "created_at": datetime.now().isoformat(),
        "files_count": len(files),
        "result": None
    }
    
    # Process in background
    background_tasks.add_task(process_pipeline, case_id, files)
    
    return {
        "case_id": case_id,
        "status": "processing",
        "message": "Analysis started. Check /cases/{case_id} for results."
    }

@app.post("/analyze/json")
async def analyze_json(files: List[UploadFile] = File(...)):
    """Run full pipeline and return JSON result (sync)"""
    case_id = f"CASE_{uuid.uuid4().hex[:8].upper()}"
    
    try:
        result = await run_pipeline(case_id, files)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cases/{case_id}")
def get_case(case_id: str):
    """Get case status and results"""
    if case_id not in cases_db:
        raise HTTPException(status_code=404, detail="Case not found")
    return cases_db[case_id]

@app.get("/cases")
def list_cases():
    """List all cases"""
    return list(cases_db.values())

@app.get("/pdf/{case_id}")
async def download_pdf(case_id: str):
    """Download generated PDF for case"""
    if case_id not in cases_db:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case = cases_db[case_id]
    if case["status"] != "completed":
        raise HTTPException(status_code=400, detail="PDF not ready yet")
    
    # Generate PDF on-demand or return cached
    pdf_path = f"/outputs/{case_id}.pdf"
    if os.path.exists(pdf_path):
        return FileResponse(pdf_path, media_type="application/pdf")
    
    raise HTTPException(status_code=404, detail="PDF not found")

async def process_pipeline(case_id: str, files: List[UploadFile]):
    """Background pipeline processing"""
    try:
        result = await run_pipeline(case_id, files)
        cases_db[case_id]["status"] = "completed"
        cases_db[case_id]["result"] = result
    except Exception as e:
        cases_db[case_id]["status"] = "failed"
        cases_db[case_id]["error"] = str(e)

async def run_pipeline(case_id: str, files: List[UploadFile]) -> dict:
    """Execute full 6-stage pipeline"""
    
    async with httpx.AsyncClient() as client:
        # Stage 1: OCR & Entity Extraction
        ocr_results = []
        for file in files:
            file_bytes = await file.read()
            resp = await client.post(
                f"{SERVICE_URLS['ocr']}/extract",
                files={"file": (file.filename, file_bytes, file.content_type)},
                timeout=60.0
            )
            ocr_results.append(resp.json())
        
        # Combine OCR results
        combined_text = " ".join([r["text"] for r in ocr_results])
        all_entities = merge_entities([r["entities"] for r in ocr_results])
        avg_confidence = sum([r["confidence"] for r in ocr_results]) / len(ocr_results)
        
        # Stage 2: Classification
        classify_resp = await client.post(
            f"{SERVICE_URLS['classifier']}/classify",
            json={"text": combined_text, "entities": all_entities},
            timeout=30.0
        )
        classification = classify_resp.json()
        
        # Stage 3: RAG - Legal Retrieval
        rag_resp = await client.post(
            f"{SERVICE_URLS['rag']}/retrieve",
            json={
                "query": combined_text[:500],
                "crime_type": classification["crime_type"],
                "top_k": 5
            },
            timeout=30.0
        )
        articles = rag_resp.json().get("articles", [])
        
        # Stage 4: Verification
        verify_resp = await client.post(
            f"{SERVICE_URLS['verification']}/verify",
            json={
                "evidence_text": combined_text,
                "extracted_entities": all_entities,
                "classification": classification,
                "retrieved_articles": articles
            },
            timeout=60.0
        )
        verification = verify_resp.json()
        
        # Stage 5: Build result
        result = {
            "case_id": case_id,
            "classification": classification,
            "entities": all_entities,
            "articles": articles,
            "verification": {
                "status": verification["status"],
                "rounds": verification["rounds"]
            },
            "score": {
                "total_score": verification["final_score"],
                "grade": verification["score_breakdown"].get("grade", "WEAK"),
                "breakdown": verification["score_breakdown"]
            },
            "timeline": verification["timeline"],
            "ocr_confidence": round(avg_confidence, 2),
            "files_processed": len(files)
        }
        
        return result

def merge_entities(entities_list: list) -> dict:
    """Merge entities from multiple files"""
    merged = {"phones": [], "amounts": [], "dates": [], "accounts": [], "emails": []}
    
    for entities in entities_list:
        for key in merged:
            if key in entities:
                # Avoid duplicates
                existing = {e["value"] for e in merged[key]}
                for e in entities[key]:
                    if e["value"] not in existing:
                        merged[key].append(e)
    
    return merged

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
