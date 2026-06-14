"""PDF Generator Service - WeasyPrint + Jinja2"""
import os
import base64
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from .generate import generate_complaint_pdf

app = FastAPI(title="PDF Generator Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUTS_DIR = os.getenv("OUTPUTS_DIR", "/outputs")


class PDFRequest(BaseModel):
    case_id: str
    crime_type: str
    evidence_summary: str
    timeline: List[dict] = []
    law_articles: List[dict] = []
    score: int = 0
    grade: str = "C"
    complainant_name: str = ""
    language: str = "ar"


@app.get("/health")
def health():
    """
    Liveness + readiness probe.
    Checks: output directory writability, WeasyPrint availability.
    """
    import os as _os

    outputs_ok    = False
    weasyprint_ok = False

    try:
        _os.makedirs(OUTPUTS_DIR, exist_ok=True)
        test_path = _os.path.join(OUTPUTS_DIR, ".health_check")
        with open(test_path, "w") as f:
            f.write("ok")
        _os.unlink(test_path)
        outputs_ok = True
    except Exception:
        outputs_ok = False

    try:
        from weasyprint import HTML  # noqa: F401
        weasyprint_ok = True
    except Exception:
        weasyprint_ok = False

    overall = "healthy" if (outputs_ok and weasyprint_ok) else "degraded"
    return {
        "status":     overall,
        "service":    "pdf-gen",
        "version":    "1.0.0",
        "outputs_dir": OUTPUTS_DIR,
        "outputs":    "writable"    if outputs_ok    else "error",
        "weasyprint": "ok"          if weasyprint_ok else "unavailable",
    }


@app.post("/generate")
async def generate_pdf(request: PDFRequest):
    try:
        pdf_bytes = generate_complaint_pdf(
            case_id=request.case_id,
            crime_type=request.crime_type,
            evidence_summary=request.evidence_summary,
            timeline=request.timeline,
            law_articles=request.law_articles,
            score=request.score,
            grade=request.grade,
            complainant_name=request.complainant_name,
            language=request.language,
        )

        filename = f"{request.case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(OUTPUTS_DIR, filename)
        os.makedirs(OUTPUTS_DIR, exist_ok=True)

        with open(filepath, "wb") as f:
            f.write(pdf_bytes)

        pdf_b64 = base64.b64encode(pdf_bytes).decode()

        return {
            "status": "generated",
            "filename": filename,
            "path": filepath,
            "size_bytes": len(pdf_bytes),
            "pdf_base64": pdf_b64,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-download")
async def generate_pdf_download(request: PDFRequest):
    try:
        pdf_bytes = generate_complaint_pdf(
            case_id=request.case_id,
            crime_type=request.crime_type,
            evidence_summary=request.evidence_summary,
            timeline=request.timeline,
            law_articles=request.law_articles,
            score=request.score,
            grade=request.grade,
            complainant_name=request.complainant_name,
            language=request.language,
        )

        filename = f"{request.case_id}_complaint.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))