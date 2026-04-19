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
