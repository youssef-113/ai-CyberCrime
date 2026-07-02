# OCR Service — System Design

## Overview

The OCR Service extracts text and structured entities from uploaded evidence files (screenshots, PDFs, chat logs). It sits at the first stage of the analysis pipeline and is the most computationally intensive component.

**Mount point:** `/ocr`
**Source:** `backend/services/ocr/`

---

## Architecture

```
                ┌──────────────┐
                │  User Upload │
                │  (PNG/JPEG/  │
                │   WebP/TIFF/ │
                │   PDF/TXT)   │
                └──────┬───────┘
                       │
                ┌──────▼───────┐
                │   Validate   │
                │  magic bytes │
                │  MIME, size  │
                │  dimensions  │
                └──────┬───────┘
                       │
                ┌──────▼───────┐
                │  TXT file?   │──yes──→ decode UTF-8, normalize, return
                └──────┬───────┘
                       │ no
                ┌──────▼───────┐
                │ Redis Cache  │──hit──→ return cached OCRResponse
                │  (SHA-256)   │
                └──────┬───────┘
                       │ miss
                ┌──────▼────────────────────────────────┐
                │       3-Tier OCR Pipeline              │
                │                                        │
                │  1. Preprocess (grayscale → CLAHE      │
                │     → denoise → adaptive threshold)     │
                │                                        │
                │  2. Chandra OCR 2 (primary)            │
                │     └─ conf ≥ 0.85 → ACCEPT            │
                │     └─ conf < 0.85 → PaddleOCR         │
                │                                        │
                │  3. PaddleOCR (fallback)               │
                │     └─ conf ≥ 0.80 → ACCEPT            │
                │     └─ conf < 0.80 → Groq layer        │
                │                                        │
                │  4. Groq AI Understanding Layer         │
                │     (entity enhancement, never OCR)     │
                └──────┬────────────────────────────────┘
                       │
                ┌──────▼──────────────┐
                │ Arabic Normalization │
                │ remove diacritics    │
                │ unify alef variants  │
                │ fix ta marbuta       │
                │ OCR noise cleanup    │
                └──────┬──────────────┘
                       │
                ┌──────▼──────────────┐
                │  Entity Extraction   │
                │ phones, amounts,     │
                │ dates, accounts,     │
                │ emails, URLs, IBANs  │
                └──────┬──────────────┘
                       │
                ┌──────▼──────────────┐
                │  Threat Analysis     │
                │ keyword matching     │
                │ threat score (0–1)   │
                └──────┬──────────────┘
                       │
                ┌──────▼──────────────┐
                │  Cache & Return      │
                │  → OCRResponse       │
                └─────────────────────┘
```

---

## Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/ocr/health` | Liveness + engine status | No |
| GET | `/ocr/metrics` | Runtime metrics snapshot | No |
| GET | `/ocr/engines/status` | Per-engine availability | No |
| POST | `/ocr/extract` | Single-file OCR (sync) | No |
| POST | `/ocr/extract/batch` | Multi-file OCR (sync, max 10) | No |
| POST | `/ocr/api/v1/ocr/upload` | Upload + enqueue Celery job | No |
| POST | `/ocr/api/v1/ocr/process` | Sync alias for extract | No |
| GET | `/ocr/api/v1/ocr/status/{job_id}` | Poll Celery job status | No |
| GET | `/ocr/api/v1/ocr/result/{job_id}` | Retrieve completed result | No |
| POST | `/ocr/api/v1/ocr/retry/{job_id}` | Re-queue failed job | No |

---

## 3-Tier OCR Engine

### Tier 1: Chandra OCR 2 (Primary)

- **Role:** Primary OCR reader for Arabic script
- **Confidence threshold:** 0.85 (configurable via `CHANDRA_CONFIDENCE_THRESHOLD`)
- **Languages:** `["ar", "en"]`
- **Behavior:** If weighted-average confidence ≥ 0.85, result is accepted immediately. No fallback invoked.

### Tier 2: PaddleOCR (Fallback)

- **Role:** Fallback when Chandra confidence is low
- **Confidence threshold:** 0.80 (configurable via `PADDLE_CONFIDENCE_THRESHOLD`)
- **Language:** `"ar"`
- **Behavior:** If PaddleOCR confidence ≥ 0.80, result is accepted. Else, proceeds to Groq layer.
- **Flag:** `fallback_triggered = true`

### Tier 3: Groq AI Understanding Layer

- **Role:** NOT an OCR engine — only for understanding/enrichment of low-confidence output
- **Model:** `llama-3.3-70b-versatile` (configurable via `GROQ_MODEL`)
- **Behavior:** Sends best OCR text to Groq for structured entity extraction. If Groq returns a higher confidence estimate, its `full_text` is merged into the result.
- **Prompt injection guard:** Filters patterns like `"ignore previous"`, `"act as"` before sending.

### Confidence Scoring

Weighted-average algorithm:
- Words below `WORD_FILTER_THRESHOLD` (0.30) are filtered out
- Each surviving word weighted by its character length
- Final score: `sum(confidence × length) / sum(length)`
- Status labels: `"high"` (≥ 0.75), `"medium"` (≥ 0.50), `"low"` (< 0.50)

---

## Image Preprocessing

**File:** `preprocessing.py`

Arabic text requires specialized preprocessing because connected characters are sensitive to resolution and noise.

| Step | Method | Purpose |
|------|--------|---------|
| Grayscale | `cv2.COLOR_BGR2GRAY` | Remove color noise |
| Resize | `cv2.resize`, target 800px width | Critical for Arabic connected letters |
| Contrast | CLAHE (clipLimit=2.0, 8×8) | Separate connected characters |
| Denoise | `fastNlMeansDenoising` | Remove sensor noise while preserving edges |
| Threshold | Adaptive Gaussian (block=11, C=2) | Binary image for OCR |
| Deskew | Hough lines → median angle rotation | Correct skewed documents |

---

## Arabic Text Normalization

**File:** `arabic_utils.py`

| Step | Rule |
|------|------|
| Remove diacritics | Strip tashkeel (fatha, kasra, damma, shadda, sukun) |
| Remove tatweel | Strip kashida (elongation character ـ) |
| Unify Alef | أ/إ/آ/ٱ → ا |
| Unify Ta marbuta | ة → ه |
| Unify Alef maqsura | ى → ي |
| OCR confusion | Presentation forms → standard Unicode |
| Number normalization | Arabic-Indic digits → English (٠→0, etc.) |
| Spacing | Collapse multiple whitespace, fix punctuation spacing |
| Noise cleanup | Remove non-printables, isolated symbols |

---

## Entity Extraction

**File:** `entities.py`

| Entity | Pattern | Confidence |
|--------|---------|------------|
| Phone (intl) | `+20`/`0020` + prefix + 8 digits | 0.98 |
| Phone (local) | `0` + prefix + 8 digits | 0.95 |
| Amount (EGP) | Number + `EGP`/`جنيه`/`ج.م` | 0.92 |
| Date (std) | DD/MM/YYYY or DD-MM-YYYY | 0.88 |
| Date (Arabic) | Arabic numeral date | 0.85 |
| Social media | `@mention`, `fb.com/`, `instagram.com/`, etc. | 0.90 |
| Email | Standard RFC pattern | 0.95 |
| URL | `http://` or `www.` | 0.90 |
| IBAN | `EG` + 27 digits | 0.98 |

### Threat Indicator Analysis

Checks for keywords like `هنشر` (publish), `هفضحك` (expose), `تهديد` (threat), etc.
- `threat_score = min(found_keywords / 3, 1.0)`
- `is_threatening = threat_score > 0.3`

---

## Async Processing (Celery)

**File:** `tasks.py`
**Queue:** `ocr`

| Task | Description | Max Retries |
|------|-------------|-------------|
| `process_image_async` | Single image/text file | 3 (exp. backoff) |
| `process_pdf_async` | Multi-page PDF via `pdf2image` | 3 |
| `process_batch_async` | List of files, merged results | 2 |

All tasks:
- Check Redis cache before processing
- Clean up temp files in `finally` block
- Log structured metrics on success/failure
- Use `acks_late=True` for at-least-once delivery

---

## Data Models

### OCRResponse (service output)

```
OCRResponse
├── evidence_blocks: List[EvidenceBlock]
│   ├── block_id, file_name, raw_text, normalized_text
│   ├── confidence, quality_flag, ocr_source, bbox
├── entities: EntityCollection
│   ├── phones, amounts, dates, accounts, emails, urls, ibans
├── full_text: str
├── normalized_text: str
├── avg_confidence: float
├── language: str ("ar" | "en" | "mixed")
└── processing_metadata: dict
    ├── processing_time_ms, engine_used, fallback_triggered
    ├── blocks_count, threat_indicators, threat_score
    └── confidence_score, groq_entities
```

### Key Pydantic Models (`models.py`)

| Model | Fields |
|-------|--------|
| `ExtractedEntity` | type, value, confidence, source_block |
| `EvidenceBlock` | block_id, file_name, raw_text, normalized_text, confidence, quality_flag, ocr_source, bbox |
| `ConfidenceScore` | average, minimum, weighted_average, status, filtered_word_count |
| `OCRResult` | text, confidence, blocks, engine, confidence_score, fallback_triggered, groq_entities |
| `EntityCollection` | phones, amounts, dates, accounts, urls, emails, ibans |

---

## Caching

**Key format:** `ocr:result:{sha256(image_bytes)}`
**TTL:** 3600 seconds (configurable via `OCR_CACHE_TTL`)
**Storage:** Redis (via `services.common.cache`)
**Behavior:** Cache hit returns full `OCRResponse` dict. Cache writes are non-critical (fail silently).

---

## Configuration

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `MAX_FILE_SIZE_BYTES` | 10 MB | Max upload size |
| `MAX_IMAGE_DIMENSION` | 8000 px | Max image dimension |
| `MAX_PDF_PAGES` | 20 | Max PDF pages to OCR |
| `OCR_TIMEOUT` | 30s | Per-image processing timeout |
| `OCR_CACHE_ENABLED` | true | Enable Redis caching |
| `OCR_CACHE_TTL` | 3600 | Cache TTL in seconds |
| `CHANDRA_CONFIDENCE_THRESHOLD` | 0.85 | Chandra OCR min confidence |
| `PADDLE_CONFIDENCE_THRESHOLD` | 0.80 | PaddleOCR min confidence |
| `GROQ_API_KEY` | — | Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq LLM model |
| `GROQ_TIMEOUT` | 20s | Groq request timeout |
| `MAX_BATCH_FILES` | 10 | Max files per batch |
| `CACHE_PREFIX_OCR` | `ocr:` | Redis key prefix |

---

## Engine Startup

The OCR engine is initialized **lazily on first request** (not on app startup) because Starlette does not propagate startup events to mounted sub-applications. The singleton is created in `_ensure_engine()` and reused for all subsequent requests.

```python
_ocr_engine: Optional[OCREngine] = None

def _ensure_engine() -> OCREngine:
    global _ocr_engine
    if _ocr_engine is None:
        config = OCRConfig(...)
        _ocr_engine = get_ocr_engine(config)
    return _ocr_engine
```

---

## Text File Fast-Path

Files with `.txt` extension bypass the entire OCR pipeline:
- Decode as UTF-8
- Run Arabic normalization
- Extract entities directly from text
- Return with `avg_confidence=1.0` and `engine_used="text_file"`

---

## Error Handling

| Scenario | HTTP Status | Behavior |
|----------|-------------|----------|
| Unsupported file type | 415 | Magic byte validation fails |
| File too large | 413 | Size > MAX_FILE_SIZE_BYTES |
| OCR timeout | 408 | Processing > OCR_TIMEOUT seconds |
| Engine not initialized | 503 | Lazy init failure |
| Batch too large | 400 | > MAX_BATCH_FILES |
| Celery enqueue failure | 503 | Broker unavailable |
| Cache unavailable | — | Non-critical, processing continues |

---

## Metrics

Exported at `GET /ocr/metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| total_requests | Counter | Total OCR requests |
| chandra_used | Counter | Chandra OCR 2 accepted results |
| paddle_used | Counter | PaddleOCR accepted results |
| groq_used | Counter | Groq layer invocations |
| errors | Counter | Pipeline errors |
| avg_confidence | Gauge | Running average confidence |
| avg_latency_ms | Gauge | Running average latency |
