"""Classifier Service - Stage 3a: Crime Classification"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import httpx
import os
from prompts import CLASSIFICATION_PROMPT

app = FastAPI(title="Classifier Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-3-haiku-20240307")

class ClassificationRequest(BaseModel):
    text: str
    entities: dict

class ClassificationResponse(BaseModel):
    crime_type: str
    confidence: float
    reasoning: str
    suggested_articles: List[str]
    missing_evidence: List[str]

CRIME_TYPES = ["blackmail", "scam", "threat", "defamation", "privacy_violation", "unknown"]

@app.get("/health")
def health():
    return {"status": "healthy", "service": "classifier"}

@app.post("/classify", response_model=ClassificationResponse)
async def classify(request: ClassificationRequest):
    """Classify crime type using LLM"""
    
    # Build prompt
    prompt = CLASSIFICATION_PROMPT.format(
        text=request.text[:4000],
        entities=str(request.entities)
    )
    
    # Call LLM (Claude/OpenAI compatible)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": LLM_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": LLM_MODEL,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30.0
        )
        
        result = response.json()
        content = result.get("content", [{}])[0].get("text", "")
    
    # Parse JSON from LLM response
    classification = parse_classification(content)
    
    return ClassificationResponse(**classification)

def parse_classification(content: str) -> dict:
    """Parse LLM JSON response"""
    import json
    import re
    
    # Extract JSON from markdown code blocks if present
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
    if json_match:
        content = json_match.group(1)
    
    try:
        data = json.loads(content)
        return {
            "crime_type": data.get("crime_type", "unknown"),
            "confidence": data.get("confidence", 0.5),
            "reasoning": data.get("reasoning", ""),
            "suggested_articles": data.get("suggested_articles", []),
            "missing_evidence": data.get("missing_evidence", [])
        }
    except json.JSONDecodeError:
        return {
            "crime_type": "unknown",
            "confidence": 0.0,
            "reasoning": "Failed to parse classification",
            "suggested_articles": [],
            "missing_evidence": []
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
