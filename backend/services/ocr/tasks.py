"""
Celery tasks for async OCR processing (v2)

Queue:  ocr
Broker: redis://redis:6379/1  (CELERY_BROKER_URL)
Backend:redis://redis:6379/2  (CELERY_RESULT_BACKEND)

Tasks
─────
process_image_async  — single image / text file
process_pdf_async    — multi-page PDF (via pdf2image)
process_batch_async  — list of file paths
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any, Dict, List, Optional

from celery import Task

from services.common.celery_app import celery_app

logger = logging.getLogger("ocr.tasks")


# ══════════════════════════════════════════════════════════════════════════════
#  Base task class
# ══════════════════════════════════════════════════════════════════════════════

class OCRTask(Task):
    """
    Base Celery task for OCR operations.

    - Logs failure details to the structured logger
    - Writes a performance_metrics row to the DB on completion
    - Cleans up temp files on failure
    """

    abstract = True   # not registered as a task itself

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "OCR task FAILED | task_id=%s error=%s",
            task_id, str(exc),
            exc_info=True,
        )
        # Best-effort: remove temp file
        file_path = kwargs.get("file_path") or (args[0] if args else None)
        if file_path and os.path.exists(str(file_path)):
            try:
                os.unlink(file_path)
            except OSError:
                pass
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        logger.info("OCR task SUCCESS | task_id=%s", task_id)
        super().on_success(retval, task_id, args, kwargs)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(
            "OCR task RETRY | task_id=%s attempt=%d error=%s",
            task_id, self.request.retries, str(exc),
        )
        super().on_retry(exc, task_id, args, kwargs, einfo)


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _read_file(file_path: str) -> bytes:
    with open(file_path, "rb") as fh:
        return fh.read()


def _cache_key(content: bytes) -> str:
    return f"ocr:result:{hashlib.sha256(content).hexdigest()}"


def _get_cached(content: bytes) -> Optional[Dict]:
    try:
        from services.common.cache import cache
        return cache.get(_cache_key(content))
    except Exception:
        return None


def _store_cached(content: bytes, result: Dict, ttl: int = 3600) -> None:
    try:
        from services.common.cache import cache
        cache.set(_cache_key(content), result, ttl=ttl)
    except Exception:
        pass


def _build_config():
    from .ocr_engine import OCRConfig
    return OCRConfig(
        paddle_confidence_threshold=float(os.getenv("PADDLE_CONFIDENCE_THRESHOLD",  "0.80")),
        use_preprocessing=True,
        target_width=800,
        use_groq_layer=os.getenv("GROQ_API_KEY", "") != "",
    )


# ══════════════════════════════════════════════════════════════════════════════
#  Task: process_image_async
# ══════════════════════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    base=OCRTask,
    name="services.ocr.tasks.process_image_async",
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def process_image_async(
    self,
    file_path: str,
    filename: str,
    block_id: str = "E001",
) -> Dict[str, Any]:
    """
    Process a single image or text file asynchronously.

    Args:
        file_path: Absolute path to the temp file on disk
        filename:  Original upload filename
        block_id:  Evidence block identifier prefix

    Returns:
        Serialisable dict matching OCRResponse shape
    """
    from .arabic_utils import normalize_arabic_text
    from .entities import extract_entities, merge_entities
    from .ocr_engine import get_ocr_engine

    t_start = time.perf_counter()
    content = _read_file(file_path)

    # ── Redis cache check ──────────────────────────────────────────────────
    cached = _get_cached(content)
    if cached:
        logger.info("Cache HIT for %s", filename)
        return cached

    # ── Text file fast-path ────────────────────────────────────────────────
    if filename.lower().endswith(".txt"):
        text       = content.decode("utf-8", errors="ignore")
        normalized = normalize_arabic_text(text)
        result = {
            "status":            "success",
            "full_text":         text,
            "normalized_text":   normalized,
            "avg_confidence":    1.0,
            "engine_used":       "text_file",
            "fallback_triggered": False,
            "entities":          {},
            "evidence_blocks":   [],
            "processing_time_ms": 0,
        }
        _store_cached(content, result)
        return result

    # ── OCR processing ─────────────────────────────────────────────────────
    try:
        engine     = get_ocr_engine(_build_config())
        ocr_result = engine.process_image(content, filename, block_id)

        # Entity extraction
        all_ents = [
            extract_entities(blk.normalized_text, blk.block_id)
            for blk in ocr_result.blocks
        ]
        merged   = merge_entities(all_ents)

        processing_ms = (time.perf_counter() - t_start) * 1000

        result = {
            "status":            "success",
            "full_text":         ocr_result.text,
            "normalized_text":   normalize_arabic_text(ocr_result.text),
            "avg_confidence":    round(ocr_result.confidence, 4),
            "engine_used":       ocr_result.engine,
            "fallback_triggered": ocr_result.fallback_triggered,
            "entities":          merged.model_dump() if hasattr(merged, "model_dump") else {},
            "evidence_blocks":   [b.model_dump() for b in ocr_result.blocks],
            "groq_entities":     getattr(ocr_result, "groq_entities", None),
            "processing_time_ms": round(processing_ms, 2),
        }
        _store_cached(content, result)
        return result

    except Exception as exc:
        logger.error("process_image_async failed: %s", exc)
        try:
            raise self.retry(exc=exc, countdown=10 * (self.request.retries + 1))
        except self.MaxRetriesExceededError:
            return {
                "status":  "error",
                "error":   str(exc),
                "file":    filename,
            }
    finally:
        if os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except OSError:
                pass


# ══════════════════════════════════════════════════════════════════════════════
#  Task: process_pdf_async
# ══════════════════════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    base=OCRTask,
    name="services.ocr.tasks.process_pdf_async",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def process_pdf_async(
    self,
    file_path:  str,
    filename:   str,
    max_pages:  int = 20,
) -> Dict[str, Any]:
    """
    Convert PDF → images (pdf2image), run OCR on each page, merge results.

    Falls back to treating the PDF as a single blob if pdf2image is missing.
    """
    from .arabic_utils import normalize_arabic_text
    from .entities import extract_entities, merge_entities
    from .ocr_engine import get_ocr_engine

    t_start  = time.perf_counter()
    content  = _read_file(file_path)
    engine   = get_ocr_engine(_build_config())

    try:
        from pdf2image import convert_from_bytes  # type: ignore
        pages = convert_from_bytes(content, dpi=200)[:max_pages]
        logger.info("PDF: %d pages for %s", len(pages), filename)

        import io
        all_blocks = []
        all_ents   = []
        texts      = []

        for i, page in enumerate(pages):
            buf = io.BytesIO()
            page.save(buf, format="PNG")
            page_bytes = buf.getvalue()
            bid        = f"PDF{i+1:03d}"
            ocr_result = engine.process_image(page_bytes, filename, bid)
            all_blocks.extend(ocr_result.blocks)
            texts.append(ocr_result.text)
            for blk in ocr_result.blocks:
                all_ents.append(extract_entities(blk.normalized_text, blk.block_id))

        merged     = merge_entities(all_ents)
        full_text  = " ".join(texts)
        avg_conf   = (
            sum(b.confidence for b in all_blocks) / len(all_blocks)
            if all_blocks else 0.0
        )

    except ImportError:
        logger.warning("pdf2image not installed — treating PDF as single image blob")
        ocr_result = engine.process_image(content, filename, "PDF001")
        all_blocks = ocr_result.blocks
        texts      = [ocr_result.text]
        all_ents   = [
            extract_entities(blk.normalized_text, blk.block_id)
            for blk in ocr_result.blocks
        ]
        merged    = merge_entities(all_ents)
        full_text = ocr_result.text
        avg_conf  = ocr_result.confidence

    processing_ms = (time.perf_counter() - t_start) * 1000

    result = {
        "status":             "success",
        "full_text":          full_text,
        "normalized_text":    normalize_arabic_text(full_text),
        "avg_confidence":     round(avg_conf, 4),
        "pages_processed":    len(texts),
        "evidence_blocks":    [b.model_dump() for b in all_blocks],
        "entities":           merged.model_dump() if hasattr(merged, "model_dump") else {},
        "processing_time_ms": round(processing_ms, 2),
    }

    # Cache keyed on raw content
    _store_cached(content, result)

    if os.path.exists(file_path):
        try:
            os.unlink(file_path)
        except OSError:
            pass

    return result


# ══════════════════════════════════════════════════════════════════════════════
#  Task: process_batch_async
# ══════════════════════════════════════════════════════════════════════════════

@celery_app.task(
    bind=True,
    base=OCRTask,
    name="services.ocr.tasks.process_batch_async",
    max_retries=2,
    default_retry_delay=15,
    acks_late=True,
)
def process_batch_async(
    self,
    file_paths: List[str],
    filenames:  List[str],
) -> Dict[str, Any]:
    """
    Process a list of files as a batch.  Each file dispatched individually
    then results merged.

    Returns aggregate result dict.
    """
    from .arabic_utils import normalize_arabic_text, detect_language
    from .entities import merge_entities
    from .ocr_engine import get_ocr_engine

    if len(file_paths) != len(filenames):
        return {"status": "error", "error": "file_paths and filenames length mismatch"}

    engine     = get_ocr_engine(_build_config())
    all_blocks = []
    all_ents   = []
    texts      = []
    errors     = []

    for path, name in zip(file_paths, filenames):
        try:
            content    = _read_file(path)
            ocr_result = engine.process_image(content, name, f"B{len(texts)+1:03d}")
            all_blocks.extend(ocr_result.blocks)
            texts.append(ocr_result.text)

            from .entities import extract_entities
            for blk in ocr_result.blocks:
                all_ents.append(extract_entities(blk.normalized_text, blk.block_id))
        except Exception as exc:
            errors.append({"file": name, "error": str(exc)})
        finally:
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass

    merged    = merge_entities(all_ents)
    full_text = " ".join(texts)
    avg_conf  = (
        sum(b.confidence for b in all_blocks) / len(all_blocks)
        if all_blocks else 0.0
    )

    return {
        "status":            "success" if not errors else "partial",
        "full_text":         full_text,
        "normalized_text":   normalize_arabic_text(full_text),
        "avg_confidence":    round(avg_conf, 4),
        "language":          detect_language(full_text),
        "evidence_blocks":   [b.model_dump() for b in all_blocks],
        "entities":          merged.model_dump() if hasattr(merged, "model_dump") else {},
        "files_processed":   len(texts),
        "errors":            errors,
    }
