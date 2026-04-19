# Unified JSON Schema for AI Cybercrime Evidence Builder

## Service Communication Schema

### 1. OCR Service (Port 8001)

**Input:**
```json
{
  "file": "binary-image-or-pdf"
}
```

**Output:**
```json
{
  "text": "extracted text content",
  "entities": {
    "phones": [{"type": "phone", "value": "01012345678", "confidence": 0.95}],
    "amounts": [{"type": "amount", "value": "5000 EGP", "confidence": 0.90}],
    "dates": [{"type": "date", "value": "15/01/2024", "confidence": 0.85}],
    "accounts": [{"type": "account", "value": "@username", "confidence": 0.95}],
    "emails": []
  },
  "confidence": 0.92,
  "language": "ar"
}
```

### 2. Classifier Service (Port 8002)

**Input:**
```json
{
  "text": "ocr extracted text",
  "entities": {}
}
```

**Output:**
```json
{
  "crime_type": "blackmail|scam|threat|defamation|privacy_violation|unknown",
  "confidence": 0.92,
  "reasoning": "explanation of classification",
  "suggested_articles": ["Article 25 - Law 175/2018"],
  "missing_evidence": ["screenshot of threat", "proof of payment"]
}
```

### 3. RAG Service (Port 8003)

**Input:**
```json
{
  "query": "blackmail threat demanding money",
  "crime_type": "blackmail",
  "top_k": 5
}
```

**Output:**
```json
{
  "articles": [
    {
      "article_number": "25",
      "law": "Law 175/2018",
      "text": "Punishment for unauthorized access...",
      "relevance_score": 0.89,
      "penalty_ar": "الحبس و الغرامة"
    }
  ]
}
```

### 4. Verification Service (Port 8004)

**Input:**
```json
{
  "classification": {},
  "ocr_text": "extracted text",
  "entities": {},
  "law_articles": []
}
```

**Output:**
```json
{
  "final_status": "APPROVED|NEEDS_REVISION|NEEDS_USER_REVIEW",
  "rounds": 2,
  "timeline": [
    {
      "date": "2024-01-15",
      "type": "threat",
      "description": "First threat received"
    }
  ],
  "score": 85,
  "verification_summary": "All claims verified with evidence"
}
```

### 5. PDF Generation Service (Port 8005)

**Input:**
```json
{
  "case_id": "CASE_20240115_001",
  "crime_type": "blackmail",
  "evidence_summary": "...",
  "timeline": [],
  "law_articles": [],
  "score": 85,
  "grade": "STRONG",
  "complainant_name": "User Name",
  "language": "ar|en"
}
```

**Output:**
```json
{
  "pdf_path": "/outputs/complaint_CASE_001.pdf",
  "download_url": "/download/CASE_001.pdf",
  "pages": 3
}
```

### 6. API Gateway (Port 8000)

**Main Analysis Endpoint:**

**POST /analyze**
```json
{
  "files": ["uploaded-files"],
  "complainant_name": "User Name",
  "language": "ar"
}
```

**Response:**
```json
{
  "case_id": "CASE_20240115_001",
  "status": "completed",
  "ocr": {},
  "classification": {},
  "law_articles": [],
  "verification": {},
  "pdf_url": "/download/CASE_001.pdf",
  "score": 85,
  "grade": "STRONG"
}
```

## Error Response Schema

All services return errors in this format:

```json
{
  "error": true,
  "message": "Human readable error message",
  "code": "ERROR_CODE",
  "service": "service-name"
}
```

## Health Check Schema

All services must return:

```json
{
  "status": "healthy",
  "service": "service-name"
}
```

Or for detailed health:

```json
{
  "status": "healthy",
  "service": "rag",
  "articles_indexed": 42,
  "version": "1.0.0"
}
```

## Grade Classification

| Score | Grade | Color | Meaning |
|-------|-------|-------|---------|
| 75-100 | STRONG | Green | Ready for submission |
| 50-74 | MEDIUM | Yellow | Needs more evidence |
| 0-49 | WEAK | Red | Insufficient evidence |

## Crime Types

```json
{
  "blackmail": "Threats to expose unless demands met",
  "scam": "Financial fraud, deception for money",
  "threat": "Direct threats of harm",
  "defamation": "False statements damaging reputation",
  "privacy_violation": "Unauthorized sharing of private content",
  "unknown": "Could not determine crime type"
}
```
