"""OCR Engine with EasyOCR primary and PaddleOCR fallback

Architecture:
- PaddleOCR: Main engine (better for Arabic)
- EasyOCR: Fallback if confidence is low

Note: Based on requirements, EasyOCR can be primary with PaddleOCR as fallback,
or vice versa. This implementation uses EasyOCR as primary (as per original code)
with PaddleOCR as fallback, but can be easily swapped.
"""
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import logging

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

from preprocessing import preprocess_image
from arabic_utils import normalize_arabic_text, detect_language
from models import OCRResult, EvidenceBlock


# Confidence threshold for fallback
CONFIDENCE_THRESHOLD = 0.65

# Target width for preprocessing (critical for Arabic)
TARGET_WIDTH = 800


@dataclass
class OCRConfig:
    """OCR engine configuration"""
    easyocr_langs: List[str] = None
    paddleocr_langs: List[str] = None
    confidence_threshold: float = 0.65
    use_preprocessing: bool = True
    target_width: int = 800
    
    def __post_init__(self):
        if self.easyocr_langs is None:
            self.easyocr_langs = ['ar', 'en']
        if self.paddleocr_langs is None:
            self.paddleocr_langs = ['ar', 'en']


class OCREngine:
    """
    OCR Engine with primary/fallback strategy
    
    Default: EasyOCR (primary) → PaddleOCR (fallback)
    """
    
    def __init__(self, config: Optional[OCRConfig] = None):
        self.config = config or OCRConfig()
        self._easyocr_reader = None
        self._paddleocr_reader = None
        self._initialized = False
    
    def initialize(self):
        """Initialize OCR readers (call once at startup)"""
        if self._initialized:
            return
        
        # Initialize EasyOCR
        if EASYOCR_AVAILABLE:
            try:
                logger.info("Initializing EasyOCR...")
                self._easyocr_reader = easyocr.Reader(
                    self.config.easyocr_langs,
                    gpu=False,
                    verbose=False
                )
                logger.info("EasyOCR initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")
                self._easyocr_reader = None
        
        # Initialize PaddleOCR
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
        1. Preprocess image (grayscale, contrast, resize, threshold)
        2. Try EasyOCR first
        3. If confidence < threshold, try PaddleOCR
        4. Return best result
        """
        if not self._initialized:
            self.initialize()
        
        # Preprocess image
        if self.config.use_preprocessing:
            try:
                processed_image = preprocess_image(image_bytes, self.config.target_width)
                # Convert back to PIL for EasyOCR
                from PIL import Image
                pil_image = Image.fromarray(processed_image)
            except Exception as e:
                logger.warning(f"Preprocessing failed: {e}, using raw image")
                from PIL import Image
                import io
                pil_image = Image.open(io.BytesIO(image_bytes))
        else:
            from PIL import Image
            import io
            pil_image = Image.open(io.BytesIO(image_bytes))
        
        # Try EasyOCR first (primary)
        easyocr_result = self._run_easyocr(pil_image, file_name, block_id)
        
        # Check if we need fallback
        if easyocr_result.confidence >= self.config.confidence_threshold:
            return easyocr_result
        
        # Try PaddleOCR as fallback
        if PADDLEOCR_AVAILABLE and self._paddleocr_reader:
            logger.info(f"EasyOCR confidence {easyocr_result.confidence:.2f} below threshold, trying PaddleOCR")
            paddle_result = self._run_paddleocr(pil_image, file_name, block_id)
            
            # Return the better result
            if paddle_result.confidence > easyocr_result.confidence:
                return paddle_result
        
        return easyocr_result
    
    def _run_easyocr(
        self,
        image: "PIL.Image",
        file_name: str,
        block_id: str
    ) -> OCRResult:
        """Run EasyOCR on image"""
        if not self._easyocr_reader:
            raise RuntimeError("EasyOCR not initialized")
        
        # Convert PIL to numpy for EasyOCR
        img_array = np.array(image)
        
        # Run OCR
        results = self._easyocr_reader.readtext(img_array, detail=1)
        
        # Parse results
        blocks = []
        full_text_parts = []
        total_confidence = 0.0
        
        for idx, result in enumerate(results):
            bbox, text, conf = result
            
            normalized_text = normalize_arabic_text(text)
            
            block = EvidenceBlock(
                block_id=f"{block_id}_E{idx:03d}" if len(results) > 1 else block_id,
                file_name=file_name,
                raw_text=text,
                normalized_text=normalized_text,
                confidence=round(conf, 3),
                quality_flag="OK" if conf >= 0.7 else "LOW_CONFIDENCE",
                ocr_source="easyocr",
                bbox=bbox[0] + bbox[2] if len(bbox) >= 4 else None
            )
            blocks.append(block)
            full_text_parts.append(normalized_text)
            total_confidence += conf
        
        full_text = " ".join(full_text_parts)
        avg_confidence = total_confidence / len(results) if results else 0.0
        
        return OCRResult(
            text=full_text,
            confidence=round(avg_confidence, 3),
            blocks=blocks,
            engine="easyocr"
        )
    
    def _run_paddleocr(
        self,
        image: "PIL.Image",
        file_name: str,
        block_id: str
    ) -> OCRResult:
        """Run PaddleOCR on image"""
        if not self._paddleocr_reader:
            raise RuntimeError("PaddleOCR not initialized")
        
        # Convert PIL to numpy
        img_array = np.array(image)
        
        # Run OCR
        result = self._paddleocr_reader.ocr(img_array, cls=True)
        
        # Parse results
        blocks = []
        full_text_parts = []
        total_confidence = 0.0
        count = 0
        
        if result and result[0]:
            for idx, line in enumerate(result[0]):
                bbox, (text, conf) = line
                
                normalized_text = normalize_arabic_text(text)
                
                block = EvidenceBlock(
                    block_id=f"{block_id}_P{idx:03d}" if len(result[0]) > 1 else block_id,
                    file_name=file_name,
                    raw_text=text,
                    normalized_text=normalized_text,
                    confidence=round(conf, 3),
                    quality_flag="OK" if conf >= 0.7 else "LOW_CONFIDENCE",
                    ocr_source="paddleocr",
                    bbox=[bbox[0][0], bbox[0][1], bbox[2][0], bbox[2][1]]
                )
                blocks.append(block)
                full_text_parts.append(normalized_text)
                total_confidence += conf
                count += 1
        
        full_text = " ".join(full_text_parts)
        avg_confidence = total_confidence / count if count > 0 else 0.0
        
        return OCRResult(
            text=full_text,
            confidence=round(avg_confidence, 3),
            blocks=blocks,
            engine="paddleocr"
        )
    
    def batch_process(
        self,
        images: List[Tuple[bytes, str]],
        base_block_id: str = "E"
    ) -> List[OCRResult]:
        """
        Process multiple images in batch
        
        Args:
            images: List of (image_bytes, file_name) tuples
            base_block_id: Prefix for block IDs
            
        Returns:
            List of OCRResult objects
        """
        results = []
        for idx, (image_bytes, file_name) in enumerate(images):
            block_id = f"{base_block_id}{idx+1:03d}"
            result = self.process_image(image_bytes, file_name, block_id)
            results.append(result)
        return results


# Global engine instance (singleton pattern)
_ocr_engine: Optional[OCREngine] = None


def get_ocr_engine(config: Optional[OCRConfig] = None) -> OCREngine:
    """Get or create global OCR engine instance"""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = OCREngine(config)
        _ocr_engine.initialize()
    return _ocr_engine


def reset_ocr_engine():
    """Reset global OCR engine (for testing)"""
    global _ocr_engine
    _ocr_engine = None
