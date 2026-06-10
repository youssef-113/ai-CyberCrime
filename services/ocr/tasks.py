"""Celery tasks for async OCR processing"""
import os
import logging
from typing import Dict, Any
from celery import Task
from services.common.celery_app import celery_app

logger = logging.getLogger("ocr.tasks")


class OCRTask(Task):
    """Base task for OCR operations with error handling"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f"OCR task {task_id} failed: {str(exc)}")
        # Log to database or monitoring system
        super().on_failure(exc, task_id, args, kwargs, einfo)
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        logger.info(f"OCR task {task_id} completed successfully")
        super().on_success(retval, task_id, args, kwargs)


@celery_app.task(
    bind=True,
    base=OCRTask,
    name="services.ocr.tasks.process_image_async",
    max_retries=3,
    default_retry_delay=60
)
def process_image_async(self, file_path: str, filename: str, block_id: str) -> Dict[str, Any]:
    """
    Process image asynchronously with OCR
    
    Args:
        file_path: Path to the image file
        filename: Original filename
        block_id: Block identifier for tracking
    
    Returns:
        OCR result dictionary
    """
    from .ocr_engine import get_ocr_engine, OCRConfig
    from .arabic_utils import normalize_arabic
    from .entities import extract_entities
    import time
    
    try:
        # Initialize OCR engine
        config = OCRConfig(
            easyocr_langs=['ar', 'en'],
            paddleocr_langs=['ar', 'en'],
            confidence_threshold=0.65,
            use_preprocessing=True,
            target_width=800
        )
        ocr_engine = get_ocr_engine(config)
        
        # Read file
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Process OCR
        start_time = time.time()
        ocr_result = ocr_engine.process_image(content, filename, block_id)
        processing_time = time.time() - start_time
        
        # Normalize text
        for block in ocr_result.blocks:
            block.normalized_text = normalize_arabic(block.raw_text)
        
        # Extract entities
        entities = extract_entities(ocr_result.blocks[0].normalized_text, block_id)
        
        return {
            "status": "success",
            "text": ocr_result.blocks[0].normalized_text,
            "entities": entities,
            "confidence": ocr_result.blocks[0].confidence,
            "processing_time": processing_time,
            "block_id": block_id,
        }
        
    except Exception as e:
        logger.error(f"OCR processing failed: {str(e)}")
        raise


@celery_app.task(
    bind=True,
    base=OCRTask,
    name="services.ocr.tasks.process_pdf_async",
    max_retries=3,
    default_retry_delay=60
)
def process_pdf_async(self, file_path: str, filename: str, max_pages: int = 20) -> Dict[str, Any]:
    """
    Process PDF asynchronously with OCR
    
    Args:
        file_path: Path to the PDF file
        filename: Original filename
        max_pages: Maximum number of pages to process
    
    Returns:
        OCR result dictionary with all pages
    """
    from .ocr_engine import get_ocr_engine, OCRConfig
    from .arabic_utils import normalize_arabic
    from .entities import extract_entities, merge_entities
    import time
    
    try:
        # Initialize OCR engine
        config = OCRConfig(
            easyocr_langs=['ar', 'en'],
            paddleocr_langs=['ar', 'en'],
            confidence_threshold=0.65,
            use_preprocessing=True,
            target_width=800
        )
        ocr_engine = get_ocr_engine(config)
        
        # Read file
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Process PDF (simplified - in production use pdf2image)
        start_time = time.time()
        ocr_result = ocr_engine.process_image(content, filename, "PDF001")
        processing_time = time.time() - start_time
        
        # Normalize text
        for block in ocr_result.blocks:
            block.normalized_text = normalize_arabic(block.raw_text)
        
        # Extract entities from all blocks
        all_entities = []
        for block in ocr_result.blocks:
            block_entities = extract_entities(block.normalized_text, block.block_id)
            all_entities.append(block_entities)
        
        # Merge entities
        merged_entities = merge_entities(all_entities)
        
        return {
            "status": "success",
            "text": "\n".join([b.normalized_text for b in ocr_result.blocks]),
            "entities": merged_entities,
            "pages_processed": len(ocr_result.blocks),
            "processing_time": processing_time,
        }
        
    except Exception as e:
        logger.error(f"PDF OCR processing failed: {str(e)}")
        raise
