"""Celery tasks for async classification processing"""
import logging
import asyncio
from typing import Dict, Any
from celery import Task
from services.common.celery_app import celery_app

logger = logging.getLogger("classifier.tasks")


class ClassifierTask(Task):
    """Base task for classification operations with error handling"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f"Classifier task {task_id} failed: {str(exc)}")
        super().on_failure(exc, task_id, args, kwargs, einfo)


@celery_app.task(
    bind=True,
    base=ClassifierTask,
    name="services.classifier.tasks.classify_async",
    max_retries=3,
    default_retry_delay=60
)
def classify_async(self, text: str, entities: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify crime type asynchronously
    
    Args:
        text: Evidence text to classify
        entities: Extracted entities from OCR
    
    Returns:
        Classification result
    """
    try:
        from .prompts import CLASSIFICATION_PROMPT
        from .crime_definitions import CRIME_DEFINITIONS
        from .arabic_utils import normalize_arabic
        from .article_mapping import get_suggested_articles
        from .validators import build_validation_notes
        from services.common.llm_client import llm_request
        import os
        import json
        import re
        
        LLM_MODEL = os.getenv("LLM_MODEL", "")
        
        # Normalize text
        clean_text = normalize_arabic(text)
        
        # Build prompt
        prompt = CLASSIFICATION_PROMPT.format(
            text=clean_text[:4000],
            entities=str(entities),
            crime_definitions=CRIME_DEFINITIONS,
        )
        
        # Call LLM
        content = asyncio.run(llm_request(prompt, model=LLM_MODEL, max_tokens=1000))
        
        # Parse classification
        try:
            data = json.loads(content)
        except Exception:
            try:
                json_match = re.search(r"\{.*\}", content, re.DOTALL)
                if not json_match:
                    raise ValueError("No JSON found")
                data = json.loads(json_match.group())
            except Exception:
                data = {
                    "crime_type": "unknown",
                    "confidence": 0.0,
                    "key_indicators": [],
                    "claims": [],
                    "missing_evidence": ["Could not parse classifier response"],
                    "classifier_notes": content[:200],
                }
        
        classification = {
            "crime_type": data.get("crime_type", "unknown"),
            "confidence": data.get("confidence", 0.5),
            "key_indicators": data.get("key_indicators", []),
            "claims": data.get("claims", []),
            "missing_evidence": data.get("missing_evidence", []),
            "classifier_notes": data.get("classifier_notes", ""),
        }
        
        # Add validation notes
        validation_notes = build_validation_notes(
            classification.get("crime_type", "unknown"),
            entities,
        )
        if validation_notes:
            classification["missing_evidence"].extend(validation_notes)
        
        # Add suggested articles
        classification["suggested_articles"] = get_suggested_articles(
            classification.get("crime_type", "unknown"),
            classification.get("confidence", 0.0),
        )
        
        return {
            "status": "success",
            "classification": classification,
        }
        
    except Exception as e:
        logger.error(f"Classification failed: {str(e)}")
        raise
