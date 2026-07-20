from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EntityCollection(BaseModel):
    persons: List[str] = []
    phones: List[str] = []
    emails: List[str] = []
    urls: List[str] = []
    social_accounts: List[str] = []
    bank_accounts: List[str] = []
    iban: List[str] = []
    amounts: List[str] = []
    dates: List[str] = []


class TimelineEvent(BaseModel):
    date: str = ""
    event: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class OCRResponse(BaseModel):
    document_language: str = "unknown"
    crime_type: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    entities: EntityCollection = Field(default_factory=EntityCollection)
    timeline: List[TimelineEvent] = []
    raw_text: str = ""
    clean_text: str = ""


class OCRResult(BaseModel):
    text: str
    confidence: float
    engine: str = "surya"
    blocks: List[Dict[str, Any]] = []
    fallback_triggered: bool = False


class JobStatus(BaseModel):
    job_id: str
    status: str
    message: Optional[str] = None


class JobResult(BaseModel):
    job_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BatchOCRResponse(BaseModel):
    results: List[OCRResponse] = []
    errors: List[str] = []
    total_processed: int = 0
    total_errors: int = 0
