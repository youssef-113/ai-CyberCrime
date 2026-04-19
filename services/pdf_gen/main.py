"""PDF Generation Service - Stage 5: Complaint Generator"""
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from generate import generate_complaint_pdf

app = FastAPI(title="PDF Generation Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class PDFRequest(BaseModel):
    case_id: str
    crime_type: str
    evidence_summary: str
    timeline: List[dict]
    law_articles: List[dict]
    score: int
    grade: str
    complainant_name: Optional[str] = "Complainant"
    language: str = "ar"  # ar or en

@app.get("/health")
def health():
    return {"status": "healthy", "service": "pdf_gen"}

@app.post("/generate")
async def generate_pdf(request: PDFRequest):
    """Generate complaint PDF"""
    
    pdf_bytes = generate_complaint_pdf(
        case_id=request.case_id,
        crime_type=request.crime_type,
        evidence_summary=request.evidence_summary,
        timeline=request.timeline,
        law_articles=request.law_articles,
        score=request.score,
        grade=request.grade,
        complainant_name=request.complainant_name,
        language=request.language
    )
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=complaint_{request.case_id}.pdf"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
