"""Multi-Agent Verification: Attacker + Judge"""
import json
import re
import time

import httpx
import os

from typing import List, Optional
from .strategies import get_strategy
from .timeline import build_validated_timeline, timeline_summary

LLM_API_KEY = os.getenv("LLM_API_KEY", "")


async def run_verification_agents(
    evidence: str,
    entities: dict,
    classification: dict,
    articles: List[dict],
    evidence_blocks: Optional[List[dict]] = None,
    case_id: Optional[str] = None,
    store=None,
) -> dict:
    """Run Attacker-Judge multi-round verification with audit trail.

    This is the legacy entry-point kept for backwards compatibility.
    The LangGraph flow in ``graph.py`` is the preferred orchestrator.
    """
    if evidence_blocks is None:
        evidence_blocks = []

    max_rounds = 3
    rounds = []
    claims = classification.get("claims", [])
    crime_type = classification.get("crime_type", "generic")

    claim_text = (
        f"The evidence shows {crime_type} "
        f"with confidence {classification.get('confidence', 0)}"
    )

    for round_num in range(1, max_rounds + 1):
        t0 = time.monotonic()

        attacker_result = await attacker_agent(
            claim=claim_text,
            evidence=evidence,
            round_num=round_num,
            claims=claims,
            evidence_blocks=evidence_blocks,
            crime_type=crime_type,
        )

        judge_result = await judge_agent(
            claim=claim_text,
            evidence=evidence,
            challenge=attacker_result["combined_text"],
            articles=articles,
            evidence_blocks=evidence_blocks,
            entities=entities,
            round_num=round_num,
        )

        latency_ms = int((time.monotonic() - t0) * 1000)

        if store and case_id:
            store.save_round(
                case_id=case_id,
                round_num=round_num,
                attacker_data={
                    "prompt": attacker_result.get("prompt", ""),
                    "response": attacker_result.get("llm_response", ""),
                    "challenges": attacker_result.get("structured_challenges", []),
                },
                judge_data={
                    "prompt": judge_result.get("prompt", ""),
                    "response": judge_result.get("raw_response", ""),
                    "articles_cited": judge_result.get("articles_cited", []),
                    "claims_to_drop": judge_result.get("claims_to_drop", []),
                    "confidence": judge_result.get("confidence"),
                },
                status=judge_result["status"],
                latency_ms=latency_ms,
            )

        rounds.append({
            "round": round_num,
            "attacker_challenge": attacker_result["combined_text"],
            "attacker_structured": attacker_result["structured_challenges"],
            "judge_decision": judge_result["decision"],
            "status": judge_result["status"],
            "articles_cited": judge_result.get("articles_cited", []),
            "claims_to_drop": judge_result.get("claims_to_drop", []),
            "confidence": judge_result.get("confidence"),
            "latency_ms": latency_ms,
        })

        if judge_result["status"] == "APPROVED":
            break

        # Drop unsupported claims for next round
        dropped = judge_result.get("claims_to_drop", [])
        if dropped:
            claims = [
                c for c in claims
                if c.get("claim", c.get("text", "")) not in dropped
                and str(c) not in dropped
            ]

        claim_text = judge_result.get("revised_claim", claim_text)

    final_status = rounds[-1]["status"] if rounds else "NEEDS_USER_REVIEW"

    return {
        "final_status": final_status,
        "rounds": len(rounds),
        "details": rounds,
    }


async def attacker_agent(
    claim: str,
    evidence: str,
    round_num: int,
    claims: list,
    evidence_blocks: list,
    crime_type: str,
) -> dict:
    """Attacker: Finds weaknesses in the claim using crime-aware strategies.

    Returns a dict with:
        structured_challenges – list of strings from the strategy
        llm_response          – raw LLM text
        combined_text         – structured + LLM merged for prompt context
        prompt                – the full prompt sent to the LLM
    """
    strategy = get_strategy(crime_type)
    structured_challenges = strategy.generate_challenges(claims, evidence_blocks)
    structured_text = "\n".join(f"- {c}" for c in structured_challenges)

    prompt = f"""You are a skeptical prosecutor challenging this legal claim.

CLAIM: {claim}
EVIDENCE: {evidence[:2000]}
ROUND: {round_num}

STRUCTURED CHALLENGES ALREADY IDENTIFIED:
{structured_text}

Add 1-2 additional nuanced challenges beyond the above. Be harsh but factual."""

    llm_response = await call_llm(prompt)
    combined = structured_text + "\n" + llm_response

    return {
        "structured_challenges": structured_challenges,
        "llm_response": llm_response,
        "combined_text": combined,
        "prompt": prompt,
    }


async def judge_agent(
    claim: str,
    evidence: str,
    challenge: str,
    articles: list,
    evidence_blocks: list,
    entities: dict,
    round_num: int = 1,
) -> dict:
    """Judge: Evaluates claim against challenge with timeline context and law articles.

    Returns a dict with:
        decision       – reasoning text with article citations
        status         – APPROVED | NEEDS_REVISION | NEEDS_USER_REVIEW
        articles_cited – list of article identifiers (e.g. ["Art. 336"])
        claims_to_drop – list of claim texts/indices to remove
        confidence     – 0.0–1.0
        revised_claim  – updated claim text (if NEEDS_REVISION)
        raw_response   – the raw LLM output
        prompt         – the full prompt sent to the LLM
    """
    timeline = build_validated_timeline(evidence, entities, evidence_blocks)
    timeline_text = timeline_summary(timeline)

    articles_text = "\n".join(
        f"- Article {a.get('article_number', '?')} ({a.get('law', '?')}): "
        f"{a.get('text', '')[:200]}"
        for a in articles[:3]
    )

    prompt = f"""You are a fair judge evaluating legal claims against evidence and law.

CLAIM: {claim}
EVIDENCE: {evidence[:2000]}
ATTACKER CHALLENGES: {challenge}

EVIDENCE TIMELINE:
{timeline_text}

RELEVANT LAW ARTICLES:
{articles_text}

DECISION RULES:
1. APPROVED: Claim fully supported by evidence AND aligns with cited articles.
2. NEEDS_REVISION: Claim partially supported; drop unsupported portions.
3. NEEDS_USER_REVIEW: Major gaps between claims and evidence.

You MUST cite specific article numbers in your reasoning.

Respond in valid JSON only:
{{
    "decision": "detailed reasoning with article citations",
    "status": "APPROVED|NEEDS_REVISION|NEEDS_USER_REVIEW",
    "claims_to_drop": ["claim text or index"],
    "articles_cited": ["Art. X"],
    "confidence": 0.0
}}"""

    raw_response = await call_llm(prompt)

    parsed = _parse_judge_json(raw_response)

    return {
        "decision": parsed.get("decision", raw_response[:200]),
        "status": parsed.get("status", _infer_status(raw_response)),
        "articles_cited": parsed.get("articles_cited", []),
        "claims_to_drop": parsed.get("claims_to_drop", []),
        "confidence": parsed.get("confidence"),
        "revised_claim": claim,
        "raw_response": raw_response,
        "prompt": prompt,
    }


# ── helpers ──────────────────────────────────────────────────────────────


def _parse_judge_json(raw: str) -> dict:
    """Extract JSON object from LLM response, tolerating surrounding text."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    m = re.search(r"```(?:json)?\s*(\{.*?})\s*```", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    m = re.search(r"\{.*}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    return {}


def _infer_status(raw: str) -> str:
    """Fallback status detection from raw text."""
    if "APPROVED" in raw:
        return "APPROVED"
    if "NEEDS_REVISION" in raw:
        return "NEEDS_REVISION"
    return "NEEDS_USER_REVIEW"


async def call_llm(prompt: str) -> str:
    """Call LLM API"""

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": LLM_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30.0,
            )

            result = response.json()
            return result.get("content", [{}])[0].get("text", "No response")
        except Exception as e:
            return f"Error: {str(e)}"
 