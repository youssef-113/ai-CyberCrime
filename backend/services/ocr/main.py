from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from arabic_utils import detect_language, normalize_arabic_text
from chroma_store import health_check as chroma_health, store_ocr_result
from entities import check_threat_indicators, extract_entities, merge_entities
from models import BatchOCRResponse, JobResult, JobStatus, OCRResponse
from ocr_engine import get_ocr_engine, reset_ocr_engine
from reasoning import build_ocr_response, reason_text

logger = logging.getLogger("ocr.main")

MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_BYTES", str(10 * 1024 * 1024)))
MAX_IMAGE_DIMENSION = int(os.getenv("MAX_IMAGE_DIMENSION", "8000"))
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "20"))
OCR_TIMEOUT = int(os.getenv("OCR_TIMEOUT", "60"))
OCR_CACHE_ENABLED = os.getenv("OCR_CACHE_ENABLED", "true").lower() == "true"

ALLOWED_MIME = {
    "image/png", "image/jpeg", "image/jpg",
    "image/webp", "image/tiff", "application/pdf",
}
MAGIC_BYTES: Dict[bytes, str] = {
    b"\x89PNG": "image/png",
    b"\xFF\xD8\xFF": "image/jpeg",
    b"%PDF": "application/pdf",
    b"RIFF": "image/webp",
    b"II*\x00": "image/tiff",
    b"MM\x00*": "image/tiff",
}

router = APIRouter(prefix="/ocr")


def _validate_magic_bytes(content: bytes) -> str:
    for magic, mime in MAGIC_BYTES.items():
        if content[:len(magic)] == magic:
            return mime
    raise HTTPException(
        status_code=415,
        detail="Unsupported file type — must be PNG, JPEG, WebP, TIFF, or PDF",
    )


def _validate_file(content: bytes, filename: str) -> str:
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum is {MAX_FILE_SIZE // (1024 * 1024)} MB",
        )
    if filename.lower().endswith(".txt"):
        return "text/plain"
    return _validate_magic_bytes(content)


async def _ocr_process(content: bytes, filename: str) -> OCRResponse:
    mime = _validate_file(content, filename)

    if filename.lower().endswith(".txt"):
        text = content.decode("utf-8", errors="ignore")
        clean = normalize_arabic_text(text)
        qwen_data = reason_text(clean)
        response = build_ocr_response(text, clean, qwen_data)
        response.document_language = detect_language(text)
        store_ocr_result(response, document_id=filename)
        return response

    engine = get_ocr_engine()
    start = time.perf_counter()

    try:
        ocr_result = await asyncio.wait_for(
            asyncio.to_thread(engine.extract_text, content, filename),
            timeout=OCR_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("OCR timed out for %s", filename)
        return OCRResponse(
            raw_text="", clean_text="",
            confidence=0.0, document_language="unknown",
            crime_type="", summary="OCR timeout",
        )
    except Exception as exc:
        logger.warning("OCR failed for %s: %s", filename, exc)
        return OCRResponse(
            raw_text="", clean_text="",
            confidence=0.0, document_language="unknown",
            crime_type="", summary=f"OCR error: {exc}",
        )

    raw_text = ocr_result.text
    clean_text = normalize_arabic_text(raw_text)
    lang = detect_language(clean_text)

    qwen_data = None
    if clean_text.strip():
        qwen_data = reason_text(clean_text)

    response = build_ocr_response(raw_text, clean_text, qwen_data)
    if response.document_language == "unknown" and lang:
        response.document_language = lang

    store_ocr_result(response, document_id=filename)

    return response


@router.get("/health")
async def health() -> Dict[str, Any]:
    engine = get_ocr_engine()
    engine_metrics = engine.get_metrics()
    ch = chroma_health()

    status = "healthy" if engine_metrics.get("initialized") else "degraded"

    return {
        "status": status,
        "service": "ocr",
        "version": "2.0.0",
        "engine": {
            "initialized": engine_metrics.get("initialized", False),
            "surya_available": engine_metrics.get("surya_available", False),
            "requests": engine_metrics.get("total_requests", 0),
            "errors": engine_metrics.get("errors", 0),
        },
        "chroma": ch,
        "limits": {
            "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
            "ocr_timeout_s": OCR_TIMEOUT,
        },
    }


@router.get("/engines/status")
async def engines_status() -> Dict[str, Any]:
    engine = get_ocr_engine()
    m = engine.get_metrics()
    return {
        "initialized": m.get("initialized", False),
        "surya": {
            "available": m.get("surya_available", False),
            "requests": m.get("total_requests", 0),
            "errors": m.get("errors", 0),
            "avg_confidence": m.get("avg_confidence", 0.0),
            "avg_latency_ms": m.get("avg_latency_ms", 0.0),
        },
        "qwen": {
            "available": True,
        },
        "chroma": chroma_health(),
    }


@router.post("/extract", response_model=OCRResponse)
async def extract_text(file: UploadFile = File(...)) -> OCRResponse:
    content = await file.read()
    return await _ocr_process(content, file.filename or "upload")


@router.post("/extract/batch", response_model=BatchOCRResponse)
async def extract_batch(files: List[UploadFile] = File(...)) -> BatchOCRResponse:
    MAX_BATCH = int(os.getenv("MAX_BATCH_FILES", "10"))
    if len(files) > MAX_BATCH:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum batch size is {MAX_BATCH}",
        )

    tasks = [
        _ocr_process(await f.read(), f.filename or f"file_{i}")
        for i, f in enumerate(files)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    ok_results: List[OCRResponse] = []
    errors: List[str] = []
    for r in results:
        if isinstance(r, OCRResponse):
            ok_results.append(r)
        else:
            errors.append(str(r))

    return BatchOCRResponse(
        results=ok_results,
        errors=errors,
        total_processed=len(ok_results),
        total_errors=len(errors),
    )


@router.post("/jobs/upload", response_model=JobStatus)
async def ocr_upload(file: UploadFile = File(...)) -> JobStatus:
    content = await file.read()
    filename = file.filename or "upload"
    _validate_file(content, filename)

    suffix = os.path.splitext(filename)[1] or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from tasks import process_image_async
        task = process_image_async.delay(tmp_path, filename)
        return JobStatus(job_id=task.id, status="PENDING", message="Job enqueued")
    except Exception as exc:
        os.unlink(tmp_path)
        logger.error("Failed to enqueue OCR job: %s", exc)
        raise HTTPException(status_code=503, detail=f"Could not enqueue job: {exc}")


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def ocr_job_status(job_id: str) -> JobStatus:
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


@router.get("/jobs/{job_id}/result", response_model=JobResult)
async def ocr_job_result(job_id: str) -> JobResult:
    try:
        from services.common.celery_app import celery_app
        task = celery_app.AsyncResult(job_id)

        if task.status == "SUCCESS":
            return JobResult(job_id=job_id, status="SUCCESS", result=task.result)
        if task.status == "FAILURE":
            return JobResult(job_id=job_id, status="FAILURE", error=str(task.result))
        return JobResult(job_id=job_id, status=task.status)

    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Job not found: {exc}")


@router.post("/jobs/{job_id}/retry", response_model=JobStatus)
async def ocr_job_retry(job_id: str) -> JobStatus:
    try:
        from services.common.celery_app import celery_app
        from tasks import process_image_async

        old = celery_app.AsyncResult(job_id)
        if old.status not in ("FAILURE", "REVOKED"):
            return JobStatus(
                job_id=job_id,
                status=old.status,
                message="Job is not in a failed state; cannot retry",
            )

        kwargs = old.kwargs or {}
        new_task = process_image_async.delay(
            kwargs.get("file_path", ""),
            kwargs.get("filename", "unknown"),
        )
        return JobStatus(
            job_id=new_task.id,
            status="PENDING",
            message=f"Retry enqueued (original job_id={job_id})",
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Retry failed: {exc}")


def _save_temp(content: bytes, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        return tmp.name
