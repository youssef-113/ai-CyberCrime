# ACEB — Technical Architecture Document

**AI Cybercrime Evidence Builder**  
Version: 1.0 | Status: TRL 1 → TRL 4 (Active Development)  
Law No. 175/2018 · Egyptian Penal Code · RAG + Multi-Agent AI

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Principles](#2-architecture-principles)
3. [Service Architecture](#3-service-architecture)
4. [Data Flow & Pipeline](#4-data-flow--pipeline)
5. [OCR & NLP Layer](#5-ocr--nlp-layer)
6. [LLM Classification Engine](#6-llm-classification-engine)
7. [RAG Legal Retrieval](#7-rag-legal-retrieval)
8. [Multi-Agent Verification](#8-multi-agent-verification)
9. [Evidence Scoring Engine](#9-evidence-scoring-engine)
10. [PDF Generation](#10-pdf-generation)
11. [Legal Chatbot](#11-legal-chatbot)
12. [Data Schema](#12-data-schema)
13. [Infrastructure & DevOps](#13-infrastructure--devops)
14. [Security & Privacy](#14-security--privacy)
15. [Performance Targets](#15-performance-targets)

---

## 1. System Overview

ACEB is a microservices-based AI pipeline that transforms raw crime evidence (screenshots, PDFs, text) into legally grounded complaint documents under Egyptian law. The system operates in Arabic and English and is designed to run entirely on a single `docker-compose up` command.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          ACEB System Boundary                           │
│                                                                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────────┐   │
│  │  Upload  │──▶│   OCR    │──▶│  Classify│──▶│  Legal RAG       │   │
│  │  (User)  │   │  :8001   │   │  :8002   │   │  :8003 ChromaDB  │   │
│  └──────────┘   └──────────┘   └──────────┘   └──────────────────┘   │
│                                                         │               │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐           │               │
│  │ PDF Gen  │◀──│  Score   │◀──│  Verify  │◀──────────┘               │
│  │  :8005   │   │  Engine  │   │  :8004   │                           │
│  └──────────┘   └──────────┘   └──────────┘                           │
│        │                                                                │
│        ▼                                                                │
│  ┌──────────┐   ┌──────────┐                                           │
│  │  محضر    │   │ Chatbot  │  ← User-facing outputs                   │
│  │  (PDF)   │   │  :8006   │                                           │
│  └──────────┘   └──────────┘                                           │
│                                                                         │
│  Orchestrated by: Main API (port 8000)                                 │
│  Frontend: Streamlit (port 8501) / React (production)                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Architecture Principles

### 2.1 Zero Hallucination

Every claim in the system output must be grounded in evidence. Two mechanisms enforce this:

1. **Citation-forcing prompts** — the LLM classifier cannot make a claim without citing the `evidence_block_id` that supports it. If no block supports the claim, the claim cannot exist.
2. **Citation validator** — before PDF generation, every law article is verified against the ChromaDB knowledge base. Articles that don't exist in the database cannot appear in the complaint.

### 2.2 Evidence Traceability

Every piece of information is tagged with its origin:

```
Raw image → OCR block (block_id: E001) → extracted entity → classifier claim → law article → PDF section
```

The `block_id` travels through the entire pipeline. The attacker agent uses it to verify claims. The PDF appendix traces every statement back to its source.

### 2.3 Microservices Isolation

Each pipeline stage is an independent Docker container with its own FastAPI endpoint. Services communicate only through JSON over HTTP. A failure in any one service does not cascade to others — the orchestrator handles graceful degradation.

### 2.4 Arabic-First Design

All text normalisation, embedding models, PDF rendering, and UI copy are designed for Arabic as the primary language. English is supported but secondary.

---

## 3. Service Architecture

| Service | Port | Image | Memory | Purpose |
|---------|------|-------|--------|---------|
| `api` | 8000 | python:3.11-slim | 256 MB | Pipeline orchestrator |
| `ocr` | 8001 | python:3.11-slim + libgl | 1.5 GB | EasyOCR + entity extraction |
| `classifier` | 8002 | python:3.11-slim | 256 MB | LLM crime classification |
| `rag` | 8003 | python:3.11-slim | 512 MB | ChromaDB legal retrieval |
| `verification` | 8004 | python:3.11-slim | 256 MB | Attacker + Judge agents |
| `pdf_gen` | 8005 | python:3.11-slim + pango | 256 MB | WeasyPrint Arabic PDF |
| `chatbot` | 8006 | python:3.11-slim | 256 MB | Legal chatbot session |
| `frontend` | 8501 | python:3.11-slim | 256 MB | Streamlit demo UI |
| `chromadb` | 8006 | chromadb/chroma:latest | 512 MB | Vector database |

**Shared volumes:**
- `./data` — law PDFs, ChromaDB index, test cases
- `./outputs` — generated PDFs (auto-cleared after 24h)
- `./assets/fonts` — Amiri, Cairo Arabic fonts

---

## 4. Data Flow & Pipeline

### 4.1 Request Lifecycle

```
POST /analyze  (multipart/form-data: files[])
      │
      ▼
┌─ api/:8000 ─────────────────────────────────────────────────────────────┐
│                                                                         │
│  1. Validate files (max 10, types: PNG/JPG/PDF, max 10MB each)         │
│  2. Generate case_id (UUID4)                                            │
│  3. Sequential service calls:                                           │
│                                                                         │
│     POST /ocr → {evidence_blocks, entities, avg_confidence}            │
│          │                                                              │
│     POST /classify ← ocr_output                                        │
│          │ → {crime_type, confidence, claims, missing_evidence}         │
│          │                                                              │
│     POST /retrieve ← crime_type + full_text                            │
│          │ → {articles: [{article_id, law, text, penalty, score}]}     │
│          │                                                              │
│     POST /verify ← claims + articles + evidence_blocks                 │
│          │ → {status: APPROVED|NEEDS_REVISION, rounds, log}            │
│          │                                                              │
│     POST /score ← all previous outputs                                 │
│          │ → {total_score, breakdown, grade}                            │
│          │                                                              │
│     POST /pdf ← all structured data                                    │
│          │ → application/pdf (binary)                                   │
│                                                                         │
│  4. Return PDF as FileResponse                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 JSON Endpoints

The `/analyze/json` endpoint returns the full structured pipeline output without generating the PDF — used by the frontend to display intermediate results and by the chatbot to load case context:

```json
{
  "case_id": "CASE_A3F2B1",
  "crime_type": "blackmail",
  "confidence": 0.92,
  "timeline": [...],
  "entities": {"phones": [...], "amounts": [...], "dates": [...]},
  "claims": [...],
  "articles": [...],
  "score": {"total_score": 87, "breakdown": {...}, "grade": "STRONG"},
  "verification": {"status": "APPROVED", "rounds": 2, "log": [...]}
}
```

---

## 5. OCR & NLP Layer

**Service:** `ocr` | **Port:** 8001 | **Owner:** M1

### 5.1 OCR Strategy

```python
def extract_text(image_bytes: bytes) -> dict:
    # Primary: EasyOCR (free, offline, Arabic + English)
    reader = easyocr.Reader(['ar', 'en'], gpu=False)
    results = reader.readtext(image_bytes, detail=True)
    avg_conf = mean([r[2] for r in results]) if results else 0

    if avg_conf >= 0.65:
        return build_response("easyocr", results, avg_conf)
    else:
        # Fallback: Google Cloud Vision API
        return call_google_vision(image_bytes)
```

**Confidence threshold:** 0.65. Below this, Google Vision is called automatically.

### 5.2 Arabic Text Normalisation

Applied to all extracted text before classification:

```python
def normalize_arabic(text: str) -> str:
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)  # Remove diacritics
    text = re.sub(r'[أإآٱ]', 'ا', text)                # Unify Alef variants
    text = text.replace('ة', 'ه')                       # Unify Ta marbuta
    text = text.replace('ﻭ', 'و').replace('ﻱ', 'ي')    # Fix OCR confusion
    text = re.sub(r'\s+', ' ', text).strip()
    return text
```

### 5.3 Entity Extraction

Egyptian-specific regex patterns:

```python
PATTERNS = {
    "phone_eg":   r'(\+20|0)(10|11|12|15)\d{8}',
    "amount_egp": r'\d{1,7}[,.]?\d*\s*(جنيه|ج\.م|EGP|LE|الف|k)',
    "iban_eg":    r'EG\d{27}',
    "date_ar":    r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',
    "url":        r'https?://\S+|www\.\S+',
}
```

Named entities (names, organisations) extracted via AraBERT NER.

---

## 6. LLM Classification Engine

**Service:** `classifier` | **Port:** 8002 | **Owner:** M2

### 6.1 Citation-Forcing Prompt Architecture

The critical design decision: the LLM cannot make any claim without citing a specific `evidence_block_id`. This is enforced structurally — not by instruction alone, but by the JSON schema that the response must conform to:

```python
SYSTEM_PROMPT = """
You are a certified Egyptian cybercrime legal analyst.

ABSOLUTE RULE: You may ONLY make a claim if you can cite the exact 
evidence_block_id (E001, E002...) that directly supports it.
If no block supports the claim → DO NOT make the claim.

You must respond ONLY in valid JSON matching the schema below.
No prose. No explanation outside the JSON structure.
"""

# Response schema (enforced via Pydantic validation):
class ClassificationOutput(BaseModel):
    crime_type: Literal["blackmail","scam","threat","defamation","privacy_violation","unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    key_indicators: List[KeyIndicator]      # Each must have block_id
    claims: List[Claim]                     # Each must have evidence_block_ids
    missing_evidence: List[str]
    classifier_notes: str
```

### 6.2 Crime Type Mapping

| crime_type | Arabic | Primary Articles |
|-----------|--------|-----------------|
| `blackmail` | ابتزاز | Art. 25, 26 (Law 175) + Art. 327 Penal |
| `scam` | احتيال مالي | Art. 23 (Law 175) + Art. 336 Penal |
| `threat` | تهديد | Art. 24, 27 (Law 175) + Art. 327 Penal |
| `defamation` | تشهير / قذف | Art. 302, 303, 308 Penal + Art. 25 Law 175 |
| `privacy_violation` | انتهاك خصوصية | Art. 25, 26 (Law 175) + Art. 309 مكرر |

### 6.3 LLM Selection

| Environment | Model | Rate Limit | Use |
|------------|-------|-----------|-----|
| Production | Claude Sonnet 4.6 | As per plan | Classification + chatbot |
| Development | Gemini 1.5 Flash | 15 req/min, 1M tokens/day | Testing (free) |
| Fallback | GPT-4o-mini | As per plan | Emergency fallback |

---

## 7. RAG Legal Retrieval

**Service:** `rag` | **Port:** 8003 | **Owner:** M2

### 7.1 Knowledge Base Construction

**Chunking strategy:** One chunk = one article (not paragraph splitting). This is critical for legal text — an article must be retrieved in full, not fragmented.

```python
law_articles = [
    {
        "text": "المادة 25: يعاقب بالحبس مدة لا تقل عن 6 أشهر...",
        "article_number": "25",
        "law": "175/2018",
        "crime_type": "blackmail",      # Primary filter key
        "penalty": "6 months - 1 year",
        "penalty_ar": "حبس من 6 أشهر إلى سنة + غرامة 50,000–100,000 جنيه",
        "article_id": "law175_art25"
    }
]

vectorstore = Chroma.from_texts(
    texts=[a["text"] for a in law_articles],
    embedding=HuggingFaceEmbeddings(
        model_name="intfloat/multilingual-e5-large"
    ),
    metadatas=law_articles,
    persist_directory="data/law_db"
)
```

**Embedding model:** `intfloat/multilingual-e5-large` — chosen because it handles Arabic and English in the same vector space, enabling cross-language semantic matching.

### 7.2 Retrieval Strategy

```python
def retrieve_articles(case_text: str, crime_type: str, k: int = 5) -> list:
    query = f"جريمة {crime_type_arabic[crime_type]}: {case_text[:300]}"
    results = vectorstore.similarity_search_with_score(
        query=query,
        k=k,
        filter={"crime_type": crime_type}    # Hard filter by crime type
    )
    return [
        {**r[0].metadata, "relevance_score": float(r[1])}
        for r in results if r[1] < 0.7      # Distance threshold
    ]
```

**Hard filter:** Articles are always filtered by `crime_type` metadata. A blackmail query cannot accidentally retrieve fraud articles.

### 7.3 Citation Validation

Before any article reaches the PDF:

```python
def validate_citations(articles: list, crime_type: str) -> dict:
    valid, invalid = [], []
    for article in articles:
        result = vectorstore.get(where={"article_id": article["article_id"]})
        if result["documents"] and article["crime_type"] == crime_type:
            valid.append(article)
        else:
            invalid.append({"article": article, "reason": "Not in KB or wrong crime type"})
    return {"valid": valid, "invalid": invalid,
            "status": "PASSED" if not invalid else "FAILED"}
```

---

## 8. Multi-Agent Verification

**Service:** `verification` | **Port:** 8004 | **Owner:** M3

### 8.1 Attacker Agent

The Attacker plays the role of a hostile defense lawyer. Its sole purpose is to find claims that cannot be verified from the evidence blocks:

```python
ATTACKER_PROMPT = """
You are a hostile defense lawyer. Your job is to DISCREDIT this report.

For each claim, determine: SUPPORTED or UNSUPPORTED.
A claim is UNSUPPORTED if:
  - No evidence_block_id is cited
  - The cited block does not actually contain the claimed information
  - The claim is an inference not directly stated in the evidence

Claims: {claims}
Evidence blocks: {evidence_blocks}

Return JSON: {"attacks": [{"claim": str, "verdict": "SUPPORTED|UNSUPPORTED", "reason": str}]}
"""
```

### 8.2 Judge Agent

The Judge reviews the Attacker's findings and issues a verdict:

```python
JUDGE_PROMPT = """
Review the attacker's findings and issue a verdict.

APPROVED: All claims are supported. Report is safe for submission.
NEEDS_REVISION: {n} unsupported claims found. Drop them and resubmit.

Attack results: {attacks}
Unsupported count: {count}

Return JSON: {"verdict": "APPROVED|NEEDS_REVISION", "reasoning": str, "claims_to_drop": [str]}
"""
```

### 8.3 Revision Loop (LangGraph)

```python
def run_verification_loop(state: VerificationState) -> VerificationState:
    for round_num in range(1, 4):   # Maximum 3 rounds
        attack_result = run_attacker(state.claims, state.evidence_blocks)
        unsupported = [a for a in attack_result.attacks if a.verdict == "UNSUPPORTED"]

        judge_result = run_judge(attack_result, state.claims)
        state.verification_log.append({
            "round": round_num,
            "attacks_found": len(unsupported),
            "verdict": judge_result.verdict
        })

        if judge_result.verdict == "APPROVED":
            return state.model_copy(update={"status": "APPROVED", "rounds": round_num})

        # Auto-remove unsupported claims and retry
        bad_claims = {a.claim for a in unsupported}
        state.claims = [c for c in state.claims if c.claim not in bad_claims]

    return state.model_copy(update={"status": "NEEDS_USER_REVIEW"})
```

**Termination:** Loop terminates on `APPROVED` or after 3 rounds. If 3 rounds fail, user is shown exactly which claims remain unsupported.

---

## 9. Evidence Scoring Engine

**Service:** Part of `verification` | **Owner:** M3

### 9.1 Score Weights

```python
SCORE_WEIGHTS = {
    "explicit_threat_found":    20,  # "هنشر"، "هكسر"، "هاجمك"
    "financial_demand_found":   20,  # Amount in EGP detected
    "contact_identified":       15,  # Phone number or account found
    "multiple_evidence_files":  15,  # > 1 file uploaded
    "ocr_confidence_high":      15,  # avg OCR confidence > 0.75
    "law_articles_retrieved":   10,  # ≥ 3 relevant articles matched
    "date_timestamp_found":      5,  # Timeline can be built
}
# Total: 100 points
```

### 9.2 Grade Boundaries

| Grade | Score | Meaning |
|-------|-------|---------|
| `STRONG` | ≥ 75 | High probability of authorities taking action |
| `MEDIUM` | 45–74 | Case is reportable; additional evidence recommended |
| `WEAK` | < 45 | Additional evidence needed before formal submission |

---

## 10. PDF Generation

**Service:** `pdf_gen` | **Port:** 8005 | **Owner:** M4

### 10.1 Technology Stack

**WeasyPrint** is chosen over alternatives (reportlab, fpdf2) because:
- Full CSS support including `direction: rtl` for Arabic
- Uses Pango + HarfBuzz for correct Arabic ligature joining
- Renders complex HTML templates faithfully

### 10.2 Template Structure (Jinja2)

```html
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<style>
  @font-face {
    font-family: Amiri;
    src: url('{{ font_path }}/Amiri-Regular.ttf');
  }
  body {
    direction: rtl;
    font-family: Amiri, serif;
    font-size: 13pt;
    color: #1a1a2e;
  }
  .score-badge {
    background: {% if score >= 75 %}#1f6b45{% elif score >= 45 %}#c8913a{% else %}#b84c1e{% endif %};
    color: white;
    padding: 6px 16px;
    font-size: 16pt;
    font-weight: bold;
  }
  .article-box {
    border-right: 4px solid #c8913a;
    padding: 8px 14px;
    margin: 8px 0;
    background: #fafaf7;
  }
</style>
</head>
<body>
  <!-- Section 1: Cover -->
  <h1>بلاغ جريمة إلكترونية — {{ crime_type_ar }}</h1>
  <div class="score-badge">قوة الأدلة: {{ score }}% — {{ grade }}</div>

  <!-- Section 2: Timeline -->
  {% for event in timeline %}
  <div class="timeline-item">{{ event.date }}: {{ event.summary }}</div>
  {% endfor %}

  <!-- Section 3: Law Articles -->
  {% for article in articles %}
  <div class="article-box">
    <strong>المادة {{ article.article_number }} — قانون {{ article.law }}</strong>
    <p>{{ article.text }}</p>
    <em>العقوبة: {{ article.penalty_ar }}</em>
  </div>
  {% endfor %}

  <!-- Section 4: Contacts -->
  <div class="contacts">
    <strong>للإبلاغ:</strong> مباحث الإنترنت — الخط الساخن: 108
    واتساب: 0224065052 | moi.gov.eg
  </div>
</body>
</html>
```

### 10.3 Generation

```python
def generate_pdf(case_data: dict) -> bytes:
    template = jinja_env.get_template("complaint_ar.html")
    html_content = template.render(**case_data, font_path=FONT_PATH)
    pdf_bytes = HTML(string=html_content, base_url=str(TEMPLATE_DIR)).write_pdf()
    return pdf_bytes
```

---

## 11. Legal Chatbot

**Service:** `chatbot` | **Port:** 8006 | **Owner:** M2 + M4

### 11.1 Session Architecture

The chatbot is stateless between service restarts but maintains full session context within a conversation. The case context is injected into every API call:

```python
def chat(session_id: str, user_message: str, case_context: dict) -> str:
    history = session_store.get(session_id, [])

    system_prompt = f"""
    You are a certified Egyptian legal advisor specialising in cybercrime.
    You are helping with case: {case_context['case_id']}
    Crime type identified: {case_context['crime_type']}
    Evidence strength: {case_context['score']['total_score']}%

    RULES:
    - Answer ONLY in formal Arabic (العربية الرسمية)
    - Cite article numbers for every legal statement
    - If asked about an article not in the retrieved list below, say it requires
      further consultation — do NOT invent articles
    - Retrieved applicable articles: {json.dumps(case_context['articles'])}
    """

    messages = [{"role": "user" if m["role"]=="user" else "assistant",
                 "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": user_message})

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        system=system_prompt,
        messages=messages,
        max_tokens=1000
    )

    assistant_reply = response.content[0].text
    history.append({"role":"user","content":user_message})
    history.append({"role":"assistant","content":assistant_reply})
    session_store[session_id] = history

    return assistant_reply
```

---

## 12. Data Schema

### 12.1 Unified Case Schema (v1)

```json
{
  "case_id": "CASE_A3F2",
  "created_at": "2024-11-15T14:32:00Z",
  "files_processed": 3,
  "evidence_blocks": [
    {
      "block_id": "E001",
      "file_name": "screenshot_1.png",
      "raw_text": "هبعتلك صورك لو ما بعتيش 5000 جنيه",
      "normalized_text": "هبعتلك صورك لو ما بعتيش 5000 جنيه",
      "confidence": 0.82,
      "quality_flag": "OK",
      "ocr_source": "easyocr"
    }
  ],
  "entities": {
    "phones":   [{"value": "01012345678", "source_block": "E001"}],
    "amounts":  [{"value": "5000 جنيه",   "source_block": "E001"}],
    "dates":    [{"value": "2024-11-14",   "source_block": "E002"}],
    "accounts": [],
    "urls":     []
  },
  "classification": {
    "crime_type":    "blackmail",
    "confidence":    0.92,
    "key_indicators": [
      {"indicator": "هبعتلك صورك", "block_id": "E001", "significance": "Explicit threat to share private images"}
    ],
    "claims": [
      {"claim": "Suspect demanded EGP 5000 under threat of image disclosure",
       "evidence_block_ids": ["E001"], "strength": "strong"}
    ],
    "missing_evidence": ["Bank transfer receipt if payment was made"]
  },
  "articles": [
    {"article_id": "law175_art26", "article_number": "26", "law": "175/2018",
     "text": "المادة 26: ...", "penalty_ar": "حبس 2–5 سنوات", "relevance_score": 0.12}
  ],
  "verification": {
    "status": "APPROVED",
    "rounds": 2,
    "log": [
      {"round": 1, "attacks_found": 1, "verdict": "NEEDS_REVISION"},
      {"round": 2, "attacks_found": 0, "verdict": "APPROVED"}
    ]
  },
  "score": {
    "total_score": 87,
    "grade": "STRONG",
    "breakdown": {
      "explicit_threat_found": 20,
      "financial_demand_found": 20,
      "contact_identified": 15,
      "multiple_evidence_files": 15,
      "ocr_confidence_high": 12,
      "law_articles_retrieved": 10,
      "date_timestamp_found": 0
    }
  },
  "timeline": [
    {"date": "2024-11-14", "block_id": "E002", "event_summary": "First threatening message received"}
  ]
}
```

---

## 13. Infrastructure & DevOps

### 13.1 docker-compose.yml (abbreviated)

```yaml
version: '3.9'
services:
  api:
    build: ./services/api
    ports: ["8000:8000"]
    env_file: .env
    volumes: ["./data:/app/data", "./outputs:/app/outputs"]
    depends_on: [ocr, classifier, rag, verification, pdf_gen, chatbot]

  ocr:
    build: ./services/ocr
    ports: ["8001:8001"]
    volumes: ["./data:/app/data"]

  chromadb:
    image: chromadb/chroma:latest
    ports: ["8007:8000"]
    volumes: ["./data/law_db:/chroma/chroma"]
```

### 13.2 GitHub Actions CI

```yaml
name: CI
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [develop]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --cov=services/ --cov-report=xml

  docker-build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker-compose build
      - run: docker-compose up -d
      - run: sleep 30 && make health
      - run: docker-compose down
```

### 13.3 Branch Protection

| Branch | Protection Rules |
|--------|-----------------|
| `main` | Require 2 approvals · CI must pass · No direct push |
| `develop` | Require 1 approval · CI must pass |

---

## 14. Security & Privacy

### 14.1 Data Handling

- **No persistent storage of victim data** — case files are processed in memory and outputs are auto-deleted after 24 hours
- **No logging of evidence content** — only metadata (file count, processing time) is logged
- **No third-party data sharing** — Google Vision API calls are made with evidence images only, not victim identifiers
- **Secrets management** — all API keys in `.env` (gitignored), never hardcoded

### 14.2 API Security

- Rate limiting: 10 requests/minute per IP on `/analyze`
- File size limit: 10MB per file, 10 files max per request
- File type validation: PNG, JPG, JPEG, PDF only (magic bytes checked, not just extension)
- HTTPS enforced in production (Railway/AWS provides TLS termination)

### 14.3 Legal Compliance

- No real victim data used in development (all synthetic)
- Beta pilot requires written informed consent from participants
- Data protection policy to be drafted before public launch (PDPL Egypt compliance)

---

## 15. Performance Targets

| Metric | Target | Current Status |
|--------|--------|---------------|
| Full pipeline (upload → PDF) | ≤ 90 seconds | TBD |
| OCR + entity extraction | ≤ 15 seconds | TBD |
| LLM classification (cached) | ≤ 10 seconds | TBD |
| RAG retrieval | ≤ 2 seconds | TBD |
| Verification loop (1 round) | ≤ 20 seconds | TBD |
| PDF generation | ≤ 5 seconds | TBD |
| Time to first value (summary) | ≤ 30 seconds | TBD |
| Concurrent requests | 10 simultaneous | TBD |

All benchmarks to be measured and documented at TRL 4 milestone (Week 4–6).

---

*Document maintained by M1 (Team Leader). Last updated: March 2026.  
For questions, open an issue or contact the team leader.*
