"""LangGraph Revision Loop – replaces the basic for-loop in agents.py.

State machine:
    attacker → judge → (APPROVED or max_rounds)? → END
                                ↘ else → attacker  (loop)

Each node is async so it can call the LLM-backed agents directly.
Round-level persistence is handled inside the nodes via the shared
``VerificationStore``.
"""
import time
from typing import List, Optional, TypedDict

from langgraph.graph import StateGraph, END

from .agents import attacker_agent, judge_agent
from .database import VerificationStore
from .scoring import calculate_score
from .timeline import build_validated_timeline


# ── State definition ─────────────────────────────────────────────────────


class VerificationState(TypedDict, total=False):
    """State that flows through the graph."""

    # ── inputs ────────────────────────────────────────────────────────
    case_id: str
    user_id: Optional[str]
    source_case_id: Optional[str]
    session_id: Optional[str]
    evidence_text: str
    entities: dict
    claims: List[dict]
    evidence_blocks: List[dict]
    articles: List[dict]
    crime_type: str

    # ── loop control ──────────────────────────────────────────────────
    round_num: int
    max_rounds: int
    claim_text: str

    # ── per-round intermediates ──────────────────────────────────────
    current_challenges: str
    current_structured_challenges: List[str]
    current_judge_result: dict
    current_chat_message_id: Optional[str]

    # ── accumulated outputs ───────────────────────────────────────────
    verification_log: List[dict]
    final_status: str

    # ── scoring / timeline (filled at the end) ───────────────────────
    final_score: int
    score_breakdown: dict
    grade: str
    timeline: dict

    # ── internal (not serialized) ────────────────────────────────────
    store: Optional[VerificationStore]


# ── Node functions ───────────────────────────────────────────────────────


async def attacker_node(state: VerificationState) -> dict:
    """Run the attacker agent with crime-specific strategy + LLM."""
    result = await attacker_agent(
        claim=state.get("claim_text", ""),
        evidence=state.get("evidence_text", ""),
        round_num=state.get("round_num", 1),
        claims=state.get("claims", []),
        evidence_blocks=state.get("evidence_blocks", []),
        crime_type=state.get("crime_type", "generic"),
    )

    return {
        "current_challenges": result["combined_text"],
        "current_structured_challenges": result["structured_challenges"],
    }


async def judge_node(state: VerificationState) -> dict:
    """Run the judge agent, persist the round, and update claims."""
    t0 = time.monotonic()

    result = await judge_agent(
        claim=state.get("claim_text", ""),
        evidence=state.get("evidence_text", ""),
        challenge=state.get("current_challenges", ""),
        articles=state.get("articles", []),
        evidence_blocks=state.get("evidence_blocks", []),
        entities=state.get("entities", {}),
        round_num=state.get("round_num", 1),
    )

    latency_ms = int((time.monotonic() - t0) * 1000)

    # ── build log entry ───────────────────────────────────────────────
    log_entry = {
        "round": state.get("round_num", 1),
        "attacker_challenge": state.get("current_challenges", ""),
        "attacker_structured": state.get("current_structured_challenges", []),
        "judge_decision": result["decision"],
        "status": result["status"],
        "articles_cited": result.get("articles_cited", []),
        "claims_to_drop": result.get("claims_to_drop", []),
        "confidence": result.get("confidence"),
        "latency_ms": latency_ms,
    }

    # ── drop unsupported claims ───────────────────────────────────────
    dropped = result.get("claims_to_drop", [])
    current_claims = state.get("claims", [])
    if dropped:
        current_claims = [
            c for c in current_claims
            if c.get("claim", c.get("text", "")) not in dropped
            and str(c) not in dropped
        ]

    # ── persist to database ───────────────────────────────────────────
    store: Optional[VerificationStore] = state.get("store")
    if store and state.get("case_id"):
        store.save_round(
            case_id=state["case_id"],
            round_num=state.get("round_num", 1),
            attacker_data={
                "prompt": "",
                "response": "",
                "challenges": state.get("current_structured_challenges", []),
            },
            judge_data={
                "prompt": result.get("prompt", ""),
                "response": result.get("raw_response", ""),
                "articles_cited": result.get("articles_cited", []),
                "claims_to_drop": result.get("claims_to_drop", []),
                "confidence": result.get("confidence"),
            },
            status=result["status"],
            latency_ms=latency_ms,
            chat_message_id=state.get("current_chat_message_id"),
        )

    new_log = state.get("verification_log", []) + [log_entry]

    return {
        "claims": current_claims,
        "claim_text": result.get("revised_claim", state.get("claim_text", "")),
        "current_judge_result": result,
        "verification_log": new_log,
        "round_num": state.get("round_num", 1) + 1,
        "final_status": result["status"],
    }


# ── Conditional edge ────────────────────────────────────────────────────


def should_continue(state: VerificationState) -> str:
    """Decide whether to loop back to attacker or terminate."""
    if state.get("final_status") == "APPROVED":
        return END
    if state.get("round_num", 1) > state.get("max_rounds", 3):
        return END
    return "attacker"


# ── Graph construction ──────────────────────────────────────────────────


def build_verification_graph():
    """Return a compiled LangGraph ``StateGraph`` for verification."""
    builder = StateGraph(VerificationState)

    builder.add_node("attacker", attacker_node)
    builder.add_node("judge", judge_node)

    builder.add_edge("attacker", "judge")
    builder.add_conditional_edges("judge", should_continue)

    builder.set_entry_point("attacker")

    return builder.compile()


# Module-level compiled graph – import and use directly.
verification_graph = build_verification_graph()


# ── Convenience runner ──────────────────────────────────────────────────


async def run_verification_graph(
    evidence_text: str,
    entities: dict,
    classification: dict,
    articles: List[dict],
    evidence_blocks: Optional[List[dict]] = None,
    case_id: Optional[str] = None,
    store: Optional[VerificationStore] = None,
    max_rounds: int = 3,
    user_id: Optional[str] = None,
    source_case_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict:
    """High-level entry point that builds initial state, runs the graph,
    then computes score and timeline.

    Args:
        user_id: UUID of the requesting user (from JWT/auth)
        source_case_id: Main case_id from the cases table (parent case)
        session_id: chat_sessions.session_id that triggered this verification

    Returns the same shape as ``run_verification_agents`` so callers
    (including ``main.py``) can switch transparently.
    """
    if evidence_blocks is None:
        evidence_blocks = []

    crime_type = classification.get("crime_type", "generic")
    claims = classification.get("claims", [])

    claim_text = (
        f"The evidence shows {crime_type} "
        f"with confidence {classification.get('confidence', 0)}"
    )

    # Create case in the audit store (with auth context)
    if store and case_id:
        store.create_case(
            case_id=case_id,
            crime_type=crime_type,
            user_id=user_id,
            source_case_id=source_case_id,
            session_id=session_id,
        )

    initial_state: VerificationState = {
        "case_id": case_id or "",
        "user_id": user_id,
        "source_case_id": source_case_id,
        "session_id": session_id,
        "evidence_text": evidence_text,
        "entities": entities,
        "claims": claims,
        "evidence_blocks": evidence_blocks,
        "articles": articles,
        "crime_type": crime_type,
        "round_num": 1,
        "max_rounds": max_rounds,
        "claim_text": claim_text,
        "current_challenges": "",
        "current_structured_challenges": [],
        "current_judge_result": {},
        "current_chat_message_id": None,
        "verification_log": [],
        "final_status": "PENDING",
        "final_score": 0,
        "score_breakdown": {},
        "grade": "",
        "timeline": {},
        "store": store,
    }

    # LangGraph async invoke
    result = await verification_graph.ainvoke(initial_state)

    # ── post-processing: scoring + timeline ───────────────────────────
    score, breakdown = calculate_score(
        verification={
            "final_status": result.get("final_status", "NEEDS_USER_REVIEW"),
            "crime_type": crime_type,
        },
        entities=entities,
        article_count=len(articles),
        evidence_blocks=evidence_blocks,
    )

    timeline = build_validated_timeline(
        evidence_text, entities, evidence_blocks
    )

    grade = breakdown.get("grade", "WEAK")

    # Update case status in store
    if store and case_id:
        store.update_case_status(
            case_id=case_id,
            final_status=result.get("final_status", "NEEDS_USER_REVIEW"),
            final_score=score,
            total_rounds=len(result.get("verification_log", [])),
            grade=grade,
        )

    return {
        "final_status": result.get("final_status", "NEEDS_USER_REVIEW"),
        "rounds": len(result.get("verification_log", [])),
        "details": result.get("verification_log", []),
        "final_score": score,
        "score_breakdown": breakdown,
        "grade": grade,
        "timeline": timeline,
    }
