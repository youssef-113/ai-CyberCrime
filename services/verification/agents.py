"""Multi-Agent Verification: Attacker + Judge"""
import httpx
import os
from typing import List, Dict

LLM_API_KEY = os.getenv("LLM_API_KEY", "")

async def run_verification_agents(evidence: str, entities: dict, classification: dict, articles: List[dict]) -> dict:
    """Run Attacker-Judge multi-round verification"""
    
    max_rounds = 3
    rounds = []
    
    # Initial claim from classification
    claim = f"The evidence shows {classification.get('crime_type', 'unknown')} with confidence {classification.get('confidence', 0)}"
    
    for round_num in range(1, max_rounds + 1):
        # Attacker challenges the claim
        attacker_challenge = await attacker_agent(claim, evidence, round_num)
        
        # Judge evaluates
        judge_decision = await judge_agent(claim, evidence, attacker_challenge, articles)
        
        rounds.append({
            "round": round_num,
            "attacker_challenge": attacker_challenge,
            "judge_decision": judge_decision["decision"],
            "status": judge_decision["status"]
        })
        
        # If approved, stop
        if judge_decision["status"] == "APPROVED":
            break
        
        # Update claim for next round
        claim = judge_decision.get("revised_claim", claim)
    
    final_status = rounds[-1]["status"] if rounds else "NEEDS_USER_REVIEW"
    
    return {
        "final_status": final_status,
        "rounds": len(rounds),
        "details": rounds
    }

async def attacker_agent(claim: str, evidence: str, round_num: int) -> str:
    """Attacker: Finds weaknesses in the claim"""
    
    prompt = f"""You are a skeptical prosecutor challenging this legal claim.

CLAIM: {claim}
EVIDENCE: {evidence[:2000]}
ROUND: {round_num}

Find SPECIFIC weaknesses:
1. What evidence is MISSING to support this claim?
2. Are there ALTERNATIVE interpretations?
3. Are there logical GAPS?

Respond with 2-3 specific challenges. Be harsh but factual."""

    return await call_llm(prompt)

async def judge_agent(claim: str, evidence: str, challenge: str, articles: List[dict]) -> dict:
    """Judge: Evaluates claim against challenge"""
    
    articles_text = "\n".join([f"- {a['text']}" for a in articles[:3]])
    
    prompt = f"""You are a fair judge evaluating a legal claim against challenges.

CLAIM: {claim}
EVIDENCE: {evidence[:2000]}
CHALLENGE: {challenge}
RELEVANT LAW:
{articles_text}

Decide:
1. Is the claim FULLY SUPPORTED by evidence? (APPROVED)
2. Needs minor fixes? (NEEDS_REVISION)
3. Major issues? (NEEDS_USER_REVIEW)

Respond in format:
DECISION: <brief reasoning>
STATUS: APPROVED|NEEDS_REVISION|NEEDS_USER_REVIEW
REVISED_CLAIM: <if applicable>"""

    response = await call_llm(prompt)
    
    # Parse response
    status = "NEEDS_USER_REVIEW"
    if "APPROVED" in response:
        status = "APPROVED"
    elif "NEEDS_REVISION" in response:
        status = "NEEDS_REVISION"
    
    return {
        "decision": response[:200],
        "status": status,
        "revised_claim": claim
    }

async def call_llm(prompt: str) -> str:
    """Call LLM API"""
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": LLM_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=30.0
            )
            
            result = response.json()
            return result.get("content", [{}])[0].get("text", "No response")
        except Exception as e:
            return f"Error: {str(e)}"
