from pydantic import BaseModel, Field
from typing import List, Literal


class KeyIndicator(BaseModel):
    indicator: str
    block_id: str
    significance: str


class Claim(BaseModel):
    claim: str
    evidence_block_ids: List[str]
    strength: Literal["strong", "medium", "weak"]


class ClassificationOutput(BaseModel):
    crime_type: Literal[
        "blackmail",
        "scam",
        "threat",
        "defamation",
        "privacy",
        "identity_theft",
        "general",
        "unknown",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    key_indicators: List[KeyIndicator]
    claims: List[Claim]
    missing_evidence: List[str]

    suggested_articles: List[dict]

    classifier_notes: str