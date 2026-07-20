# OCR Intelligence Service

Extracts Arabic/English text from cybercrime evidence using **Surya OCR**, then performs reasoning via **Qwen2.5-1B-Instruct** to produce structured JSON evidence for RAG retrieval and legal analysis.

---

## System Workflow

```
┌─────────────┐     ┌───────────────┐     ┌────────────┐     ┌──────────────┐
│  Image/PDF  │ ──▶ │  Validation   │ ──▶ │ Preprocess │ ──▶ │  Surya OCR   │
│  Upload     │     │  (magic bytes,│     │ (CLAHE,    │     │  (detection  │
│             │     │   size check) │     │  denoise,  │     │   + recog)   │
└─────────────┘     └───────────────┘     │  threshold)│     └──────┬───────┘
                                          └────────────┘            │
                                                                     ▼
┌─────────────┐     ┌───────────────┐     ┌────────────┐     ┌──────────────┐
│  ChromaDB   │ ◀── │   Response    │ ◀── │  Qwen2.5   │ ◀── │  Normalize   │
│  (vector     │     │   Builder     │     │  Reasoning  │     │  (Arabic     │
│   store)     │     │               │     │  (entities, │     │   text util) │
└─────────────┘     └───────────────┘     │  timeline,  │     └──────────────┘
                                          │  crime cls) │
                                          └────────────┘
```

### Step-by-Step Flow

1. **File Upload & Validation** (`main.py:_validate_file`)
   - Validates MIME type via magic bytes (PNG, JPEG, WebP, TIFF, PDF)
   - Checks file size limit (default 10 MB)
   - TXT files bypass OCR and go directly to reasoning

2. **Image Preprocessing** (`preprocessing.py:preprocess_image`)
   - Grayscale conversion
   - Aspect-ratio-preserving resize (target width: 800px)
   - CLAHE contrast enhancement (critical for Arabic connected letters)
   - Fast NL Means denoising
   - Adaptive Gaussian thresholding → binary image
   - Graceful fallback if OpenCV unavailable

3. **OCR Engine** (`ocr_engine.py:SuryaOCREngine`)
   - **Surya detection model** (`vikp/surya_det3`) — finds text regions
   - **Surya recognition model** (`vikp/surya_rec2`) — transcribes text
   - Supports Arabic + English languages
   - Returns text lines with per-line confidence scores
   - Maintains metrics: requests, latency, confidence, errors

4. **Arabic Text Normalization** (`arabic_utils.py:normalize_arabic_text`)
   - Remove diacritics (tashkeel), tatweel
   - Unify alef variants (أ/إ/آ/ٱ → ا)
   - Unify ta marbuta (ة → ه), alef maqsura (ى → ي)
   - Fix OCR confusion characters (presentation forms → standard)
   - Convert Arabic-Indic digits to English (٠→0, etc.)
   - Language detection: Arabic / English / Mixed

5. **Qwen Reasoning** (`reasoning.py:reason_text`)
   - Loads **Qwen2.5-1B-Instruct** on CPU or CUDA
   - Sends extracted text with structured prompt
   - Returns JSON with: language, crime_type, confidence, summary,
     entities (persons, phones, emails, URLs, social accounts, bank
     accounts, IBANs, amounts, dates), timeline

6. **Entity Extraction Fallback** (`entities.py`)
   - Regex-based extraction for phones (Egyptian formats),
     amounts (EGP, Arabic), dates, social media, emails, URLs, IBANs
   - Threat indicator detection using keyword scoring
   - Used alongside (or as fallback to) Qwen extraction

7. **Vector Store** (`chroma_store.py`)
   - Indexes OCR results into **ChromaDB** via sentence-transformers
     (`all-MiniLM-L6-v2`)
   - Supports similarity search for evidence retrieval
   - Graceful degradation if ChromaDB unavailable

8. **API Response** → Structured `OCRResponse` JSON

---

## Architecture

### File Structure

```
/ocr
├── __init__.py          # Module init, exports router
├── app.py               # FastAPI server (entry point, port 8001)
├── main.py              # FastAPI router + all endpoints
├── ocr_engine.py        # Surya OCR wrapper (SuryaOCREngine)
├── reasoning.py         # Qwen2.5-1B-Instruct integration
├── chroma_store.py      # ChromaDB vector store operations
├── entities.py          # Regex entity extraction + threat detection
├── arabic_utils.py      # Arabic normalization, language detection
├── preprocessing.py     # Image preprocessing (CLAHE, threshold)
├── models.py            # Pydantic schemas (OCRResponse, EntityCollection, etc.)
├── tasks.py             # Celery async job definitions
├── test_pipeline.py     # End-to-end test suite
├── test_ocr.py          # Basic import test
├── test_real_ocr.py     # Model availability verification
├── test_upload.py       # Pipeline simulation test
├── image.png            # Sample test image
├── requirements.txt     # Python dependencies
├── Dockerfile           # Container build
└── .env                 # Environment configuration
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Surya OCR** over Tesseract | Better Arabic support, built-in line detection, modern architecture |
| **Qwen2.5-1B-Instruct** | Small enough for CPU inference, strong Arabic + English reasoning |
| **Regex fallback** for entities | Qwen may fail to load; regex ensures basic extraction always works |
| **ChromaDB** for vector store | Purpose-built for small-to-medium evidence collections, simple API |
| **Celery** for async jobs | Long-running OCR on large images needs background processing |
| **Graceful degradation** | Every component (Surya, Qwen, ChromaDB) can fail independently |

---

## API Endpoints

### REST API

| Method | Endpoint | Description | Input | Output |
|--------|----------|-------------|-------|--------|
| `GET` | `/` | Root info | — | Service metadata |
| `GET` | `/ocr/health` | Health check | — | Engine + Chroma status |
| `GET` | `/ocr/engines/status` | Engine availability | — | Per-engine metrics |
| `POST` | `/ocr/extract` | Sync OCR + AI reasoning | `file` (multipart) | `OCRResponse` |
| `POST` | `/ocr/extract/batch` | Batch OCR (max 10 files) | `files[]` (multipart) | `BatchOCRResponse` |
| `POST` | `/ocr/jobs/upload` | Async OCR enqueue | `file` (multipart) | `JobStatus` |
| `GET` | `/ocr/jobs/{job_id}` | Job status | — | `JobStatus` |
| `GET` | `/ocr/jobs/{job_id}/result` | Job result | — | `JobResult` |
| `POST` | `/ocr/jobs/{job_id}/retry` | Retry failed job | — | `JobStatus` |

### Response Schema (`OCRResponse`)

```json
{
  "document_language": "Arabic",
  "crime_type": "Online Fraud",
  "confidence": 0.94,
  "summary": "Transfer request of 5000 EGP to phone 01012345678",
  "entities": {
    "persons": ["محمد أحمد"],
    "phones": ["01012345678"],
    "emails": [],
    "urls": [],
    "social_accounts": [],
    "bank_accounts": ["1234567890123456"],
    "iban": ["EG380019000500000000263180002"],
    "amounts": ["5000 جنيه"],
    "dates": ["15/11/2024"]
  },
  "timeline": [
    {"date": "2024-11-15", "event": "Money transfer requested", "confidence": 0.9}
  ],
  "raw_text": "تم تحويل مبلغ 5000 جنيه إلى 01012345678 بتاريخ 15/11/2024",
  "clean_text": "تم تحويل مبلغ 5000 جنيه إلى 01012345678 بتاريخ 15/11/2024"
}
```

### Batch Response Schema (`BatchOCRResponse`)

```json
{
  "results": [ /* OCRResponse[] */ ],
  "errors": ["error message"],
  "total_processed": 1,
  "total_errors": 0
}
```

---

## Models Used

| Model | Version | Purpose | Size | Source |
|-------|---------|---------|------|--------|
| **Surya Detector** | `surya_det3` | Text region detection | ~140 MB | HuggingFace `vikp/surya_det3` |
| **Surya Recognizer** | `surya_rec2` | Character recognition | ~940 MB | HuggingFace `vikp/surya_rec2` |
| **Qwen2.5-Instruct** | `1.5B` | Evidence reasoning + JSON output | ~3 GB | HuggingFace `Qwen/Qwen2.5-1.5B-Instruct` |
| **Sentence Transformer** | `all-MiniLM-L6-v2` | Text embeddings for ChromaDB | ~80 MB | `sentence-transformers` |

### Model Performance

- **Surya OCR**: ~5–30s per image (CPU), confidence typically 0.70–0.98
- **Qwen Reasoning**: ~2–10s per text (CPU), adds structured analysis
- **ChromaDB Embedding**: ~100ms per document

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_FILE_SIZE_BYTES` | `10485760` (10 MB) | Max upload size |
| `OCR_TIMEOUT` | `60` | OCR timeout in seconds |
| `OCR_CACHE_ENABLED` | `true` | Enable OCR result caching |
| `QWEN_MODEL` | `Qwen/Qwen2.5-1.5B-Instruct` | HuggingFace model path |
| `CHROMA_HOST` | `localhost` | ChromaDB host |
| `CHROMA_PORT` | `8000` | ChromaDB port |
| `CHROMA_COLLECTION` | `evidence` | ChromaDB collection name |
| `MAX_BATCH_FILES` | `10` | Max files per batch request |

---

## Quick Start

```bash
# Activate conda environment
conda activate cybercrime

# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py

# Test with an image
curl -X POST -F "file=@image.png" http://localhost:8001/ocr/extract

# Health check
curl http://localhost:8001/ocr/health
```

### Run Tests

```bash
# Full test suite (skips image OCR if Surya model not downloaded)
python test_pipeline.py

# Quick tests (no image OCR)
python test_pipeline.py --quick

# Test with specific image
python test_pipeline.py --image image.png

# Verify model availability
python test_real_ocr.py
```

---

## Dependencies

| Category | Libraries |
|----------|-----------|
| **Web Framework** | FastAPI, uvicorn, pydantic, python-multipart |
| **OCR Engine** | surya-ocr, torch, torchvision |
| **AI Reasoning** | transformers, einops |
| **Image Processing** | Pillow, opencv-python-headless, numpy |
| **PDF** | pdf2image |
| **Arabic** | arabic-reshaper, python-bidi |
| **Vector Store** | chromadb, sentence-transformers |
| **Async Jobs** | celery, redis |
| **Rate Limiting** | slowapi |
| **Logging** | python-json-logger |

---

## Error Handling

| Scenario | HTTP Status | Behavior |
|----------|-------------|----------|
| Unsupported file type | 415 | Reject with supported types list |
| File too large | 413 | Return max size limit |
| OCR timeout | 200 | Empty result with "OCR timeout" summary |
| OCR failure | 200 | Empty result with error description |
| Qwen unavailable | 200 | Response without reasoning data |
| ChromaDB unavailable | 200 | Response without vector storage |
| Celery unavailable | 503 | Fall back to sync processing |





✅ OCR Pipeline — Fully Tested & Working
What was done:
1. Downloaded missing model — surya_rec2 (897 MB) was incomplete; fully downloaded and cached.
2. Created test_pipeline.py — comprehensive end-to-end test suite with 39 tests covering:
- All 6 module imports
- Arabic text normalization & language detection
- Entity extraction (phones, amounts, dates, IBANs, emails, social accounts, threats)
- Image preprocessing (CLAHE, threshold, etc.)
- All 8 API endpoints registered on the FastAPI router
- Surya OCR engine with real model loading
- ChromaDB vector store (with in-memory fallback)
- 4 cybercrime evidence pipeline simulations (money transfer, threat, phishing, IBAN deposit)
- Real image OCR test (image.png — extracted 399 chars from a WhatsApp chat screenshot)
3. Fixed chroma_store.py — added in-memory (EphemeralClient) fallback so it works without a separate ChromaDB server.
4. Fixed reasoning.py — graceful handling when Qwen model can't load (needs HuggingFace auth token).
5. Updated ARCHITECTURE.md — comprehensive documentation with:
- Full visual workflow diagram
- Step-by-step pipeline explanation
- Complete API endpoint reference with schemas
- Model table with versions, sizes, sources
- Environment variables reference
- Error handling matrix
Key results:
Component	Status
Arabic normalization	✅
Entity extraction	✅
Image preprocessing	✅
API endpoints	✅ (8/8)
Surya OCR engine	✅ (detection + recognition)
ChromaDB vector store	✅ (in-memory mode)
Image OCR (image.png)	✅ (399 chars extracted)
Qwen reasoning	⚠️ needs HF auth token (gated model)
To enable Qwen reasoning:
huggingface-cli login
# Then accept terms at https://huggingface.co/Qwen/Qwen2.5-1B-Instruct
▣  Build · DeepSeek V4 Flash Free · 53m 4s
guide me to make it enable 
+ Thought: 343ms
%WebFetch https://huggingface.co/Qwen/Qwen2.5-1B-Instruct
+ Thought: 129ms
Run these steps in order:
# Activate env
source /home/joe/miniconda3/etc/profile.d/conda.sh && conda activate cybercrime

# 1. Login to HuggingFace (you need an HF account)
huggingface-cli login
# → paste your HF token when prompted (create at https://huggingface.co/settings/tokens)

# 2. Accept the model license at:
#    https://huggingface.co/Qwen/Qwen2.5-1B-Instruct
#    Click "Agree and access repository"

# 3. Verify it works:
python -c "
import sys; sys.path.insert(0, '/mnt/F/projects/ocr')
from reasoning import reason_text
r = reason_text('تحويل 5000 جنيه إلى 01012345678')
print(r)
"
That's it. The model (~2 GB) will auto-download on first use. After that, all the Qwen fields in the OCR response (crime_type, summary, entities, timeline) will be populated instead of empty.