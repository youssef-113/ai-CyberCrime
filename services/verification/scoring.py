"""Evidence Scoring - Calculate strength score 0-100"""
from typing import Dict, Tuple

def calculate_score(verification: dict, entities: dict, article_count: int) -> Tuple[int, dict]:
    """Calculate evidence strength score"""
    
    breakdown = {
        "explicit_threat_found": 0,
        "financial_demand_found": 0,
        "contact_identified": 0,
        "multiple_evidence_files": 0,
        "ocr_confidence_high": 0,
        "law_articles_retrieved": 0,
        "date_timestamp_found": 0,
        "verification_passed": 0
    }
    
    # Explicit threat (20 pts)
    if entities.get("threats") or any(t in str(entities) for t in ["blackmail", "threat", "scam"]):
        breakdown["explicit_threat_found"] = 20
    
    # Financial demand (20 pts)
    if entities.get("amounts"):
        breakdown["financial_demand_found"] = 20
    
    # Contact identified (15 pts)
    if entities.get("phones") or entities.get("accounts"):
        breakdown["contact_identified"] = 15
    
    # Multiple files (15 pts)
    if entities.get("file_count", 1) >= 2:
        breakdown["multiple_evidence_files"] = 15
    
    # OCR confidence (15 pts)
    if entities.get("ocr_confidence", 0) > 0.8:
        breakdown["ocr_confidence_high"] = 15
    
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
