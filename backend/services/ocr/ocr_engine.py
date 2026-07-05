"""
OCR Engine — Groq Vision API primary, PaddleOCR fallback, Groq understanding layer

Architecture:
  Tier 1  → Groq Vision API   (confidence threshold: 90 %)
  Tier 2  → PaddleOCR         (confidence threshold: 80 %)
  Tier 3  → Groq AI           (understanding + entity extraction as last resort)
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("ocr.engine")

# ── Optional engine imports ────────────────────────────────────────────────

try:
    from paddleocr import PaddleOCR  # type: ignore
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    logger.warning("PaddleOCR not available")

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("httpx not available — Groq layer disabled")

try:
    from groq import Groq
    GROQ_SDK_AVAILABLE = True
except ImportError:
    GROQ_SDK_AVAILABLE = False
    logger.warning("groq SDK not available — Groq Vision disabled")

from .arabic_utils import detect_language, normalize_arabic_text
from .models import ConfidenceScore, EvidenceBlock, OCRResult
try:
    from .preprocessing import preprocess_image
except Exception as exc:  # pragma: no cover - dependency guard
    logger.warning("Preprocessing import failed: %s", exc)
    preprocess_image = None

# ── Groq Vision API configuration ──────────────────────────────────────────
GROQ_VISION_CONFIDENCE  = 0.90
GROQ_API_URL            = os.getenv("GROQ_API_URL",     "https://api.groq.com/openai/v1/chat/completions")
GROQ_API_KEY            = os.getenv("GROQ_API_KEY",     "")
GROQ_VISION_MODEL       = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
GROQ_TIMEOUT            = float(os.getenv("GROQ_TIMEOUT", "30"))

# ── Confidence thresholds ──────────────────────────────────────────────────
PADDLE_CONFIDENCE_THRESHOLD  = 0.80
WORD_FILTER_THRESHOLD        = 0.30
CONFIDENCE_HIGH              = 0.75
CONFIDENCE_MEDIUM            = 0.50
TARGET_WIDTH                 = 800

# ── Groq understanding layer config ────────────────────────────────────────
GROQ_MODEL     = os.getenv("GROQ_MODEL",     "llama-3.3-70b-versatile")
GROQ_TIMEOUT   = float(os.getenv("GROQ_TIMEOUT", "20"))

# ── OCR cache TTL (seconds) ────────────────────────────────────────────────
OCR_CACHE_TTL  = int(os.getenv("OCR_CACHE_TTL", "3600"))


# ══════════════════════════════════════════════════════════════════════════════
#  Config dataclass
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class OCRConfig:
    """Runtime-configurable OCR engine settings"""
    paddleocr_lang: str   = "ar"
    # Thresholds
    groq_vision_confidence_threshold: float = GROQ_VISION_CONFIDENCE
    paddle_confidence_threshold:      float = PADDLE_CONFIDENCE_THRESHOLD
    word_filter_threshold:            float = WORD_FILTER_THRESHOLD
    # Pre-processing
    use_preprocessing: bool = True
    target_width:      int  = TARGET_WIDTH
    # Groq Vision (primary OCR)
    use_groq_vision:          bool = True
    groq_vision_model:        str  = GROQ_VISION_MODEL
    # Groq understanding layer
    use_groq_layer:    bool = True


# ══════════════════════════════════════════════════════════════════════════════
#  Confidence scorer
# ══════════════════════════════════════════════════════════════════════════════

class ConfidenceScorer:
    """Weighted-average confidence scorer for OCR word results."""

    @staticmethod
    def compute(
        word_results: List[Tuple[str, float]],
        filter_threshold: float = WORD_FILTER_THRESHOLD,
    ) -> ConfidenceScore:
        if not word_results:
            return ConfidenceScore(
                average=0.0, minimum=0.0, weighted_average=0.0,
                status="low", filtered_word_count=0,
            )

        confidences   = [c for _, c in word_results]
        filtered      = [(t, c) for t, c in word_results if c >= filter_threshold]
        filtered_count = len(word_results) - len(filtered)

        avg     = sum(confidences) / len(confidences)
        min_conf = min(confidences)

        if filtered:
            total_w = sum(max(len(t), 1) for t, _ in filtered)
            w_sum   = sum(c * max(len(t), 1) for t, c in filtered)
            weighted_avg = w_sum / total_w if total_w else 0.0
        else:
            weighted_avg = 0.0

        if weighted_avg >= CONFIDENCE_HIGH:
            status = "high"
        elif weighted_avg >= CONFIDENCE_MEDIUM:
            status = "medium"
        else:
            status = "low"

        return ConfidenceScore(
            average=round(avg, 4),
            minimum=round(min_conf, 4),
            weighted_average=round(weighted_avg, 4),
            status=status,
            filtered_word_count=filtered_count,
        )


# ══════════════════════════════════════════════════════════════════════════════
#  Groq Understanding Layer
# ══════════════════════════════════════════════════════════════════════════════

_INJECTION_PATTERNS = [
    "ignore previous", "disregard", "forget instructions",
    "system prompt", "you are now", "act as", "new instructions",
    "pretend you", "roleplay as",
]


def _sanitize_for_groq(text: str) -> str:
    lower = text.lower()
    for pattern in _INJECTION_PATTERNS:
        if pattern in lower:
            text = text.replace(pattern, "[FILTERED]")
            logger.warning("Prompt-injection pattern filtered: %s", pattern)
    return text[:4000]


def groq_understand(raw_ocr_text: str) -> Dict[str, Any]:
    if not HTTPX_AVAILABLE or not GROQ_API_KEY:
        logger.warning("Groq layer skipped — httpx or API key unavailable")
        return {}

    sanitized = _sanitize_for_groq(raw_ocr_text)
    if not sanitized.strip():
        return {}

    system_prompt = (
        "You are a cybercrime evidence analysis assistant. "
        "Given raw OCR text from a screenshot or document, extract structured information. "
        "Return ONLY valid JSON — no markdown, no explanation."
    )
    user_prompt = (
        f"Analyze this OCR text and return JSON with these fields:\n"
        f"full_text, crime_type, threat_detected (bool), phone_numbers (list), "
        f"emails (list), urls (list), social_accounts (list), amounts (list), "
        f"dates (list), confidence (0-100 integer).\n\n"
        f"OCR TEXT:\n{sanitized}"
    )

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 1024,
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=GROQ_TIMEOUT) as client:
            resp = client.post(GROQ_API_URL, json=payload, headers=headers)
            resp.raise_for_status()

        raw_json = resp.json()["choices"][0]["message"]["content"].strip()
        if raw_json.startswith("```"):
            raw_json = raw_json.split("```")[1]
            if raw_json.startswith("json"):
                raw_json = raw_json[4:]
        result = json.loads(raw_json)
        logger.info(
            "Groq layer: crime_type=%s threat=%s confidence=%s",
            result.get("crime_type"), result.get("threat_detected"),
            result.get("confidence"),
        )
        return result

    except json.JSONDecodeError as exc:
        logger.error("Groq returned non-JSON: %s", exc)
        return {}
    except Exception as exc:
        logger.error("Groq layer failed: %s", exc)
        return {}


# ══════════════════════════════════════════════════════════════════════════════
#  Main OCR Engine
# ══════════════════════════════════════════════════════════════════════════════

class OCREngine:
    """
    Three-tier OCR engine.

    Flow:
      1. Groq Vision API  → if confidence ≥ 90 %  →  done
      2. PaddleOCR        → if confidence ≥ 80 %  →  done
      3. Groq understanding → entity extraction for any remaining low-confidence output
    """

    def __init__(self, config: Optional[OCRConfig] = None):
        self.config          = config or OCRConfig()
        self._groq_client    = None
        self._paddle         = None
        self._initialized    = False
        self._scorer         = ConfidenceScorer()

        self.metrics: Dict[str, Any] = {
            "total_requests":    0,
            "groq_vision_used":  0,
            "paddle_used":       0,
            "groq_used":         0,
            "errors":            0,
            "avg_confidence":    0.0,
            "avg_latency_ms":    0.0,
            "_conf_sum":         0.0,
            "_latency_sum":      0.0,
        }

    # ── Initialisation ─────────────────────────────────────────────────────

    def initialize(self) -> None:
        if self._initialized:
            return

        if GROQ_SDK_AVAILABLE and GROQ_API_KEY:
            try:
                self._groq_client = Groq(api_key=GROQ_API_KEY)
                logger.info("Groq Vision client ready (model=%s)", self.config.groq_vision_model)
            except Exception as exc:
                logger.error("Groq Vision init failed: %s", exc)
                self._groq_client = None
        else:
            logger.warning("Groq Vision unavailable — groq SDK or API key missing")

        if PADDLEOCR_AVAILABLE:
            try:
                logger.info("Initialising PaddleOCR …")
                self._paddle = PaddleOCR(
                    use_angle_cls=True,
                    lang=self.config.paddleocr_lang,
                    show_log=False,
                )
                logger.info("PaddleOCR ready")
            except Exception as exc:
                logger.error("PaddleOCR init failed: %s", exc)
                self._paddle = None

        self._initialized = True

    # ── Public interface ───────────────────────────────────────────────────

    def process_image(
        self,
        image_bytes: bytes,
        file_name: str,
        block_id: str = "E001",
    ) -> OCRResult:
        if not self._initialized:
            self.initialize()

        t_start = time.perf_counter()
        self.metrics["total_requests"] += 1

        try:
            img = self._prepare_image(image_bytes)

            # ── Tier 1: Groq Vision API ────────────────────────────────────
            groq_vision_result: Optional[OCRResult] = None
            if self.config.use_groq_vision and self._groq_client is not None:
                groq_vision_result = self._run_groq_vision(image_bytes, file_name, block_id)
                if groq_vision_result.confidence >= self.config.groq_vision_confidence_threshold:
                    logger.info("Groq Vision accepted: conf=%.2f file=%s", groq_vision_result.confidence, file_name)
                    self.metrics["groq_vision_used"] += 1
                    return self._finalise(groq_vision_result, t_start)
                logger.info("Groq Vision conf %.2f < %.2f — trying PaddleOCR",
                            groq_vision_result.confidence, self.config.groq_vision_confidence_threshold)

            # ── Tier 2: PaddleOCR ─────────────────────────────────────────
            result = self._run_paddle(img, file_name, block_id)

            if result.confidence >= self.config.paddle_confidence_threshold:
                logger.info("PaddleOCR accepted: conf=%.2f file=%s", result.confidence, file_name)
                self.metrics["paddle_used"] += 1
                return self._finalise(result, t_start)

            logger.info("PaddleOCR conf %.2f < %.2f — sending to Groq understanding layer",
                        result.confidence, self.config.paddle_confidence_threshold)

            # ── Tier 3: Groq understanding layer ──────────────────────────
            # If Groq Vision returned partial text, use it as input instead of empty Paddle result
            best_text = result.text
            if groq_vision_result is not None and len(groq_vision_result.text) > len(result.text):
                best_text = groq_vision_result.text

            if self.config.use_groq_layer:
                groq_data = groq_understand(best_text)
                if groq_data:
                    self.metrics["groq_used"] += 1
                    result = self._merge_groq(result, groq_data, file_name, block_id)
                    # If Groq returned empty text (no OCR content), inject its entities on an empty block
                    if not result.text:
                        result.text = best_text
                        result.blocks = []
                        result.confidence = 0.3

            result.fallback_triggered = True
            self.metrics["paddle_used"] += 1
            return self._finalise(result, t_start)

        except Exception as exc:
            self.metrics["errors"] += 1
            logger.exception("OCR pipeline error for %s: %s", file_name, exc)
            return self._empty_result(file_name, block_id, "none")

    def batch_process(
        self,
        images: List[Tuple[bytes, str]],
        base_block_id: str = "E",
    ) -> List[OCRResult]:
        results = []
        for idx, (image_bytes, file_name) in enumerate(images):
            block_id = f"{base_block_id}{idx + 1:03d}"
            try:
                results.append(self.process_image(image_bytes, file_name, block_id))
            except Exception as exc:
                logger.error("Batch item %d (%s) failed: %s", idx, file_name, exc)
                results.append(self._empty_result(file_name, block_id, "none"))
        return results

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "total_requests":  self.metrics["total_requests"],
            "groq_vision_used": self.metrics["groq_vision_used"],
            "paddle_used":     self.metrics["paddle_used"],
            "groq_used":       self.metrics["groq_used"],
            "errors":          self.metrics["errors"],
            "avg_confidence":  round(self.metrics["avg_confidence"], 4),
            "avg_latency_ms":  round(self.metrics["avg_latency_ms"], 2),
            "engines": {
                "groq_vision": self._groq_client is not None,
                "paddle":      self._paddle  is not None,
                "groq":        bool(GROQ_API_KEY),
            },
        }

    # ── Private helpers ────────────────────────────────────────────────────

    def _finalise(self, result: OCRResult, t_start: float) -> OCRResult:
        latency_ms = (time.perf_counter() - t_start) * 1000
        n = self.metrics["total_requests"]
        self.metrics["_conf_sum"]    += result.confidence
        self.metrics["_latency_sum"] += latency_ms
        self.metrics["avg_confidence"] = self.metrics["_conf_sum"] / n
        self.metrics["avg_latency_ms"] = self.metrics["_latency_sum"] / n
        return result

    def _prepare_image(self, image_bytes: bytes):
        if self.config.use_preprocessing and preprocess_image is not None:
            try:
                return preprocess_image(image_bytes, self.config.target_width)
            except Exception as exc:
                logger.warning("Preprocessing failed (%s) — using raw bytes", exc)

        try:
            import cv2
            nparr = np.frombuffer(image_bytes, np.uint8)
            img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                return img
        except Exception as exc:
            logger.warning("Image decode fallback failed (%s) — returning empty result", exc)

        raise ValueError("Cannot decode image bytes — corrupt or unsupported format")

    # ── Groq Vision API ────────────────────────────────────────────────────

    def _run_groq_vision(self, image_bytes: bytes, file_name: str, block_id: str) -> OCRResult:
        if self._groq_client is None:
            return self._empty_result(file_name, block_id, "groq_vision")

        try:
            b64_image = base64.b64encode(image_bytes).decode("utf-8")
            mime_type = _infer_mime(file_name) or "image/jpeg"

            response = self._groq_client.chat.completions.create(
                model=self.config.groq_vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "You are an OCR engine. Extract ALL visible text from this image exactly as written. "
                                    "Return ONLY the extracted text — no commentary, no formatting, no markdown. "
                                    "Preserve the original language (Arabic, English, or both). "
                                    "If the image contains no readable text, return an empty string."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{b64_image}",
                                },
                            },
                        ],
                    },
                ],
                temperature=0.0,
                max_tokens=4096,
            )

            raw_text = response.choices[0].message.content or ""
            raw_text = raw_text.strip().strip('"\'`')

            if not raw_text:
                return self._empty_result(file_name, block_id, "groq_vision")

            norm = normalize_arabic_text(raw_text)
            block = EvidenceBlock(
                block_id=block_id,
                file_name=file_name,
                raw_text=raw_text,
                normalized_text=norm,
                confidence=0.95,
                quality_flag="OK",
                ocr_source="groq_vision",
                bbox=None,
            )

            return OCRResult(
                text=norm,
                confidence=0.90,
                blocks=[block],
                engine="groq_vision",
                confidence_score=self._scorer.compute([(raw_text, 0.95)], self.config.word_filter_threshold),
                fallback_triggered=False,
            )

        except Exception as exc:
            logger.error("Groq Vision failed for %s: %s", file_name, exc)
            return self._empty_result(file_name, block_id, "groq_vision")

    # ── PaddleOCR ─────────────────────────────────────────────────────────

    def _run_paddle(self, img: np.ndarray, file_name: str, block_id: str) -> OCRResult:
        if self._paddle is None:
            return self._empty_result(file_name, block_id, "paddleocr")

        try:
            raw = self._paddle.ocr(img, cls=True)
        except Exception as exc:
            logger.error("PaddleOCR failed: %s", exc)
            return self._empty_result(file_name, block_id, "paddleocr")

        if not raw or not raw[0]:
            return self._empty_result(file_name, block_id, "paddleocr")

        normalised = []
        for line in raw[0]:
            bbox, (text, conf) = line
            normalised.append((bbox, text, conf))

        return self._parse_results(normalised, file_name, block_id, "paddleocr", "P")

    # ── Shared result parser ───────────────────────────────────────────────

    def _parse_results(
        self,
        raw: List[Tuple],
        file_name: str,
        block_id: str,
        engine: str,
        prefix: str,
    ) -> OCRResult:
        blocks       = []
        word_results = []
        text_parts   = []

        for idx, item in enumerate(raw):
            bbox, text, conf = item

            if conf < self.config.word_filter_threshold:
                continue

            norm = normalize_arabic_text(text)
            bid  = f"{block_id}_{prefix}{idx:03d}" if len(raw) > 1 else block_id

            blocks.append(EvidenceBlock(
                block_id=bid,
                file_name=file_name,
                raw_text=text,
                normalized_text=norm,
                confidence=round(conf, 4),
                quality_flag=self._quality_flag(conf),
                ocr_source=engine,
                bbox=self._flatten_bbox(bbox),
            ))
            text_parts.append(norm)
            word_results.append((text, conf))

        score = self._scorer.compute(word_results, self.config.word_filter_threshold)
        full  = " ".join(text_parts)

        return OCRResult(
            text=full,
            confidence=round(score.weighted_average, 4),
            blocks=blocks,
            engine=engine,
            confidence_score=score,
            fallback_triggered=False,
        )

    # ── Groq merge ────────────────────────────────────────────────────────

    def _merge_groq(
        self,
        result: OCRResult,
        groq_data: Dict[str, Any],
        file_name: str,
        block_id: str,
    ) -> OCRResult:
        groq_conf = groq_data.get("confidence", 0) / 100.0

        if groq_data.get("full_text") and groq_conf > result.confidence:
            better_text = normalize_arabic_text(groq_data["full_text"])
            groq_block  = EvidenceBlock(
                block_id=f"{block_id}_G000",
                file_name=file_name,
                raw_text=groq_data["full_text"],
                normalized_text=better_text,
                confidence=round(groq_conf, 4),
                quality_flag=self._quality_flag(groq_conf),
                ocr_source="groq_understanding",
                bbox=None,
            )
            result.blocks.insert(0, groq_block)
            result.text       = better_text
            result.confidence = round(groq_conf, 4)

        result.groq_entities = {
            "crime_type":      groq_data.get("crime_type"),
            "threat_detected": groq_data.get("threat_detected", False),
            "phone_numbers":   groq_data.get("phone_numbers", []),
            "emails":          groq_data.get("emails", []),
            "urls":            groq_data.get("urls", []),
            "social_accounts": groq_data.get("social_accounts", []),
            "amounts":         groq_data.get("amounts", []),
            "dates":           groq_data.get("dates", []),
        }
        return result

    # ── Static helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _quality_flag(confidence: float) -> str:
        if confidence >= CONFIDENCE_HIGH:
            return "OK"
        if confidence >= CONFIDENCE_MEDIUM:
            return "LOW_CONFIDENCE"
        return "FALLBACK_USED"

    @staticmethod
    def _flatten_bbox(bbox) -> Optional[List[float]]:
        try:
            if bbox and len(bbox) >= 4:
                xs = [p[0] for p in bbox]
                ys = [p[1] for p in bbox]
                return [min(xs), min(ys), max(xs), max(ys)]
        except (TypeError, IndexError):
            pass
        return None

    @staticmethod
    def _empty_result(file_name: str, block_id: str, engine: str) -> OCRResult:
        return OCRResult(
            text="",
            confidence=0.0,
            blocks=[],
            engine=engine,
            confidence_score=ConfidenceScore(
                average=0.0, minimum=0.0, weighted_average=0.0,
                status="low", filtered_word_count=0,
            ),
            fallback_triggered=False,
        )


def _infer_mime(file_name: str) -> Optional[str]:
    ext = (file_name or "").rsplit(".", 1)[-1].lower()
    return {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext)


# ══════════════════════════════════════════════════════════════════════════════
#  Cache helpers
# ══════════════════════════════════════════════════════════════════════════════

def _ocr_cache_key(image_bytes: bytes) -> str:
    digest = hashlib.sha256(image_bytes).hexdigest()
    return f"ocr:result:{digest}"


def get_cached_result(image_bytes: bytes) -> Optional[Dict]:
    try:
        from services.common.cache import cache, CACHE_PREFIX_OCR
        key = _ocr_cache_key(image_bytes)
        return cache.get(key)
    except Exception:
        return None


def cache_result(image_bytes: bytes, result_dict: Dict, ttl: int = OCR_CACHE_TTL) -> None:
    try:
        from services.common.cache import cache, CACHE_PREFIX_OCR
        key = _ocr_cache_key(image_bytes)
        cache.set(key, result_dict, ttl=ttl)
    except Exception as exc:
        logger.debug("OCR cache write failed (non-critical): %s", exc)


# ══════════════════════════════════════════════════════════════════════════════
#  Global singleton
# ══════════════════════════════════════════════════════════════════════════════

_ocr_engine: Optional[OCREngine] = None


def get_ocr_engine(config: Optional[OCRConfig] = None) -> OCREngine:
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = OCREngine(config)
        _ocr_engine.initialize()
    return _ocr_engine


def reset_ocr_engine() -> None:
    global _ocr_engine
    _ocr_engine = None
