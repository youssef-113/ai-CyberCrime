from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Optional

from models import EntityCollection, OCRResponse, TimelineEvent

logger = logging.getLogger("ocr.reasoning")

QWEN_AVAILABLE = False
try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    QWEN_AVAILABLE = True
except ImportError:
    logger.warning("transformers/torch not installed — Qwen reasoning disabled")

MODEL_NAME = os.getenv("QWEN_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
DEVICE = "cuda" if QWEN_AVAILABLE and torch.cuda.is_available() else "cpu"

_model = None
_tokenizer = None


def _ensure_model() -> None:
    global _model, _tokenizer
    if _model is not None:
        return
    if not QWEN_AVAILABLE:
        logger.error("Cannot load Qwen — missing transformers/torch")
        return
    logger.info("Loading Qwen2.5-1B-Instruct on %s …", DEVICE)
    t0 = time.perf_counter()
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    _model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype="auto",
        device_map="auto",
        trust_remote_code=True,
    )
    logger.info("Qwen model loaded in %.1fs", time.perf_counter() - t0)


SYSTEM_PROMPT = (
    "You are a cybercrime evidence analysis assistant. "
    "Given OCR text extracted from an image or document, analyze it and "
    "return ONLY valid JSON. No markdown. No explanations. No additional text."
)

USER_PROMPT_TEMPLATE = """Analyze this OCR text and return valid JSON:

{{
  "document_language": "Arabic" or "English" or "Mixed",
  "crime_type": "classification (e.g. Online Fraud, Phishing, Threat, Harassment, Drug Trafficking, ...)",
  "confidence": 0.0-1.0,
  "summary": "brief English summary of the evidence",
  "entities": {{
    "persons": [],
    "phones": [],
    "emails": [],
    "urls": [],
    "social_accounts": [],
    "bank_accounts": [],
    "iban": [],
    "amounts": [],
    "dates": []
  }},
  "timeline": []
}}

IMPORTANT: Return ONLY the JSON object above. Preserve ALL Arabic text exactly.

OCR TEXT:
{ocr_text}"""


def reason_text(ocr_text: str) -> Optional[Dict[str, Any]]:
    if not ocr_text or not ocr_text.strip():
        return None
    try:
        _ensure_model()
    except Exception as exc:
        logger.warning("Qwen model load failed: %s", exc)
        return None
    if _model is None or _tokenizer is None:
        return None

    sanitized = ocr_text[:6000].strip()
    if not sanitized:
        return None

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(ocr_text=sanitized)},
    ]

    try:
        text = _tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = _tokenizer(text, return_tensors="pt").to(_model.device)

        with torch.no_grad():
            outputs = _model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False,
                temperature=None,
                top_p=None,
                top_k=None,
                pad_token_id=_tokenizer.eos_token_id,
            )

        response = _tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        response = response.strip()

        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        response = response.strip()

        data = json.loads(response)
        logger.info(
            "Qwen: language=%s crime_type=%s confidence=%s",
            data.get("document_language"), data.get("crime_type"), data.get("confidence"),
        )
        return data

    except json.JSONDecodeError as exc:
        logger.error("Qwen returned non-JSON: %s\nResponse: %s", exc, response)
        return None
    except Exception as exc:
        logger.error("Qwen reasoning failed: %s", exc)
        return None


def build_ocr_response(raw_text: str, clean_text: str, qwen_data: Optional[Dict[str, Any]] = None) -> OCRResponse:
    if qwen_data is None:
        return OCRResponse(
            document_language="unknown",
            crime_type="",
            confidence=0.0,
            summary="",
            entities=EntityCollection(),
            timeline=[],
            raw_text=raw_text,
            clean_text=clean_text,
        )

    entities_raw = qwen_data.get("entities", {})

    def _ensure_str_list(items):
        return [str(i) for i in (items or [])]

    entity_collection = EntityCollection(
        persons=_ensure_str_list(entities_raw.get("persons")),
        phones=_ensure_str_list(entities_raw.get("phones")),
        emails=_ensure_str_list(entities_raw.get("emails")),
        urls=_ensure_str_list(entities_raw.get("urls")),
        social_accounts=_ensure_str_list(entities_raw.get("social_accounts")),
        bank_accounts=_ensure_str_list(entities_raw.get("bank_accounts")),
        iban=_ensure_str_list(entities_raw.get("iban")),
        amounts=_ensure_str_list(entities_raw.get("amounts")),
        dates=_ensure_str_list(entities_raw.get("dates")),
    )

    timeline_raw = qwen_data.get("timeline", [])
    timeline = [
        TimelineEvent(
            date=t.get("date", ""),
            event=t.get("event", ""),
            confidence=t.get("confidence", 0.0),
        )
        for t in timeline_raw
    ]

    return OCRResponse(
        document_language=qwen_data.get("document_language", "unknown"),
        crime_type=qwen_data.get("crime_type", ""),
        confidence=min(max(float(qwen_data.get("confidence", 0.0)), 0.0), 1.0),
        summary=qwen_data.get("summary", ""),
        entities=entity_collection,
        timeline=timeline,
        raw_text=raw_text,
        clean_text=clean_text,
    )
