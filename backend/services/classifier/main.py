"""Classifier Service - Stage 3a: Crime Classification"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import httpx
import os
import json
import re

from .prompts import CLASSIFICATION_PROMPT
from .models import ClassificationOutput
from .crime_definitions import CRIME_DEFINITIONS
from .validators import build_validation_notes
from .article_mapping import get_suggested_articles
from .arabic_utils import normalize_arabic
from .metrics_runtime import start_timer, record_classification, get_runtime_metrics
from services.common.llm_client import llm_request

router = APIRouter(prefix="/classifier")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")


class ClassificationRequest(BaseModel):
    text: str
    entities: dict
    user_id: Optional[str] = None  # For metrics tracking
    session_id: Optional[str] = None  # For metrics tracking


CRIME_TYPES = list(CRIME_DEFINITIONS.keys())


@router.get("/health")
def health():
    """
    Liveness + readiness probe.
    Checks: LLM reachability, Redis availability.
    """
    import httpx as _httpx

    llm_ok    = False
    redis_ok  = False

    # LLM check (Ollama or Groq)
    llm_provider = os.getenv("LLM_PROVIDER", "ollama")
    try:
        if llm_provider == "ollama":
            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
            r = _httpx.get(f"{ollama_url}/api/tags", timeout=3.0)
            llm_ok = r.status_code == 200
        else:
            # Groq — just verify key present
            llm_ok = bool(os.getenv("GROQ_API_KEY", ""))
    except Exception:
        llm_ok = False

    # Redis check
    try:
        from services.common.cache import cache
        redis_ok = cache.enabled
    except Exception:
        redis_ok = False

    status = "healthy" if llm_ok else "degraded"
    return {
        "status":  status,
        "service": "classifier",
        "version": "1.0.0",
        "llm":     "ok" if llm_ok    else "unavailable",
        "redis":   "ok" if redis_ok  else "unavailable",
    }


@router.get("/metrics")
def metrics():
    return get_runtime_metrics()


@router.post("/classify", response_model=ClassificationOutput)
async def classify(request: ClassificationRequest):
    start_time = start_timer()

    clean_text = normalize_arabic(request.text)

    prompt = CLASSIFICATION_PROMPT.format(
        text=clean_text[:4000],
        entities=str(request.entities),
        crime_definitions=CRIME_DEFINITIONS,
    )

    content = ""
    fallback_note = ""

    try:
        content = await llm_request(prompt, model=LLM_MODEL, max_tokens=1000)
    except Exception as e:
        fallback_note = f"LLM call failed: {str(e)}"

    classification = parse_classification(content)

    if not content and fallback_note:
        classification["classifier_notes"] = fallback_note

    validation_notes = build_validation_notes(
        classification.get("crime_type", "unknown"),
        request.entities,
    )

    if validation_notes:
        classification["missing_evidence"].extend(validation_notes)

    classification["suggested_articles"] = get_suggested_articles(
        classification.get("crime_type", "unknown"),
        classification.get("confidence", 0.0),
    )

    latency = start_timer() - start_time

    record_classification(
        crime_type=classification.get("crime_type", "unknown"),
        latency_seconds=latency,
        success=True,
    )

    return ClassificationOutput(**classification)


def parse_classification(content: str) -> dict:
    try:
        data = json.loads(content)
    except Exception:
        try:
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found")

            data = json.loads(json_match.group())
        except Exception:
            return {
                "crime_type": "unknown",
                "confidence": 0.0,
                "key_indicators": [],
                "claims": [],
                "missing_evidence": ["Could not parse classifier response as JSON"],
                "classifier_notes": content[:200],
            }

    return {
        "crime_type": data.get("crime_type", "unknown"),
        "confidence": data.get("confidence", 0.5),
        "key_indicators": data.get("key_indicators", []),
        "claims": data.get("claims", []),
        "missing_evidence": data.get("missing_evidence", []),
        "classifier_notes": data.get("classifier_notes", ""),
    }

