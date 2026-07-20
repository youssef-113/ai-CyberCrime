from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Any, Dict, List, Optional

from celery import Task

from services.common.celery_app import celery_app

logger = logging.getLogger("ocr.tasks")


class OCRTask(Task):
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error("OCR task FAILED | task_id=%s error=%s", task_id, str(exc))
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
        logger.warning("OCR task RETRY | task_id=%s attempt=%d", task_id, self.request.retries)
        super().on_retry(exc, task_id, args, kwargs, einfo)


def _read_file(file_path: str) -> bytes:
    with open(file_path, "rb") as fh:
        return fh.read()


def _build_response(ocr_text: str, clean_text: str, qwen_data: Optional[Dict] = None) -> Dict[str, Any]:
    from arabic_utils import detect_language

    entities = qwen_data.get("entities", {}) if qwen_data else {}
    timeline = qwen_data.get("timeline", []) if qwen_data else []

    return {
        "document_language": qwen_data.get("document_language", "unknown") if qwen_data else detect_language(clean_text),
        "crime_type": qwen_data.get("crime_type", "") if qwen_data else "",
        "confidence": min(max(float(qwen_data.get("confidence", 0.0)), 0.0), 1.0) if qwen_data else 0.0,
        "summary": qwen_data.get("summary", "") if qwen_data else "",
        "entities": entities,
        "timeline": timeline,
        "raw_text": ocr_text,
        "clean_text": clean_text,
    }


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
) -> Dict[str, Any]:
    from arabic_utils import normalize_arabic_text
    from ocr_engine import get_ocr_engine
    from reasoning import reason_text

    t_start = time.perf_counter()
    content = _read_file(file_path)

    if filename.lower().endswith(".txt"):
        text = content.decode("utf-8", errors="ignore")
        clean = normalize_arabic_text(text)
        qwen_data = reason_text(clean)
        result = _build_response(text, clean, qwen_data)
        result["status"] = "success"
        return result

    try:
        engine = get_ocr_engine()
        ocr_result = engine.extract_text(content, filename)
        raw_text = ocr_result.text
        clean_text = normalize_arabic_text(raw_text)

        qwen_data = None
        if clean_text.strip():
            qwen_data = reason_text(clean_text)

        result = _build_response(raw_text, clean_text, qwen_data)
        result["status"] = "success"

        from chroma_store import store_ocr_result
        from models import OCRResponse

        resp = OCRResponse(**result)
        store_ocr_result(resp, document_id=filename)

        return result

    except Exception as exc:
        logger.error("process_image_async failed: %s", exc)
        try:
            raise self.retry(exc=exc, countdown=10 * (self.request.retries + 1))
        except self.MaxRetriesExceededError:
            return {"status": "error", "error": str(exc), "file": filename}
    finally:
        if os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except OSError:
                pass


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
    file_path: str,
    filename: str,
    max_pages: int = 20,
) -> Dict[str, Any]:
    from arabic_utils import normalize_arabic_text
    from ocr_engine import get_ocr_engine
    from reasoning import reason_text

    t_start = time.perf_counter()
    content = _read_file(file_path)
    engine = get_ocr_engine()

    try:
        from pdf2image import convert_from_bytes
        pages = convert_from_bytes(content, dpi=200)[:max_pages]
        logger.info("PDF: %d pages for %s", len(pages), filename)

        import io
        all_texts: List[str] = []

        for i, page in enumerate(pages):
            buf = io.BytesIO()
            page.save(buf, format="PNG")
            page_bytes = buf.getvalue()
            ocr_result = engine.extract_text(page_bytes, f"{filename}_p{i+1}")
            all_texts.append(ocr_result.text)

        raw_text = "\n".join(all_texts)
        clean_text = normalize_arabic_text(raw_text)
        qwen_data = reason_text(clean_text) if clean_text.strip() else None
        result = _build_response(raw_text, clean_text, qwen_data)
        result["status"] = "success"
        result["pages_processed"] = len(pages)
        return result

    except ImportError:
        logger.warning("pdf2image not installed — treating PDF as single image")
        ocr_result = engine.extract_text(content, filename)
        raw_text = ocr_result.text
        clean_text = normalize_arabic_text(raw_text)
        qwen_data = reason_text(clean_text) if clean_text.strip() else None
        result = _build_response(raw_text, clean_text, qwen_data)
        result["status"] = "success"
        return result

    except Exception as exc:
        logger.error("process_pdf_async failed: %s", exc)
        return {"status": "error", "error": str(exc), "file": filename}
    finally:
        if os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except OSError:
                pass


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
    filenames: List[str],
) -> Dict[str, Any]:
    from arabic_utils import normalize_arabic_text
    from ocr_engine import get_ocr_engine
    from reasoning import reason_text

    if len(file_paths) != len(filenames):
        return {"status": "error", "error": "file_paths and filenames length mismatch"}

    engine = get_ocr_engine()
    results: List[Dict] = []
    errors: List[str] = []

    for path, name in zip(file_paths, filenames):
        try:
            content = _read_file(path)
            ocr_result = engine.extract_text(content, name)
            raw_text = ocr_result.text
            clean_text = normalize_arabic_text(raw_text)
            qwen_data = reason_text(clean_text) if clean_text.strip() else None
            r = _build_response(raw_text, clean_text, qwen_data)
            r["file"] = name
            results.append(r)
        except Exception as exc:
            errors.append({"file": name, "error": str(exc)})
        finally:
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass

    return {
        "status": "success" if not errors else "partial",
        "results": results,
        "errors": errors,
        "total_processed": len(results),
        "total_errors": len(errors),
    }
