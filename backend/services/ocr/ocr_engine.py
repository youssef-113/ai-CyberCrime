from __future__ import annotations

import io
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

from arabic_utils import detect_language, normalize_arabic_text
from models import OCRResult

logger = logging.getLogger("ocr.engine")

SURYA_AVAILABLE = False
try:
    from surya.model.detection.model import load_model as load_det_model
    from surya.model.detection.model import load_processor as load_det_processor
    from surya.model.recognition.model import load_model as load_rec_model
    from surya.model.recognition.processor import load_processor as load_rec_processor
    from surya.ocr import run_ocr

    SURYA_AVAILABLE = True
except ImportError as e:
    logger.warning("surya-ocr not fully available: %s", e)

try:
    from preprocessing import preprocess_image
except Exception:
    preprocess_image = None


class SuryaOCREngine:
    def __init__(self):
        self._det_model = None
        self._det_processor = None
        self._rec_model = None
        self._rec_processor = None
        self._initialized = False
        self._metrics: Dict[str, Any] = {
            "total_requests": 0,
            "total_chars": 0,
            "avg_confidence": 0.0,
            "avg_latency_ms": 0.0,
            "errors": 0,
            "_conf_sum": 0.0,
            "_latency_sum": 0.0,
        }

    def initialize(self) -> None:
        if self._initialized:
            return
        if not SURYA_AVAILABLE:
            logger.error("Cannot initialize — surya-ocr not fully available")
            return
        logger.info("Loading Surya OCR models …")
        t0 = time.perf_counter()
        self._det_model = load_det_model()
        self._det_processor = load_det_processor()
        self._rec_model = load_rec_model()
        self._rec_processor = load_rec_processor()
        self._initialized = True
        logger.info("Surya OCR models loaded in %.1fs", time.perf_counter() - t0)

    def extract_text(self, image_bytes: bytes, filename: str = "") -> OCRResult:
        if not self._initialized:
            self.initialize()
        t_start = time.perf_counter()
        self._metrics["total_requests"] += 1

        if not SURYA_AVAILABLE or not self._initialized:
            return OCRResult(text="", confidence=0.0, engine="surya", fallback_triggered=True)

        try:
            image = Image.open(io.BytesIO(image_bytes))
            if image.mode == "RGBA":
                image = image.convert("RGB")

            if preprocess_image is not None:
                processed = preprocess_image(image_bytes, target_width=1200)
                if processed is not None and isinstance(processed, np.ndarray) and processed.size > 1:
                    image = Image.fromarray(processed)

            predictions = run_ocr(
                [image],
                [["ar", "en"]],
                self._det_model,
                self._det_processor,
                self._rec_model,
                self._rec_processor,
            )

            pred = predictions[0]
            text_lines = pred.text_lines

            blocks: List[Dict[str, Any]] = []
            text_parts: list[str] = []
            confs: list[float] = []

            for line in text_lines:
                t = line.text
                c = line.confidence
                if not t:
                    continue
                confs.append(c)
                norm = normalize_arabic_text(t)
                text_parts.append(norm)
                blocks.append({
                    "text": t,
                    "normalized": norm,
                    "confidence": round(c, 4),
                    "bbox": line.bbox,
                })

            full_text = "\n".join(text_parts)
            avg_conf = sum(confs) / len(confs) if confs else 0.0

            latency_ms = (time.perf_counter() - t_start) * 1000
            n = self._metrics["total_requests"]
            self._metrics["_conf_sum"] += avg_conf
            self._metrics["_latency_sum"] += latency_ms
            self._metrics["avg_confidence"] = self._metrics["_conf_sum"] / n
            self._metrics["avg_latency_ms"] = self._metrics["_latency_sum"] / n
            self._metrics["total_chars"] += len(full_text)

            return OCRResult(
                text=full_text,
                confidence=round(avg_conf, 4),
                engine="surya",
                blocks=blocks,
                fallback_triggered=False,
            )

        except Exception as exc:
            self._metrics["errors"] += 1
            logger.exception("Surya OCR failed for %s: %s", filename, exc)
            return OCRResult(text="", confidence=0.0, engine="surya", fallback_triggered=True)

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "total_requests": self._metrics["total_requests"],
            "total_chars": self._metrics["total_chars"],
            "avg_confidence": round(self._metrics["avg_confidence"], 4),
            "avg_latency_ms": round(self._metrics["avg_latency_ms"], 2),
            "errors": self._metrics["errors"],
            "initialized": self._initialized,
            "surya_available": SURYA_AVAILABLE,
        }


_engine: Optional[SuryaOCREngine] = None


def get_ocr_engine() -> SuryaOCREngine:
    global _engine
    if _engine is None:
        _engine = SuryaOCREngine()
        _engine.initialize()
    return _engine


def reset_ocr_engine() -> None:
    global _engine
    _engine = None
