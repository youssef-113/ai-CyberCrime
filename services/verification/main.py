"""Verification Service - Stage 4: Attacker + Judge Agents (LangGraph)"""
import uuid
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph import run_verification_graph
from database import VerificationStore

app = FastAPI(title="Verification Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Audit store (module-level singleton) ─────────────────────────────────
store = VerificationStore()


# ── Request / Response models ────────────────────────────────────────────


class VerificationRequest(BaseModel):
    evidence_text: str
    extracted_entities: dict
    classification: dict
    retrieved_articles: List[dict]
    evidence_blocks: Optional[List[dict]] = []
    case_id: Optional[str] = None


class VerificationRound(BaseModel):
    round: int
    attacker_challenge: str
    judge_decision: str
    status: str
    articles_cited: List[str] = []
    claims_to_drop: List[str] = []
    confidence: Optional[float] = None
    latency_ms: Optional[int] = None


class VerificationResponse(BaseModel):
    case_id: str
    status: str
    rounds: int
    round_details: List[VerificationRound]
    final_score: int
    score_breakdown: dict
    grade: str
    timeline: dict


class CaseSummary(BaseModel):
    case_id: str
    crime_type: str
    created_at: str
    final_status: Optional[str] = None
    final_score: Optional[int] = None
    total_rounds: Optional[int] = None
    grade: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "healthy", "service": "verification", "version": "2.0.0"}


@app.post("/verify", response_model=VerificationResponse)
async def verify(request: VerificationRequest):
    """Run multi-agent verification via LangGraph with audit trail."""
    case_id = request.case_id or str(uuid.uuid4())

    result = await run_verification_graph(
        evidence_text=request.evidence_text,
        entities=request.extracted_entities,
        classification=request.classification,
        articles=request.retrieved_articles,
        evidence_blocks=request.evidence_blocks,
        case_id=case_id,
        store=store,
    )

    return VerificationResponse(
        case_id=case_id,
        status=result["final_status"],
        rounds=result["rounds"],
        round_details=result["details"],
        final_score=result["final_score"],
        score_breakdown=result["score_breakdown"],
        grade=result["grade"],
        timeline=result["timeline"],
    )


# ── Audit trail endpoints ────────────────────────────────────────────────


@app.get("/cases", response_model=List[CaseSummary])
def list_cases(limit: int = 50, offset: int = 0):
    """List all verification cases (newest first)."""
    return store.list_cases(limit=limit, offset=offset)


@app.get("/cases/{case_id}", response_model=CaseSummary)
def get_case(case_id: str):
    """Get case-level summary."""
    summary = store.get_case_summary(case_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Case not found")
    return summary


@app.get("/cases/{case_id}/rounds")
def get_case_rounds(case_id: str):
    """Get full round-by-round audit trail for a case."""
    history = store.get_case_history(case_id)
    if not history:
        raise HTTPException(status_code=404, detail="Case not found")
    return history


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
