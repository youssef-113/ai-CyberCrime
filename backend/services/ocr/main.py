"""
OCR Service — FastAPI microservice, port 8001

Endpoints
─────────
GET  /health                     → liveness + engine status
GET  /metrics                    → runtime OCR metrics
GET  /engines/status             → per-engine availability

POST /extract                    → single-file OCR (sync)
POST /extract/batch              → multi-file OCR (sync)

POST /api/v1/ocr/upload          → upload file, enqueue async job
POST /api/v1/ocr/process         → process job immediately (sync alias)
GET  /api/v1/ocr/status/{job_id} → poll Celery job status
GET  /api/v1/ocr/result/{job_id} → retrieve completed result
POST /api/v1/ocr/retry/{job_id}  → re-queue a failed job
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .arabic_utils import detect_language, normalize_arabic_text
from .entities import check_threat_indicators, extract_entities, merge_entities
from .models import EvidenceBlock, EntityCollection, OCRResponse
from .ocr_engine import (
    OCRConfig,
    OCREngine,
    cache_result,
    get_cached_result,
    get_ocr_engine,
)

logger = logging.getLogger("ocr.main")

# ── Environment limits ─────────────────────────────────────────────────────
MAX_FILE_SIZE       = int(os.getenv("MAX_FILE_SIZE_BYTES",    str(10 * 1024 * 1024)))  # 10 MB
MAX_IMAGE_DIMENSION = int(os.getenv("MAX_IMAGE_DIMENSION",    "8000"))
MAX_PDF_PAGES       = int(os.getenv("MAX_PDF_PAGES",          "20"))
OCR_TIMEOUT         = int(os.getenv("OCR_TIMEOUT",            "30"))
OCR_CACHE_ENABLED   = os.getenv("OCR_CACHE_ENABLED", "true").lower() == "true"

# Allowed MIME types / magic bytes
ALLOWED_MIME = {
    "image/png", "image/jpeg", "image/jpg",
    "image/webp", "image/tiff", "application/pdf",
}
MAGIC_BYTES: Dict[bytes, str] = {
    b"\x89PNG":         "image/png",
    b"\xFF\xD8\xFF":    "image/jpeg",
    b"%PDF":            "application/pdf",
    b"RIFF":            "image/webp",   # RIFF....WEBP
    b"II*\x00":         "image/tiff",
    b"MM\x00*":         "image/tiff",
}

# ── FastAPI app ────────────────────────────────────────────────────────────
app = FastAPI(
    title="ACEB OCR Service",
    description="Chandra OCR 2 → PaddleOCR → Groq AI understanding pipeline",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singleton engine ───────────────────────────────────────────────────────
_ocr_engine: Optional[OCREngine] = None


@app.on_event("startup")
async def startup_event() -> None:
    global _ocr_engine
    config = OCRConfig(
        chandra_confidence_threshold=0.85,
        paddle_confidence_threshold=0.80,
        use_preprocessing=True,
        target_width=800,
        use_groq_layer=True,
    )
    _ocr_engine = get_ocr_engine(config)
    logger.info("OCR service started — engine initialised")


# ══════════════════════════════════════════════════════════════════════════════
#  Validation helpers
# ══════════════════════════════════════════════════════════════════════════════

def _validate_magic_bytes(content: bytes) -> str:
    """Return detected MIME type or raise 415 if unrecognised."""
    for magic, mime in MAGIC_BYTES.items():
        if content[:len(magic)] == magic:
            return mime
    raise HTTPException(
        status_code=415,
        detail="Unsupported file type — must be PNG, JPEG, WebP, TIFF, or PDF",
    )


def _validate_file(content: bytes, filename: str) -> str:
    """Full file validation: size, magic bytes, extension."""
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum is {MAX_FILE_SIZE // (1024*1024)} MB",
        )
    if filename.lower().endswith(".txt"):
        return "text/plain"
    return _validate_magic_bytes(content)


# ══════════════════════════════════════════════════════════════════════════════
#  Core OCR processing helper
# ══════════════════════════════════════════════════════════════════════════════

async def _ocr_process(content: bytes, filename: str, block_id: str = "E001") -> OCRResponse:
    """
    Run full OCR pipeline on file bytes.

    1. Validate file
    2. Check Redis cache (hit → return immediately)
    3. Run OCR engine with timeout protection
    4. Extract entities, detect language, check threats
    5. Cache result
    6. Return structured OCRResponse
    """
    if _ocr_engine is None:
        raise HTTPException(status_code=503, detail="OCR engine not initialised")

    mime = _validate_file(content, filename)
    start = time.perf_counter()

    # ── Text files: bypass OCR ────────────────────────────────────────────
    if mime == "text/plain" or filename.lower().endswith(".txt"):
        return _process_text_file(content, filename)

    # ── Cache lookup ──────────────────────────────────────────────────────
    if OCR_CACHE_ENABLED:
        cached = get_cached_result(content)
        if cached:
            logger.info("OCR cache hit: %s", filename)
            return OCRResponse(**cached)

    # ── OCR with timeout ──────────────────────────────────────────────────
    try:
        ocr_result = await asyncio.wait_for(
            asyncio.to_thread(
                _ocr_engine.process_image, content, filename, block_id
            ),
            timeout=OCR_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=408,
            detail=f"OCR timed out after {OCR_TIMEOUT}s",
        )

    # ── Entity extraction ─────────────────────────────────────────────────
    all_entities: List[Any] = []
    for block in ocr_result.blocks:
        all_entities.append(extract_entities(block.normalized_text, block.block_id))
    merged = merge_entities(all_entities) if all_entities else EntityCollection()

    # Merge Groq-extracted entities if available
    groq_ents = getattr(ocr_result, "groq_entities", None)

    lang              = detect_language(ocr_result.text)
    threat_analysis   = check_threat_indicators(ocr_result.text)
    processing_ms     = (time.perf_counter() - start) * 1000

    response = OCRResponse(
        evidence_blocks=ocr_result.blocks,
        entities=merged,
        full_text=ocr_result.text,
        normalized_text=normalize_arabic_text(ocr_result.text),
        avg_confidence=round(ocr_result.confidence, 3),
        language=lang,
        processing_metadata={
            "processing_time_ms":  round(processing_ms, 2),
            "engine_used":         ocr_result.engine,
            "fallback_triggered":  ocr_result.fallback_triggered,
            "blocks_count":        len(ocr_result.blocks),
            "threat_indicators":   threat_analysis["found_keywords"],
            "threat_score":        threat_analysis["threat_score"],
            "confidence_score":    (
                ocr_result.confidence_score.model_dump()
                if ocr_result.confidence_score else None
            ),
            "groq_entities": groq_ents,
        },
    )

    # ── Cache store ───────────────────────────────────────────────────────
    if OCR_CACHE_ENABLED:
        try:
            cache_result(content, response.model_dump())
        except Exception:
            pass  # non-critical

    return response


# ══════════════════════════════════════════════════════════════════════════════
#  Observability endpoints
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health() -> Dict[str, Any]:
    """Liveness + readiness probe — required by every service."""
    engine_ready = _ocr_engine is not None and _ocr_engine._initialized
    engines      = _ocr_engine.get_metrics()["engines"] if engine_ready else {}

    try:
        from services.common.cache import cache
        redis_ok = cache.enabled
    except Exception:
        redis_ok = False

    try:
        from services.common.celery_app import celery_app
        celery_inspect = celery_app.control.inspect(timeout=1)
        active = celery_inspect.active()
        celery_ok = active is not None
    except Exception:
        celery_ok = False

    status = "healthy" if engine_ready else "degraded"

    return {
        "status":       status,
        "service":      "ocr",
        "version":      "2.0.0",
        "engine_ready": engine_ready,
        "engines":      engines,
        "redis":        "connected" if redis_ok else "unavailable",
        "celery":       "connected" if celery_ok else "unavailable",
        "limits": {
            "max_file_size_mb":   MAX_FILE_SIZE // (1024 * 1024),
            "max_image_px":       MAX_IMAGE_DIMENSION,
            "max_pdf_pages":      MAX_PDF_PAGES,
            "ocr_timeout_s":      OCR_TIMEOUT,
        },
    }


@app.get("/metrics")
async def metrics() -> Dict[str, Any]:
    """OCR runtime metrics: latency, confidence, engine usage, error count."""
    if _ocr_engine is None:
        return {"error": "engine not initialised"}
    return _ocr_engine.get_metrics()


@app.get("/engines/status")
async def engines_status() -> Dict[str, Any]:
    """Detailed status of every OCR engine."""
    if _ocr_engine is None:
        return {
            "initialized": False,
            "chandra_ocr2": {"available": False},
            "paddleocr":    {"available": False},
            "groq":         {"available": False},
        }
    m = _ocr_engine.get_metrics()
    return {
        "initialized":  _ocr_engine._initialized,
        "chandra_ocr2": {
            "available": m["engines"]["chandra"],
            "requests":  m["chandra_used"],
        },
        "paddleocr": {
            "available": m["engines"]["paddle"],
            "requests":  m["paddle_used"],
        },
        "groq": {
            "available": m["engines"]["groq"],
            "requests":  m["groq_used"],
        },
        "config": {
            "chandra_threshold": _ocr_engine.config.chandra_confidence_threshold,
            "paddle_threshold":  _ocr_engine.config.paddle_confidence_threshold,
            "preprocessing":     _ocr_engine.config.use_preprocessing,
            "groq_layer":        _ocr_engine.config.use_groq_layer,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Sync OCR endpoints (legacy-compatible)
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/extract", response_model=OCRResponse)
async def extract_text(
    file: UploadFile = File(...),
) -> OCRResponse:
    """Extract text + entities from a single uploaded file (sync)."""
    content = await file.read()
    return await _ocr_process(content, file.filename or "upload")


@app.post("/extract/batch")
async def extract_batch(files: List[UploadFile] = File(...)) -> Dict[str, Any]:
    """Batch-process multiple files (sync, parallel)."""
    if _ocr_engine is None:
        raise HTTPException(status_code=503, detail="OCR engine not initialised")

    MAX_BATCH = int(os.getenv("MAX_BATCH_FILES", "10"))
    if len(files) > MAX_BATCH:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum batch size is {MAX_BATCH}",
        )

    start = time.perf_counter()
    tasks = [
        _ocr_process(await f.read(), f.filename or f"file_{i}")
        for i, f in enumerate(files)
    ]
    results: List[OCRResponse] = await asyncio.gather(*tasks, return_exceptions=True)

    ok_results = [r for r in results if isinstance(r, OCRResponse)]
    errors     = [str(r) for r in results if isinstance(r, Exception)]

    all_blocks: List[EvidenceBlock] = []
    all_entities: List[Any]          = []
    text_parts: List[str]            = []

    for r in ok_results:
        all_blocks.extend(r.evidence_blocks)
        text_parts.append(r.full_text)
        if hasattr(r.entities, "__iter__"):
            all_entities.append(r.entities)

    combined_text = " ".join(text_parts)
    avg_conf = (
        sum(r.avg_confidence for r in ok_results) / len(ok_results)
        if ok_results else 0.0
    )

    return {
        "evidence_blocks":  all_blocks,
        "full_text":        combined_text,
        "normalized_text":  normalize_arabic_text(combined_text),
        "avg_confidence":   round(avg_conf, 3),
        "language":         detect_language(combined_text),
        "processing_metadata": {
            "processing_time_ms": round((time.perf_counter() - start) * 1000, 2),
            "files_processed":    len(ok_results),
            "files_failed":       len(errors),
            "batch_mode":         True,
            "errors":             errors,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Async job endpoints  (POST /api/v1/ocr/*)
# ══════════════════════════════════════════════════════════════════════════════

class JobStatus(BaseModel):
    job_id:  str
    status:  str          # PENDING | STARTED | SUCCESS | FAILURE | RETRY
    message: Optional[str] = None


class JobResult(BaseModel):
    job_id:  str
    status:  str
    result:  Optional[Dict[str, Any]] = None
    error:   Optional[str]            = None


@app.post("/api/v1/ocr/upload", response_model=JobStatus)
async def ocr_upload(file: UploadFile = File(...)) -> JobStatus:
    """
    Upload a file and enqueue an async OCR job via Celery.

    Returns a job_id that can be polled with GET /api/v1/ocr/status/{job_id}.
    """
    content  = await file.read()
    filename = file.filename or "upload"

    # Validate before enqueuing
    _validate_file(content, filename)

    # Persist to temp file so Celery worker can read it
    suffix   = os.path.splitext(filename)[1] or ".bin"
    tmp_path = _save_temp(content, suffix)

    try:
        from .tasks import process_image_async
        task = process_image_async.delay(tmp_path, filename, "E001")
        return JobStatus(job_id=task.id, status="PENDING", message="Job enqueued")
    except Exception as exc:
        os.unlink(tmp_path)
        logger.error("Failed to enqueue OCR job: %s", exc)
        raise HTTPException(status_code=503, detail=f"Could not enqueue job: {exc}")


@app.post("/api/v1/ocr/process", response_model=OCRResponse)
async def ocr_process_sync(file: UploadFile = File(...)) -> OCRResponse:
    """Process a file synchronously (immediate result, no job ID)."""
    content = await file.read()
    return await _ocr_process(content, file.filename or "upload")


@app.get("/api/v1/ocr/status/{job_id}", response_model=JobStatus)
async def ocr_job_status(job_id: str) -> JobStatus:
    """Poll the status of an async OCR job."""
    try:
        from services.common.celery_app import celery_app
        task = celery_app.AsyncResult(job_id)
        return JobStatus(
            job_id=job_id,
            status=task.status,
            message=str(task.info) if task.failed() else None,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Job not found: {exc}")


@app.get("/api/v1/ocr/result/{job_id}", response_model=JobResult)
async def ocr_job_result(job_id: str) -> JobResult:
    """Retrieve the result of a completed OCR job."""
    try:
        from services.common.celery_app import celery_app
        task = celery_app.AsyncResult(job_id)

        if task.status == "SUCCESS":
            return JobResult(job_id=job_id, status="SUCCESS", result=task.result)
        if task.status == "FAILURE":
            return JobResult(job_id=job_id, status="FAILURE", error=str(task.result))
        # Still running
        return JobResult(job_id=job_id, status=task.status)

    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Job not found: {exc}")


@app.post("/api/v1/ocr/retry/{job_id}", response_model=JobStatus)
async def ocr_job_retry(job_id: str) -> JobStatus:
    """
    Re-queue a failed OCR job.

    Looks up the original task arguments from the Celery result backend
    and dispatches a new task.
    """
    try:
        from services.common.celery_app import celery_app
        from .tasks import process_image_async

        old = celery_app.AsyncResult(job_id)
        if old.status not in ("FAILURE", "REVOKED"):
            return JobStatus(
                job_id=job_id,
                status=old.status,
                message="Job is not in a failed state; cannot retry",
            )

        # Re-dispatch using stored kwargs if available
        kwargs = old.kwargs or {}
        new_task = process_image_async.delay(
            kwargs.get("file_path", ""),
            kwargs.get("filename", "unknown"),
            kwargs.get("block_id", "E001"),
        )
        return JobStatus(
            job_id=new_task.id,
            status="PENDING",
            message=f"Retry enqueued (original job_id={job_id})",
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Retry failed: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

def _process_text_file(content: bytes, filename: str) -> OCRResponse:
    """Bypass OCR for plain-text files."""
    text       = content.decode("utf-8", errors="ignore")
    normalized = normalize_arabic_text(text)

    block = EvidenceBlock(
        block_id="E001",
        file_name=filename,
        raw_text=text,
        normalized_text=normalized,
        confidence=1.0,
        quality_flag="OK",
        ocr_source="text_file",
        bbox=None,
    )
    entities = extract_entities(normalized, "E001")
    return OCRResponse(
        evidence_blocks=[block],
        entities=entities,
        full_text=text,
        normalized_text=normalized,
        avg_confidence=1.0,
        language=detect_language(text),
        processing_metadata={
            "processing_time_ms": 0,
            "engine_used":        "text_file",
            "fallback_triggered": False,
            "blocks_count":       1,
        },
    )


def _save_temp(content: bytes, suffix: str) -> str:
    """Write bytes to a temp file and return its path."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        return tmp.name


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
