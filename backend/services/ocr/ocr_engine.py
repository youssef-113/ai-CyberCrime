"""
OCR Engine — Chandra OCR 2 primary, PaddleOCR fallback, Groq AI understanding layer

Architecture:
  Primary   → Chandra OCR 2  (confidence threshold: 85 %)
  Fallback  → PaddleOCR      (confidence threshold: 80 %)
  Layer 3   → Groq AI        (understanding + entity extraction for low-confidence output)

Key design points:
- All readers initialised once at startup as a singleton
- Weighted-average confidence scoring (longer words = higher weight)
- Low-confidence words filtered before scoring
- Groq is NEVER used as a primary OCR engine — only for understanding/validation
- Full retry + timeout protection
- Structured metrics emitted per request
"""

from __future__ import annotations

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
    from chandra_ocr import ChandraOCR  # type: ignore
    CHANDRA_AVAILABLE = True
except ImportError:
    CHANDRA_AVAILABLE = False
    logger.warning("Chandra OCR 2 not available — will fall back to PaddleOCR")

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

from .arabic_utils import detect_language, normalize_arabic_text
from .models import ConfidenceScore, EvidenceBlock, OCRResult
try:
    from .preprocessing import preprocess_image
except Exception as exc:  # pragma: no cover - dependency guard
    logger.warning("Preprocessing import failed: %s", exc)
    preprocess_image = None

# ── Confidence thresholds ──────────────────────────────────────────────────
CHANDRA_CONFIDENCE_THRESHOLD = 0.85   # below → try PaddleOCR
PADDLE_CONFIDENCE_THRESHOLD  = 0.80   # below → send to Groq layer
WORD_FILTER_THRESHOLD        = 0.30   # drop individual words below this
CONFIDENCE_HIGH              = 0.75
CONFIDENCE_MEDIUM            = 0.50
TARGET_WIDTH                 = 800

# ── Groq configuration ─────────────────────────────────────────────────────
GROQ_API_URL   = os.getenv("GROQ_API_URL",   "https://api.groq.com/openai/v1/chat/completions")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY",   "")
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
    chandra_langs: List[str]  = field(default_factory=lambda: ["ar", "en"])
    # Thresholds
    chandra_confidence_threshold: float = CHANDRA_CONFIDENCE_THRESHOLD
    paddle_confidence_threshold:  float = PADDLE_CONFIDENCE_THRESHOLD
    word_filter_threshold:        float = WORD_FILTER_THRESHOLD
    # Pre-processing
    use_preprocessing: bool = True
    target_width:      int  = TARGET_WIDTH
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

# Prompt-injection guard — patterns that look like instruction overrides
_INJECTION_PATTERNS = [
    "ignore previous", "disregard", "forget instructions",
    "system prompt", "you are now", "act as", "new instructions",
    "pretend you", "roleplay as",
]


def _sanitize_for_groq(text: str) -> str:
    """Strip potential prompt-injection sequences before sending to Groq."""
    lower = text.lower()
    for pattern in _INJECTION_PATTERNS:
        if pattern in lower:
            text = text.replace(pattern, "[FILTERED]")
            logger.warning("Prompt-injection pattern filtered: %s", pattern)
    return text[:4000]   # hard cap


def groq_understand(raw_ocr_text: str) -> Dict[str, Any]:
    """
    Send low-confidence OCR output to Groq for structured understanding.

    Groq is the UNDERSTANDING LAYER only — it never replaces the OCR reader.
    Returns a dict with extracted entities and a confidence estimate.

    Returns empty dict on any failure (caller decides whether to retry).
    """
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
        # Strip potential markdown fences
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
      1. Preprocess image
      2. Chandra OCR 2  → if confidence ≥ 85 %  →  done
      3. PaddleOCR      → if confidence ≥ 80 %  →  done
      4. Groq AI        → understanding + entity extraction
    """

    def __init__(self, config: Optional[OCRConfig] = None):
        self.config          = config or OCRConfig()
        self._chandra        = None
        self._paddle         = None
        self._initialized    = False
        self._scorer         = ConfidenceScorer()

        # Runtime metrics (in-memory; exported via /health or /metrics)
        self.metrics: Dict[str, Any] = {
            "total_requests":    0,
            "chandra_used":      0,
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
        """Load all available OCR readers once at startup."""
        if self._initialized:
            return

        # Chandra OCR 2 (primary)
        if CHANDRA_AVAILABLE:
            try:
                logger.info("Initialising Chandra OCR 2 …")
                self._chandra = ChandraOCR(langs=self.config.chandra_langs)
                logger.info("Chandra OCR 2 ready")
            except Exception as exc:
                logger.error("Chandra OCR 2 init failed: %s", exc)
                self._chandra = None

        # PaddleOCR (fallback)
        if PADDLEOCR_AVAILABLE:
            try:
                logger.info("Initialising PaddleOCR …")
                self._paddle = PaddleOCR(
                    use_angle_cls=True,
                    lang=self.config.paddleocr_lang,
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
        """
        Run the three-tier OCR pipeline on a single image.

        Returns the best OCRResult, enriched with Groq data when triggered.
        """
        if not self._initialized:
            self.initialize()

        t_start = time.perf_counter()
        self.metrics["total_requests"] += 1

        try:
            img = self._prepare_image(image_bytes)

            # ── Tier 1: Chandra OCR 2 ─────────────────────────────────────
            result = self._run_chandra(img, file_name, block_id)

            if result.confidence >= self.config.chandra_confidence_threshold:
                logger.info(
                    "Chandra OCR 2 accepted: conf=%.2f file=%s",
                    result.confidence, file_name,
                )
                self.metrics["chandra_used"] += 1
                return self._finalise(result, t_start)

            logger.info(
                "Chandra conf %.2f < %.2f — trying PaddleOCR",
                result.confidence, self.config.chandra_confidence_threshold,
            )

            # ── Tier 2: PaddleOCR ─────────────────────────────────────────
            paddle_result = self._run_paddle(img, file_name, block_id)

            if paddle_result.confidence >= self.config.paddle_confidence_threshold:
                logger.info(
                    "PaddleOCR accepted: conf=%.2f file=%s",
                    paddle_result.confidence, file_name,
                )
                self.metrics["paddle_used"] += 1
                return self._finalise(paddle_result, t_start)

            logger.info(
                "PaddleOCR conf %.2f < %.2f — sending to Groq layer",
                paddle_result.confidence, self.config.paddle_confidence_threshold,
            )

            # ── Tier 3: Groq understanding layer ──────────────────────────
            best_text = (
                paddle_result.text if paddle_result.confidence > result.confidence
                else result.text
            )
            best_result = (
                paddle_result if paddle_result.confidence > result.confidence
                else result
            )

            if self.config.use_groq_layer:
                groq_data = groq_understand(best_text)
                if groq_data:
                    self.metrics["groq_used"] += 1
                    best_result = self._merge_groq(best_result, groq_data, file_name, block_id)

            best_result.fallback_triggered = True
            self.metrics["paddle_used"] += 1
            return self._finalise(best_result, t_start)

        except Exception as exc:
            self.metrics["errors"] += 1
            logger.exception("OCR pipeline error for %s: %s", file_name, exc)
            return self._empty_result(file_name, block_id, "none")

    def batch_process(
        self,
        images: List[Tuple[bytes, str]],
        base_block_id: str = "E",
    ) -> List[OCRResult]:
        """Process multiple images, reusing the same reader instances."""
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
        """Return a snapshot of runtime metrics."""
        return {
            "total_requests":  self.metrics["total_requests"],
            "chandra_used":    self.metrics["chandra_used"],
            "paddle_used":     self.metrics["paddle_used"],
            "groq_used":       self.metrics["groq_used"],
            "errors":          self.metrics["errors"],
            "avg_confidence":  round(self.metrics["avg_confidence"], 4),
            "avg_latency_ms":  round(self.metrics["avg_latency_ms"], 2),
            "engines": {
                "chandra":  self._chandra is not None,
                "paddle":   self._paddle  is not None,
                "groq":     bool(GROQ_API_KEY),
            },
        }

    # ── Private helpers ────────────────────────────────────────────────────

    def _finalise(self, result: OCRResult, t_start: float) -> OCRResult:
        """Update running metrics and return result."""
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

    # ── Chandra OCR 2 ─────────────────────────────────────────────────────

    def _run_chandra(self, img: np.ndarray, file_name: str, block_id: str) -> OCRResult:
        if self._chandra is None:
            logger.debug("Chandra not available — returning empty result")
            return self._empty_result(file_name, block_id, "chandra_ocr2")

        try:
            raw = self._chandra.read(img)   # returns list of (bbox, text, conf)
        except Exception as exc:
            logger.error("Chandra OCR 2 read failed: %s", exc)
            return self._empty_result(file_name, block_id, "chandra_ocr2")

        return self._parse_results(raw, file_name, block_id, "chandra_ocr2", "C")

    # ── PaddleOCR ─────────────────────────────────────────────────────────

    def _run_paddle(self, img: np.ndarray, file_name: str, block_id: str) -> OCRResult:
        if self._paddle is None:
            return self._empty_result(file_name, block_id, "paddleocr")

            try:
                raw = self._paddle.ocr(img, cls=True)

                logger.info("========== PADDLE RAW ==========")
                logger.info("Raw type: %s", type(raw))
                logger.info("Raw value: %r", raw)
                logger.info("================================")

            except Exception as exc:
                logger.exception("PaddleOCR failed")
                return self._empty_result(file_name, block_id, "paddleocr")
        
        logger.info("Raw length: %d", len(raw) if raw else 0)        
        if not raw or not raw[0]:
            return self._empty_result(file_name, block_id, "paddleocr")

        # Normalise PaddleOCR format → common (bbox, text, conf)
        normalised = []
        for line in raw[0]:
            bbox, (text, conf) = line
            normalised.append((bbox, text, conf))

        result = self._parse_results(normalised, file_name, block_id, "paddleocr", "P")
        result.fallback_triggered = True
        return result

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
        """
        Enrich the OCR result with Groq's structured understanding.

        Groq may return a better full_text and a confidence estimate.
        We only *override* the text if Groq returns a higher confidence.
        """
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

        # Always attach Groq's structured entities in processing metadata
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


# ══════════════════════════════════════════════════════════════════════════════
#  Cache helpers
# ══════════════════════════════════════════════════════════════════════════════

def _ocr_cache_key(image_bytes: bytes) -> str:
    """Deterministic cache key based on image content hash."""
    digest = hashlib.sha256(image_bytes).hexdigest()
    return f"ocr:result:{digest}"


def get_cached_result(image_bytes: bytes) -> Optional[Dict]:
    """Return cached OCR result dict, or None on miss."""
    try:
        from services.common.cache import cache, CACHE_PREFIX_OCR
        key = _ocr_cache_key(image_bytes)
        return cache.get(key)
    except Exception:
        return None


def cache_result(image_bytes: bytes, result_dict: Dict, ttl: int = OCR_CACHE_TTL) -> None:
    """Store OCR result in Redis cache."""
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
    """Return the global OCR engine singleton, initialising on first call."""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = OCREngine(config)
        _ocr_engine.initialize()
    return _ocr_engine


def reset_ocr_engine() -> None:
    """Reset singleton (test/reload use only)."""
    global _ocr_engine
    _ocr_engine = None
