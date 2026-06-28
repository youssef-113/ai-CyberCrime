"""Verification Service - Stage 4: Attacker + Judge Agents (LangGraph)"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .graph import run_verification_graph
from .supabase_store import SupabaseVerificationStore
from .database import VerificationStore as SQLiteStore

router = APIRouter(prefix="/verification")

# ── Audit store (module-level singleton) ─────────────────────────────────
# Uses Supabase when env vars are set, falls back to local SQLite
import os as _os

if _os.getenv("SUPABASE_URL") and (_os.getenv("SUPABASE_SERVICE_KEY") or _os.getenv("SUPABASE_KEY")):
    store = SupabaseVerificationStore()
else:
    store = SQLiteStore()


# ── Request / Response models ────────────────────────────────────────────


class VerificationRequest(BaseModel):
    evidence_text: str
    extracted_entities: dict
    classification: dict
    retrieved_articles: List[dict]
    evidence_blocks: Optional[List[dict]] = []
    case_id: Optional[str] = None
    # Foreign keys to existing auth system
    user_id: Optional[str] = None  # users.id
    source_case_id: Optional[str] = None  # cases.case_id (parent case)
    session_id: Optional[str] = None  # chat_sessions.session_id


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
    user_id: Optional[str] = None
    source_case_id: Optional[str] = None
    session_id: Optional[str] = None
    crime_type: str
    created_at: str
    final_status: Optional[str] = None
    final_score: Optional[int] = None
    total_rounds: Optional[int] = None
    grade: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────────


@router.get("/health")
def health():
    """
    Liveness + readiness probe.
    Checks: Supabase / SQLite store, Groq LLM availability.
    """
    import os as _os

    db_ok   = False
    llm_ok  = False

    # Database check
    try:
        cases  = store.list_cases(limit=1)
        db_ok  = True
    except Exception:
        db_ok  = False

    # LLM (Groq) check
    groq_key = _os.getenv("GROQ_API_KEY", "")
    if groq_key:
        try:
            import httpx as _httpx
            r = _httpx.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {groq_key}"},
                timeout=3.0,
            )
            llm_ok = r.status_code == 200
        except Exception:
            llm_ok = False
    else:
        ollama_url = _os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        try:
            import httpx as _httpx
            r      = _httpx.get(f"{ollama_url}/api/tags", timeout=3.0)
            llm_ok = r.status_code == 200
        except Exception:
            llm_ok = False

    store_type = "supabase" if "Supabase" in type(store).__name__ else "sqlite"
    overall    = "healthy" if db_ok else "degraded"

    return {
        "status":     overall,
        "service":    "verification",
        "version":    "2.0.0",
        "store":      store_type,
        "database":   "ok" if db_ok  else "unavailable",
        "llm":        "ok" if llm_ok else "unavailable",
    }


@router.post("/verify", response_model=VerificationResponse)
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
        user_id=request.user_id,
        source_case_id=request.source_case_id,
        session_id=request.session_id,
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


@router.get("/cases", response_model=List[CaseSummary])
def list_cases(limit: int = 50, offset: int = 0, user_id: Optional[str] = None):
    """List all verification cases (newest first).

    Args:
        user_id: Filter by specific user (for admin/audit use)
    """
    return store.list_cases(limit=limit, offset=offset, user_id=user_id)


@router.get("/cases/{case_id}", response_model=CaseSummary)
def get_case(case_id: str):
    """Get case-level summary."""
    summary = store.get_case_summary(case_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Case not found")
    return summary


@router.get("/cases/{case_id}/rounds")
def get_case_rounds(case_id: str):
    """Get full round-by-round audit trail for a case."""
    history = store.get_case_history(case_id)
    if not history:
        raise HTTPException(status_code=404, detail="Case not found")
    return history


