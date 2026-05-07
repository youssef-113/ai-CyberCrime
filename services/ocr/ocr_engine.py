"""OCR Engine with EasyOCR primary and PaddleOCR fallback

Architecture:
- EasyOCR: Primary engine (initialized once globally, reused)
- PaddleOCR: Fallback if confidence is low (< threshold)

Key optimizations:
- Reader initialized once at startup (singleton)
- Tuned EasyOCR parameters: detail=1, paragraph=True, contrast_ths, adjust_contrast
- Image preprocessing: grayscale → resize(×2) → contrast → threshold
- Confidence scoring: weighted average (longer words = higher weight)
- Low-confidence word filtering
- Exception handling for corrupt images / empty results
- Batch processing support
"""
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
import logging
import time

logger = logging.getLogger(__name__)

# Import OCR libraries with graceful fallback
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    logger.warning("EasyOCR not available")

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    logger.warning("PaddleOCR not available")

from .preprocessing import preprocess_image
from .arabic_utils import normalize_arabic_text, detect_language
from .models import OCRResult, EvidenceBlock, ConfidenceScore


# ─── Confidence Thresholds ─────────────────────────────────────────────
CONFIDENCE_HIGH = 0.7
CONFIDENCE_MEDIUM = 0.5
CONFIDENCE_LOW = 0.5
FALLBACK_THRESHOLD = 0.65
WORD_FILTER_THRESHOLD = 0.3  # Drop words below this confidence
TARGET_WIDTH = 800


@dataclass
class OCRConfig:
    """OCR engine configuration"""
    easyocr_langs: List[str] = field(default_factory=lambda: ['ar', 'en'])
    paddleocr_langs: List[str] = field(default_factory=lambda: ['ar', 'en'])
    confidence_threshold: float = FALLBACK_THRESHOLD
    word_filter_threshold: float = WORD_FILTER_THRESHOLD
    use_preprocessing: bool = True
    target_width: int = TARGET_WIDTH
    # EasyOCR tuned parameters
    easyocr_detail: int = 1
    easyocr_paragraph: bool = True
    easyocr_contrast_ths: float = 0.1
    easyocr_adjust_contrast: float = 0.7
    easyocr_width_ths: float = 0.5
    easyocr_decoder: str = "greedy"


class ConfidenceScorer:
    """
    Confidence scoring system for OCR results

    Scoring strategy:
    - average: simple mean of all word confidences
    - minimum: lowest confidence word (bottleneck detection)
    - weighted_average: longer words get higher weight (more reliable)
    - status: high (>0.7), medium (0.5-0.7), low (<0.5)
    - filtered_word_count: words dropped below filter threshold
    """

    @staticmethod
    def compute_score(
        word_results: List[Tuple[str, float]],
        filter_threshold: float = WORD_FILTER_THRESHOLD
    ) -> ConfidenceScore:
        """
        Compute confidence score from word-level results

        Args:
            word_results: List of (text, confidence) tuples
            filter_threshold: Drop words below this confidence

        Returns:
            ConfidenceScore with average, min, weighted, status
        """
        if not word_results:
            return ConfidenceScore(
                average=0.0,
                minimum=0.0,
                weighted_average=0.0,
                status="low",
                filtered_word_count=0
            )

        confidences = [c for _, c in word_results]
        filtered = [(t, c) for t, c in word_results if c >= filter_threshold]
        filtered_count = len(word_results) - len(filtered)

        # Simple average
        avg = sum(confidences) / len(confidences)

        # Minimum (bottleneck)
        min_conf = min(confidences)

        # Weighted average: longer words → higher weight
        if filtered:
            total_weight = 0.0
            weighted_sum = 0.0
            for text, conf in filtered:
                weight = max(len(text), 1)  # At least weight=1
                weighted_sum += conf * weight
                total_weight += weight
            weighted_avg = weighted_sum / total_weight if total_weight > 0 else 0.0
        else:
            weighted_avg = 0.0

        # Determine status
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
            filtered_word_count=filtered_count
        )

    @staticmethod
    def should_trigger_fallback(score: ConfidenceScore, threshold: float = FALLBACK_THRESHOLD) -> bool:
        """Determine if fallback OCR engine should be used"""
        return score.weighted_average < threshold


class OCREngine:
    """
    OCR Engine with primary/fallback strategy

    - EasyOCR initialized once globally (singleton), reused for all requests
    - Tuned parameters for Arabic text recognition
    - Confidence scoring with weighted average
    - Automatic fallback to PaddleOCR when confidence is low
    - Exception handling for corrupt images and empty results
    """

    def __init__(self, config: Optional[OCRConfig] = None):
        self.config = config or OCRConfig()
        self._easyocr_reader = None
        self._paddleocr_reader = None
        self._initialized = False
        self._scorer = ConfidenceScorer()

    def initialize(self):
        """Initialize OCR readers once at startup"""
        if self._initialized:
            return

        # Initialize EasyOCR (primary)
        if EASYOCR_AVAILABLE:
            try:
                logger.info(f"Initializing EasyOCR with langs={self.config.easyocr_langs}...")
                self._easyocr_reader = easyocr.Reader(
                    self.config.easyocr_langs,
                    gpu=False,
                    verbose=False
                )
                logger.info("EasyOCR initialized successfully (reused globally)")
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")
                self._easyocr_reader = None

        # Initialize PaddleOCR (fallback)
        if PADDLEOCR_AVAILABLE:
            try:
                logger.info("Initializing PaddleOCR...")
                self._paddleocr_reader = PaddleOCR(
                    use_angle_cls=True,
                    lang='ar',
                    show_log=False
                )
                logger.info("PaddleOCR initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize PaddleOCR: {e}")
                self._paddleocr_reader = None

        self._initialized = True

    def process_image(
        self,
        image_bytes: bytes,
        file_name: str,
        block_id: str = "E001"
    ) -> OCRResult:
        """
        Process single image through OCR pipeline

        Flow:
        1. Preprocess image (grayscale, resize ×2, contrast, threshold)
        2. Run EasyOCR with tuned parameters
        3. Compute confidence score (weighted, filtered)
        4. If confidence low → try PaddleOCR fallback
        5. Return best result with confidence details
        """
        if not self._initialized:
            self.initialize()

        # Preprocess image
        img_array = self._prepare_image(image_bytes)

        # Run EasyOCR (primary)
        easyocr_result = self._run_easyocr(img_array, file_name, block_id)

        # Check if fallback is needed
        if easyocr_result.confidence_score and ConfidenceScorer.should_trigger_fallback(
            easyocr_result.confidence_score, self.config.confidence_threshold
        ):
            # Try PaddleOCR as fallback
            if PADDLEOCR_AVAILABLE and self._paddleocr_reader:
                logger.info(
                    f"EasyOCR confidence {easyocr_result.confidence_score.weighted_average:.2f} "
                    f"({easyocr_result.confidence_score.status}) below threshold "
                    f"{self.config.confidence_threshold}, trying PaddleOCR fallback"
                )
                paddle_result = self._run_paddleocr(img_array, file_name, block_id)
                paddle_result.fallback_triggered = True

                # Return the better result
                if paddle_result.confidence > easyocr_result.confidence:
                    return paddle_result

        return easyocr_result

    def _prepare_image(self, image_bytes: bytes) -> np.ndarray:
        """
        Prepare image for OCR: preprocess or handle raw

        Returns numpy array ready for OCR engines
        """
        if self.config.use_preprocessing:
            try:
                return preprocess_image(image_bytes, self.config.target_width)
            except Exception as e:
                logger.warning(f"Preprocessing failed: {e}, using raw image")

        # Fallback: decode raw image without preprocessing
        try:
            import cv2
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                return img
        except Exception:
            pass

        raise ValueError("Failed to decode image — possibly corrupt or unsupported format")

    def _run_easyocr(
        self,
        img_array: np.ndarray,
        file_name: str,
        block_id: str
    ) -> OCRResult:
        """
        Run EasyOCR with tuned parameters on image

        Tuned parameters:
        - detail=1: return bounding boxes
        - paragraph=True: group words into paragraphs
        - contrast_ths: contrast threshold for low-contrast images
        - adjust_contrast: auto-adjust contrast level
        - width_ths: horizontal merging threshold for Arabic connected text
        - decoder: "greedy" for speed
        """
        if not self._easyocr_reader:
            raise RuntimeError("EasyOCR not initialized")

        try:
            results = self._easyocr_reader.readtext(
                img_array,
                detail=self.config.easyocr_detail,
                paragraph=self.config.easyocr_paragraph,
                contrast_ths=self.config.easyocr_contrast_ths,
                adjust_contrast=self.config.easyocr_adjust_contrast,
                width_ths=self.config.easyocr_width_ths,
                decoder=self.config.easyocr_decoder
            )
        except Exception as e:
            logger.error(f"EasyOCR readtext failed: {e}")
            return self._empty_result(file_name, block_id, "easyocr")

        # Handle empty results
        if not results:
            logger.warning(f"EasyOCR returned no results for {file_name}")
            return self._empty_result(file_name, block_id, "easyocr")

        # Parse results into blocks and compute confidence
        blocks = []
        word_results = []  # For confidence scoring
        full_text_parts = []

        for idx, result in enumerate(results):
            bbox, text, conf = result

            # Skip very low confidence words
            if conf < self.config.word_filter_threshold:
                logger.debug(f"Filtering low-conf word: '{text}' ({conf:.2f})")
                continue

            normalized_text = normalize_arabic_text(text)

            block = EvidenceBlock(
                block_id=f"{block_id}_E{idx:03d}" if len(results) > 1 else block_id,
                file_name=file_name,
                raw_text=text,
                normalized_text=normalized_text,
                confidence=round(conf, 4),
                quality_flag=self._quality_flag(conf),
                ocr_source="easyocr",
                bbox=self._flatten_bbox(bbox)
            )
            blocks.append(block)
            full_text_parts.append(normalized_text)
            word_results.append((text, conf))

        # Compute confidence score
        confidence_score = self._scorer.compute_score(
            word_results, self.config.word_filter_threshold
        )

        full_text = " ".join(full_text_parts)
        avg_confidence = confidence_score.weighted_average

        return OCRResult(
            text=full_text,
            confidence=round(avg_confidence, 4),
            blocks=blocks,
            engine="easyocr",
            confidence_score=confidence_score,
            fallback_triggered=False
        )

    def _run_paddleocr(
        self,
        img_array: np.ndarray,
        file_name: str,
        block_id: str
    ) -> OCRResult:
        """Run PaddleOCR on image"""
        if not self._paddleocr_reader:
            raise RuntimeError("PaddleOCR not initialized")

        try:
            result = self._paddleocr_reader.ocr(img_array, cls=True)
        except Exception as e:
            logger.error(f"PaddleOCR failed: {e}")
            return self._empty_result(file_name, block_id, "paddleocr")

        if not result or not result[0]:
            logger.warning(f"PaddleOCR returned no results for {file_name}")
            return self._empty_result(file_name, block_id, "paddleocr")

        blocks = []
        word_results = []
        full_text_parts = []

        for idx, line in enumerate(result[0]):
            bbox, (text, conf) = line

            if conf < self.config.word_filter_threshold:
                continue

            normalized_text = normalize_arabic_text(text)

            block = EvidenceBlock(
                block_id=f"{block_id}_P{idx:03d}" if len(result[0]) > 1 else block_id,
                file_name=file_name,
                raw_text=text,
                normalized_text=normalized_text,
                confidence=round(conf, 4),
                quality_flag=self._quality_flag(conf),
                ocr_source="paddleocr",
                bbox=[bbox[0][0], bbox[0][1], bbox[2][0], bbox[2][1]]
            )
            blocks.append(block)
            full_text_parts.append(normalized_text)
            word_results.append((text, conf))

        confidence_score = self._scorer.compute_score(
            word_results, self.config.word_filter_threshold
        )

        full_text = " ".join(full_text_parts)

        return OCRResult(
            text=full_text,
            confidence=round(confidence_score.weighted_average, 4),
            blocks=blocks,
            engine="paddleocr",
            confidence_score=confidence_score,
            fallback_triggered=True
        )

    def batch_process(
        self,
        images: List[Tuple[bytes, str]],
        base_block_id: str = "E"
    ) -> List[OCRResult]:
        """
        Process multiple images in batch

        Reuses the same Reader instance for all images (no model reloading).

        Args:
            images: List of (image_bytes, file_name) tuples
            base_block_id: Prefix for block IDs

        Returns:
            List of OCRResult objects
        """
        results = []
        for idx, (image_bytes, file_name) in enumerate(images):
            block_id = f"{base_block_id}{idx+1:03d}"
            try:
                result = self.process_image(image_bytes, file_name, block_id)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch item {idx} ({file_name}) failed: {e}")
                results.append(self._empty_result(file_name, block_id, "easyocr"))
        return results

    # ─── Helper Methods ────────────────────────────────────────────────

    @staticmethod
    def _quality_flag(confidence: float) -> str:
        """Map confidence to quality flag"""
        if confidence >= CONFIDENCE_HIGH:
            return "OK"
        elif confidence >= CONFIDENCE_MEDIUM:
            return "LOW_CONFIDENCE"
        else:
            return "FALLBACK_USED"

    @staticmethod
    def _flatten_bbox(bbox) -> Optional[List[float]]:
        """Flatten EasyOCR bbox to [x1, y1, x2, y2]"""
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
        """Return empty OCR result for failed/empty cases"""
        return OCRResult(
            text="",
            confidence=0.0,
            blocks=[],
            engine=engine,
            confidence_score=ConfidenceScore(
                average=0.0,
                minimum=0.0,
                weighted_average=0.0,
                status="low",
                filtered_word_count=0
            ),
            fallback_triggered=False
        )


# ─── Global Singleton ─────────────────────────────────────────────────
_ocr_engine: Optional[OCREngine] = None


def get_ocr_engine(config: Optional[OCRConfig] = None) -> OCREngine:
    """Get or create global OCR engine instance (singleton — Reader loaded once)"""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = OCREngine(config)
        _ocr_engine.initialize()
    return _ocr_engine


def reset_ocr_engine():
    """Reset global OCR engine (for testing)"""
    global _ocr_engine
    _ocr_engine = None
