"""OCR Service - Stage 2: OCR & Entity Extraction"""
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import easyocr
import re
import tempfile
import os
from PIL import Image
import numpy as np

app = FastAPI(title="OCR Service", version="1.0.0", port=8001)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize EasyOCR reader (English + Arabic)
reader = easyocr.Reader(['en', 'ar'], gpu=False)

class ExtractedEntity(BaseModel):
    type: str
    value: str
    confidence: float

class OCRResponse(BaseModel):
    text: str
    entities: Dict[str, List[ExtractedEntity]]
    confidence: float
    language: str

# Entity extraction patterns
PHONE_PATTERN = r'(\+20|0)?(10|11|12|15)\d{8}'
AMOUNT_PATTERN = r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:EGP|L|E|£|جنية|جنيه)'
DATE_PATTERN = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'
ACCOUNT_PATTERN = r'@[\w_]+'

@app.get("/health")
def health():
    return {"status": "healthy", "service": "ocr", "version": "1.0.0"}

@app.post("/extract", response_model=OCRResponse)
async def extract(file: UploadFile = File(...)):
    """Extract text and entities from image/PDF/text"""

    content = await file.read()
    tmp_path = None

    try:
        # Handle text files directly
        if file.filename.endswith('.txt'):
            full_text = content.decode('utf-8', errors='ignore')
            avg_confidence = 1.0
        else:
            # Save uploaded file temporarily for OCR
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            # Perform OCR
            results = reader.readtext(tmp_path)

            # Extract text
            full_text = " ".join([r[1] for r in results])
            avg_confidence = sum([r[2] for r in results]) / len(results) if results else 0

        # Extract entities
        entities = extract_entities(full_text)

        # Detect language
        lang = "ar" if any('\u0600' <= c <= '\u06FF' for c in full_text) else "en"

        return OCRResponse(
            text=full_text,
            entities=entities,
            confidence=round(avg_confidence, 2),
            language=lang
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

def extract_entities(text: str) -> Dict[str, List[ExtractedEntity]]:
    """Extract structured entities from text"""
    entities = {
        "phones": [],
        "amounts": [],
        "dates": [],
        "accounts": [],
        "emails": []
    }
    
    # Extract phone numbers
    for match in re.finditer(PHONE_PATTERN, text):
        entities["phones"].append(ExtractedEntity(
            type="phone",
            value=match.group(),
            confidence=0.95
        ))
    
    # Extract amounts
    for match in re.finditer(AMOUNT_PATTERN, text, re.IGNORECASE):
        entities["amounts"].append(ExtractedEntity(
            type="amount",
            value=match.group(),
            confidence=0.90
        ))
    
    # Extract dates
    for match in re.finditer(DATE_PATTERN, text):
        entities["dates"].append(ExtractedEntity(
            type="date",
            value=match.group(),
            confidence=0.85
        ))
    
    # Extract social media accounts
    for match in re.finditer(ACCOUNT_PATTERN, text):
        entities["accounts"].append(ExtractedEntity(
            type="account",
            value=match.group(),
            confidence=0.95
        ))
    
    return entities

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
