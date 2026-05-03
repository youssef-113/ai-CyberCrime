"""Evidence Scoring - Calculate strength score 0-100"""
from typing import Dict, Optional, Tuple

def calculate_score(
    verification: dict,
    entities: dict,
    article_count: int,
    evidence_blocks: Optional[list] = None,
) -> Tuple[int, dict]:
    """Calculate evidence strength score.

    Args:
        verification:     Dict with at least ``final_status``.
        entities:         Extracted entity dict (threats, amounts, phones, etc.).
        article_count:    Number of retrieved law articles.
        evidence_blocks:  Optional list of evidence block dicts for file/OCR checks.
    """
    if evidence_blocks is None:
        evidence_blocks = []

    crime_type = verification.get("crime_type", "").lower()

    breakdown = {
        "explicit_threat_found": 0,
        "financial_demand_found": 0,
        "contact_identified": 0,
        "multiple_evidence_files": 0,
        "ocr_confidence_high": 0,
        "law_articles_retrieved": 0,
        "date_timestamp_found": 0,
        "verification_passed": 0,
    }

    # Explicit threat (20 pts) – crime-type aware
    threat_types = {"blackmail", "extortion", "sextortion", "harassment", "stalking"}
    if crime_type in threat_types:
        if entities.get("threats") or any(
            t in str(entities.get("threat_keywords", []))
            for t in ["blackmail", "threat", "scam"]
        ):
            breakdown["explicit_threat_found"] = 20
    elif crime_type in {"financial_fraud", "phishing"}:
        # For financial crimes, threat = evidence of fraudulent intent
        if entities.get("threats") or entities.get("fraud_indicators"):
            breakdown["explicit_threat_found"] = 20
    else:
        # Generic: any threat signal
        if entities.get("threats"):
            breakdown["explicit_threat_found"] = 20

    # Financial demand (20 pts) – crime-type aware
    financial_types = {"financial_fraud", "phishing", "blackmail", "extortion", "sextortion"}
    if crime_type in financial_types:
        if entities.get("amounts"):
            breakdown["financial_demand_found"] = 20
    else:
        # Non-financial crimes still get points if amounts present
        if entities.get("amounts"):
            breakdown["financial_demand_found"] = 10

    # Contact identified (15 pts)
    if entities.get("phones") or entities.get("accounts") or entities.get("urls"):
        breakdown["contact_identified"] = 15

    # Multiple files (15 pts) – count from evidence_blocks when available
    if evidence_blocks:
        file_count = len({b.get("file_name") for b in evidence_blocks if b.get("file_name")})
    else:
        file_count = entities.get("file_count", 1)
    if file_count >= 2:
        breakdown["multiple_evidence_files"] = 15
    elif file_count == 1:
        breakdown["multiple_evidence_files"] = 5

    # OCR confidence (15 pts) – compute from evidence_blocks when available
    if evidence_blocks:
        confidences = [b.get("confidence", 0) for b in evidence_blocks]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
    else:
        avg_conf = entities.get("ocr_confidence", 0)
    if avg_conf > 0.75:
        breakdown["ocr_confidence_high"] = 15
    elif avg_conf > 0.5:
        breakdown["ocr_confidence_high"] = int(avg_conf * 15)

    # Law articles (10 pts)
    if article_count > 0:
        breakdown["law_articles_retrieved"] = min(article_count * 3, 10)

    # Date/timestamp (5 pts)
    if entities.get("dates"):
        breakdown["date_timestamp_found"] = 5

    # Verification passed (15 pts bonus)
    if verification.get("final_status") == "APPROVED":
        breakdown["verification_passed"] = 15
    elif verification.get("final_status") == "NEEDS_REVISION":
        breakdown["verification_passed"] = 10

    total = sum(breakdown.values())

    # Determine grade
    if total >= 75:
        grade = "STRONG"
    elif total >= 45:
        grade = "MEDIUM"
    else:
        grade = "WEAK"

    breakdown["grade"] = grade

    return total, breakdown
