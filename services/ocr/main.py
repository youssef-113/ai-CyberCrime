"""OCR Service - Stage 2: OCR & Entity Extraction

Microservice Architecture:
- main.py: FastAPI endpoints and orchestration
- preprocessing.py: Image enhancement for Arabic OCR
- ocr_engine.py: EasyOCR primary + PaddleOCR fallback
- arabic_utils.py: Arabic text normalization
- entities.py: Egyptian-specific entity extraction
- models.py: Pydantic schemas
"""
import time
import tempfile
import os
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import modular components
from models import OCRResponse, EntityCollection, EvidenceBlock
from ocr_engine import get_ocr_engine, OCREngine, OCRConfig
from arabic_utils import normalize_arabic_text, detect_language
from entities import extract_entities, merge_entities, check_threat_indicators

# Initialize FastAPI app
app = FastAPI(
    title="OCR Service",
    description="OCR & Entity Extraction for Cybercrime Evidence",
    version="1.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OCR engine on startup
_ocr_engine: Optional[OCREngine] = None


@app.on_event("startup")
async def startup_event():
    """Initialize OCR engine on service startup"""
    global _ocr_engine
    config = OCRConfig(
        easyocr_langs=['ar', 'en'],
        paddleocr_langs=['ar', 'en'],
        confidence_threshold=0.65,
        use_preprocessing=True,
        target_width=800
    )
    _ocr_engine = get_ocr_engine(config)


class ExtractRequest(BaseModel):
    """Request schema for text extraction"""
    use_preprocessing: bool = True
    use_fallback: bool = True


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ocr",
        "version": "1.1.0",
        "engine_ready": _ocr_engine is not None and _ocr_engine._initialized
    }


@app.post("/extract", response_model=OCRResponse)
async def extract_text(file: UploadFile = File(...)):
    """
    Extract text and entities from uploaded image/PDF/text file
    
    Processing pipeline:
    1. Read and validate file
    2. Preprocess image (grayscale, contrast, resize, threshold)
    3. Run OCR with EasyOCR (primary) + PaddleOCR fallback
    4. Normalize Arabic text
    5. Extract entities (phones, amounts, dates, accounts)
    6. Return structured response
    """
    if _ocr_engine is None:
        raise HTTPException(status_code=503, detail="OCR engine not initialized")
    
    start_time = time.time()
    content = await file.read()
    tmp_path = None
    
    try:
        # Handle text files directly
        if file.filename.endswith('.txt'):
            return await _process_text_file(content, file.filename)
        
        # Process image/PDF
        tmp_path = await _save_temp_file(content, file.filename)
        
        # Run OCR
        ocr_result = _ocr_engine.process_image(
            content,
            file.filename,
            block_id="E001"
        )
        
        # Extract entities from all blocks
        all_entities = []
        for block in ocr_result.blocks:
            block_entities = extract_entities(block.normalized_text, block.block_id)
            all_entities.append(block_entities)
        
        # Merge entities from all blocks
        merged_entities = merge_entities(all_entities)
        
        # Detect language
        lang = detect_language(ocr_result.text)
        
        # Check threat indicators
        threat_analysis = check_threat_indicators(ocr_result.text)
        
        processing_time = (time.time() - start_time) * 1000
        
        return OCRResponse(
            evidence_blocks=ocr_result.blocks,
            entities=merged_entities,
            full_text=ocr_result.text,
            normalized_text=normalize_arabic_text(ocr_result.text),
            avg_confidence=round(ocr_result.confidence, 3),
            language=lang,
            processing_metadata={
                "processing_time_ms": round(processing_time, 2),
                "engine_used": ocr_result.engine,
                "fallback_triggered": ocr_result.fallback_triggered,
                "blocks_count": len(ocr_result.blocks),
                "threat_indicators": threat_analysis["found_keywords"],
                "threat_score": threat_analysis["threat_score"],
                "confidence_score": ocr_result.confidence_score.model_dump() if ocr_result.confidence_score else None
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")
    
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/extract/batch")
async def extract_batch(files: List[UploadFile] = File(...)):
    """
    Batch process multiple files
    
    Returns combined results with merged entities
    """
    if _ocr_engine is None:
        raise HTTPException(status_code=503, detail="OCR engine not initialized")
    
    start_time = time.time()
    
    try:
        all_results = []
        all_entities = []
        full_text_parts = []
        
        for idx, file in enumerate(files):
            content = await file.read()
            block_id = f"E{idx+1:03d}"
            
            # Skip text files in batch (or handle separately)
            if file.filename.endswith('.txt'):
                text = content.decode('utf-8', errors='ignore')
                full_text_parts.append(text)
                continue
            
            # Process image
            ocr_result = _ocr_engine.process_image(content, file.filename, block_id)
            all_results.append(ocr_result)
            full_text_parts.append(ocr_result.text)
            
            # Extract entities
            for block in ocr_result.blocks:
                block_entities = extract_entities(block.normalized_text, block.block_id)
                all_entities.append(block_entities)
        
        # Merge everything
        merged_entities = merge_entities(all_entities) if all_entities else EntityCollection()
        combined_text = " ".join(full_text_parts)
        
        # Calculate average confidence
        if all_results:
            avg_conf = sum(r.confidence for r in all_results) / len(all_results)
        else:
            avg_conf = 1.0  # Text files
        
        # Collect all blocks
        all_blocks = []
        for result in all_results:
            all_blocks.extend(result.blocks)
        
        processing_time = (time.time() - start_time) * 1000
        
        return OCRResponse(
            evidence_blocks=all_blocks,
            entities=merged_entities,
            full_text=combined_text,
            normalized_text=normalize_arabic_text(combined_text),
            avg_confidence=round(avg_conf, 3),
            language=detect_language(combined_text),
            processing_metadata={
                "processing_time_ms": round(processing_time, 2),
                "files_processed": len(files),
                "blocks_count": len(all_blocks),
                "batch_mode": True,
                "fallback_count": sum(1 for r in all_results if r.fallback_triggered),
                "confidence_scores": [r.confidence_score.model_dump() for r in all_results if r.confidence_score]
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")


@app.get("/engines/status")
def get_engines_status():
    """Get status of OCR engines"""
    if _ocr_engine is None:
        return {
            "initialized": False,
            "easyocr": {"available": False, "initialized": False},
            "paddleocr": {"available": False, "initialized": False}
        }
    
    return {
        "initialized": _ocr_engine._initialized,
        "easyocr": {
            "available": _ocr_engine._easyocr_reader is not None,
            "initialized": _ocr_engine._easyocr_reader is not None
        },
        "paddleocr": {
            "available": _ocr_engine._paddleocr_reader is not None,
            "initialized": _ocr_engine._paddleocr_reader is not None
        },
        "config": {
            "confidence_threshold": _ocr_engine.config.confidence_threshold,
            "use_preprocessing": _ocr_engine.config.use_preprocessing,
            "target_width": _ocr_engine.config.target_width
        }
    }


# Helper functions

async def _process_text_file(content: bytes, filename: str) -> OCRResponse:
    """Process plain text file directly"""
    text = content.decode('utf-8', errors='ignore')
    normalized = normalize_arabic_text(text)
    
    # Create single block
    block = EvidenceBlock(
        block_id="E001",
        file_name=filename,
        raw_text=text,
        normalized_text=normalized,
        confidence=1.0,
        quality_flag="OK",
        ocr_source="text_file",
        bbox=None
    )
    
    # Extract entities
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
            "engine_used": "text_file",
            "source": "direct_text"
        }
    )


async def _save_temp_file(content: bytes, filename: str) -> str:
    """Save uploaded content to temporary file"""
    suffix = os.path.splitext(filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        return tmp.name


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
