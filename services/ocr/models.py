"""Pydantic models for OCR Service"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional


class ExtractedEntity(BaseModel):
    """Single extracted entity"""
    type: str
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_block: Optional[str] = None


class EvidenceBlock(BaseModel):
    """Single block of extracted evidence with metadata"""
    block_id: str
    file_name: str
    raw_text: str
    normalized_text: str
    confidence: float = Field(ge=0.0, le=1.0)
    quality_flag: str  # OK, LOW_CONFIDENCE, FALLBACK_USED
    ocr_source: str  # easyocr, paddleocr
    bbox: Optional[List[float]] = None  # Bounding box [x1, y1, x2, y2]


class ConfidenceScore(BaseModel):
    """Confidence scoring with thresholds and weighted average"""
    average: float = Field(ge=0.0, le=1.0)
    minimum: float = Field(ge=0.0, le=1.0)
    weighted_average: float = Field(ge=0.0, le=1.0)
    status: str  # high, medium, low
    filtered_word_count: int = 0  # words removed due to low confidence


class OCRResult(BaseModel):
    """Result from single OCR engine"""
    text: str
    confidence: float
    blocks: List[EvidenceBlock]
    engine: str  # easyocr, paddleocr
    confidence_score: Optional[ConfidenceScore] = None
    fallback_triggered: bool = False


class EntityCollection(BaseModel):
    """Collection of all extracted entities"""
    phones: List[ExtractedEntity] = []
    amounts: List[ExtractedEntity] = []
    dates: List[ExtractedEntity] = []
    accounts: List[ExtractedEntity] = []
    urls: List[ExtractedEntity] = []
    emails: List[ExtractedEntity] = []
    ibans: List[ExtractedEntity] = []


class OCRResponse(BaseModel):
    """Full OCR service response"""
    evidence_blocks: List[EvidenceBlock]
    entities: EntityCollection
    full_text: str
    normalized_text: str
    avg_confidence: float = Field(ge=0.0, le=1.0)
    language: str  # ar, en, mixed
    processing_metadata: Dict


class BatchOCRRequest(BaseModel):
    """Request for batch OCR processing"""
    files: List[bytes]
    file_names: List[str]
    preprocessing: bool = True
    use_fallback: bool = True


class BatchOCRResponse(BaseModel):
    """Response for batch OCR processing"""
    results: List[OCRResponse]
    total_blocks: int
    avg_confidence: float
    processing_time_ms: float
