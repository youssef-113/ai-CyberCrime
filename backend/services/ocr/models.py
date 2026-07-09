"""
Pydantic models for OCR Service v2
Supports: Groq Vision API | PaddleOCR | Groq AI understanding layer
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Low-level blocks ───────────────────────────────────────────────────────────

class ExtractedEntity(BaseModel):
    """Single extracted entity from text"""
    type:         str
    value:        str
    confidence:   float = Field(ge=0.0, le=1.0)
    source_block: Optional[str] = None


class EvidenceBlock(BaseModel):
    """One OCR text block with full metadata"""
    block_id:        str
    file_name:       str
    raw_text:        str
    normalized_text: str
    confidence:      float = Field(ge=0.0, le=1.0)
    quality_flag:    str   # OK | LOW_CONFIDENCE | FALLBACK_USED
    ocr_source:      str   # groq_vision | paddleocr | groq_understanding | text_file
    bbox:            Optional[List[float]] = None  # [x1, y1, x2, y2]


class ConfidenceScore(BaseModel):
    """Confidence breakdown for a set of OCR word results"""
    average:            float = Field(ge=0.0, le=1.0)
    minimum:            float = Field(ge=0.0, le=1.0)
    weighted_average:   float = Field(ge=0.0, le=1.0)
    status:             str   # high | medium | low
    filtered_word_count: int  = 0


# ── Engine result ─────────────────────────────────────────────────────────────

class OCRResult(BaseModel):
    """Raw result from a single OCR engine pass"""
    text:              str
    confidence:        float
    blocks:            List[EvidenceBlock]
    engine:            str   # groq_vision | paddleocr | groq_understanding | none
    confidence_score:  Optional[ConfidenceScore] = None
    fallback_triggered: bool = False
    # Populated when Groq understanding layer ran
    groq_entities:     Optional[Dict[str, Any]] = None


# ── Entity collection ─────────────────────────────────────────────────────────

class EntityCollection(BaseModel):
    """All structured entities extracted from OCR text"""
    phones:   List[ExtractedEntity] = []
    amounts:  List[ExtractedEntity] = []
    dates:    List[ExtractedEntity] = []
    accounts: List[ExtractedEntity] = []
    urls:     List[ExtractedEntity] = []
    emails:   List[ExtractedEntity] = []
    ibans:    List[ExtractedEntity] = []


# ── Full service response ─────────────────────────────────────────────────────

class OCRResponse(BaseModel):
    """Complete OCR service response returned to the API gateway"""
    evidence_blocks:    List[EvidenceBlock]
    entities:           EntityCollection
    full_text:          str
    normalized_text:    str
    avg_confidence:     float = Field(ge=0.0, le=1.0)
    language:           str   # ar | en | mixed
    processing_metadata: Dict[str, Any]


# ── Async job models ──────────────────────────────────────────────────────────

class OCRJobStatus(BaseModel):
    """Async job lifecycle status"""
    job_id:  str
    status:  str            # PENDING | STARTED | SUCCESS | FAILURE | RETRY
    message: Optional[str] = None


class OCRJobResult(BaseModel):
    """Completed async job result"""
    job_id:  str
    status:  str
    result:  Optional[Dict[str, Any]] = None
    error:   Optional[str]            = None


# ── Metrics snapshot ──────────────────────────────────────────────────────────

class EngineStats(BaseModel):
    available: bool
    requests:  int = 0


class OCRMetrics(BaseModel):
    """Runtime metrics snapshot from the OCR engine"""
    total_requests:  int
    paddle_used:     int
    groq_used:       int
    errors:          int
    avg_confidence:  float
    avg_latency_ms:  float
    engines:         Dict[str, bool]


# ── Batch ─────────────────────────────────────────────────────────────────────

class BatchOCRResponse(BaseModel):
    evidence_blocks:    List[EvidenceBlock]
    full_text:          str
    normalized_text:    str
    avg_confidence:     float
    language:           str
    processing_metadata: Dict[str, Any]
