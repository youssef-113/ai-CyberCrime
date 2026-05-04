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
        "sextortion",
        "financial_fraud",
        "phishing",
        "identity_theft",
        "cyber_threat",
        "defamation",
        "hate_speech",
        "privacy_violation",
        "data_breach",
        "account_hacking",
        "unknown",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    key_indicators: List[KeyIndicator]
    claims: List[Claim]
    missing_evidence: List[str]

    suggested_articles: List[dict]

    classifier_notes: str