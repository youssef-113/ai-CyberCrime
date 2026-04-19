"""Verification Service - Stage 4: Attacker + Judge Agents"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
from agents import run_verification_agents
from scoring import calculate_score
from timeline import build_timeline

app = FastAPI(title="Verification Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class VerificationRequest(BaseModel):
    evidence_text: str
    extracted_entities: dict
    classification: dict
    retrieved_articles: List[dict]

class VerificationRound(BaseModel):
    round: int
    attacker_challenge: str
    judge_decision: str
    status: str  # APPROVED, NEEDS_REVISION, NEEDS_USER_REVIEW

class VerificationResponse(BaseModel):
    status: str
    rounds: int
    round_details: List[VerificationRound]
    final_score: int
    score_breakdown: dict
    timeline: List[dict]

@app.get("/health")
def health():
    return {"status": "healthy", "service": "verification"}

@app.post("/verify", response_model=VerificationResponse)
async def verify(request: VerificationRequest):
    """Run multi-agent verification"""
    
    # Build timeline
    timeline = build_timeline(
        request.evidence_text,
        request.extracted_entities
    )
    
    # Run verification agents
    verification_result = await run_verification_agents(
        evidence=request.evidence_text,
        entities=request.extracted_entities,
        classification=request.classification,
        articles=request.retrieved_articles
    )
    
    # Calculate score
    score, breakdown = calculate_score(
        verification_result,
        request.extracted_entities,
        len(request.retrieved_articles)
    )
    
    return VerificationResponse(
        status=verification_result["final_status"],
        rounds=verification_result["rounds"],
        round_details=verification_result["details"],
        final_score=score,
        score_breakdown=breakdown,
        timeline=timeline
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
