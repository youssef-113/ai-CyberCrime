"""Pydantic Models for API Gateway"""
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

class AnalysisRequest(BaseModel):
    text: Optional[str] = None
    priority: str = "normal"  # normal, urgent

class Entity(BaseModel):
    type: str
    value: str
    confidence: float

class LawArticle(BaseModel):
    article_number: str
    law: str
    text: str
    relevance_score: float
    penalty_ar: Optional[str] = None

class TimelineEvent(BaseModel):
    id: str
    date: str
    type: str
    description: str
    source: str

class ClassificationResult(BaseModel):
    crime_type: str
    confidence: float
    reasoning: str
    suggested_articles: List[str]
    missing_evidence: List[str]

class VerificationResult(BaseModel):
    status: str
    rounds: int
    final_score: int
    score_breakdown: Dict

class AnalysisResult(BaseModel):
    case_id: str
    created_at: datetime
    classification: ClassificationResult
    entities: Dict[str, List[Entity]]
    articles: List[LawArticle]
    verification: VerificationResult
    timeline: List[TimelineEvent]
    score: int
    grade: str

class CaseSummary(BaseModel):
    case_id: str
    crime_type: str
    created_at: datetime
    status: str
    score: int
    grade: str

# -----------------------------
# Test Case Models (added for test_cases JSON validation)
# -----------------------------

class ExpectedEntities(BaseModel):
    amounts: Optional[List[str]] = []
    phones: Optional[List[str]] = []


class EvidenceBlock(BaseModel):
    block_id: str
    text: str
    expected_entities: ExpectedEntities


class ExpectedOutput(BaseModel):
    crime_type: str
    expected_articles: List[str]
    expected_entities: ExpectedEntities
    expected_min_score: int


class TestCase(BaseModel):
    case_id: str
    crime_type: str
    difficulty: str
    evidence_texts: List[EvidenceBlock]
    expected_output: ExpectedOutput


# -----------------------------
# OCR Proxy Models (matches OCR service response)
# -----------------------------

class OCRExtractedEntity(BaseModel):
    type: str
    value: str
    confidence: float
    source_block: Optional[str] = None


class OCREvidenceBlock(BaseModel):
    block_id: str
    file_name: str
    raw_text: str
    normalized_text: str
    confidence: float
    quality_flag: str
    ocr_source: str
    bbox: Optional[List[float]] = None


class OCRConfidenceScore(BaseModel):
    average: float
    minimum: float
    weighted_average: float
    status: str  # high, medium, low
    filtered_word_count: int = 0


class OCRProcessingMetadata(BaseModel):
    processing_time_ms: float = 0
    engine_used: str = "unknown"
    fallback_triggered: bool = False
    blocks_count: int = 0
    confidence_score: Optional[OCRConfidenceScore] = None


class OCRProxyResponse(BaseModel):
    """Structured OCR response from the gateway /ocr/extract endpoint"""
    evidence_blocks: List[OCREvidenceBlock] = []
    entities: Dict = {}
    full_text: str = ""
    normalized_text: str = ""
    avg_confidence: float = 0
    language: str = "unknown"
    processing_metadata: OCRProcessingMetadata = OCRProcessingMetadata()


class OCRPerFileSummary(BaseModel):
    """Per-file OCR summary in pipeline results"""
    file: str
    engine: str
    confidence: float
    fallback_triggered: bool = False
    confidence_score: Optional[OCRConfidenceScore] = None
    language: str = "unknown"


class OCRMetadata(BaseModel):
    """OCR metadata in pipeline results"""
    avg_confidence: float = 0
    evidence_blocks: List[Dict] = []
    per_file: List[OCRPerFileSummary] = []