"""Arabic text processing utilities

Handles Arabic-specific text normalization and reshaping:
- Normalize inconsistent characters (ا/أ/إ, ة/ه)
- Remove diacritics (tashkeel)
- Reshape Arabic text for better display
- Handle bidirectional text
"""
import re
import unicodedata
from typing import Optional
try:
    import arabic_reshaper
    ARABIC_RESHAPER_AVAILABLE = True
except ImportError:
    ARABIC_RESHAPER_AVAILABLE = False

try:
    from bidi.algorithm import get_display
    BIDI_AVAILABLE = True
except ImportError:
    BIDI_AVAILABLE = False


# Arabic character mappings for normalization
ALEF_VARIANTS = {
    'أ': 'ا',
    'إ': 'ا', 
    'آ': 'ا',
    'ٱ': 'ا',
}

TA_MARBUTA_VARIANTS = {
    'ة': 'ه',
}

# Common OCR confusion fixes
OCR_CONFUSION_MAP = {
    'ﻭ': 'و',  # Farsi kaf to Arabic waw
    'ﻱ': 'ي',  # Farsi yeh to Arabic yeh
    'ﻻ': 'لا', # Lam-alef ligature
    'ﻼ': 'لا', # Lam-alef ligature
}


def normalize_arabic_text(text: str) -> str:
    """
    Normalize Arabic text for consistent processing
    
    Steps:
    1. Remove diacritics (tashkeel)
    2. Unify Alef variants (أ/إ/آ/ٱ → ا)
    3. Unify Ta marbuta (ة → ه)
    4. Fix common OCR confusions
    5. Normalize whitespace
    
    Args:
        text: Raw Arabic text
        
    Returns:
        Normalized text
    """
    if not text:
        return ""
    
    # Step 1: Remove diacritics (tashkeel)
    text = remove_diacritics(text)
    
    # Step 2: Normalize Alef variants
    for variant, standard in ALEF_VARIANTS.items():
        text = text.replace(variant, standard)
    
    # Step 3: Normalize Ta marbuta
    for variant, standard in TA_MARBUTA_VARIANTS.items():
        text = text.replace(variant, standard)
    
    # Step 4: Fix OCR confusion characters
    for wrong, correct in OCR_CONFUSION_MAP.items():
        text = text.replace(wrong, correct)
    
    # Step 5: Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def remove_diacritics(text: str) -> str:
    """Remove Arabic diacritics (tashkeel/fatha/kasra/damma)"""
    # Arabic diacritics Unicode range: \u064B-\u065F\u0670
    return re.sub(r'[\u064B-\u065F\u0670]', '', text)


def reshape_arabic_text(text: str) -> str:
    """
    Reshape Arabic text for proper display
    
    Uses arabic_reshaper library if available
    """
    if not text or not ARABIC_RESHAPER_AVAILABLE:
        return text
    
    try:
        reshaped = arabic_reshaper.reshape(text)
        return reshaped
    except Exception:
        return text


def prepare_for_display(text: str) -> str:
    """
    Prepare Arabic text for display (reshape + bidi algorithm)
    
    Combines reshaping and bidirectional text handling
    """
    if not text:
        return ""
    
    # Reshape first
    if ARABIC_RESHAPER_AVAILABLE:
        text = reshape_arabic_text(text)
    
    # Apply bidi algorithm
    if BIDI_AVAILABLE:
        try:
            text = get_display(text)
        except Exception:
            pass
    
    return text


def detect_language(text: str) -> str:
    """
    Detect if text is Arabic, English, or mixed
    
    Returns: 'ar', 'en', or 'mixed'
    """
    if not text:
        return "en"
    
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    latin_chars = sum(1 for c in text if c.isascii() and c.isalpha())
    total_chars = arabic_chars + latin_chars
    
    if total_chars == 0:
        return "en"
    
    arabic_ratio = arabic_chars / total_chars
    latin_ratio = latin_chars / total_chars
    
    if arabic_ratio > 0.7:
        return "ar"
    elif latin_ratio > 0.7:
        return "en"
    else:
        return "mixed"


def extract_arabic_words(text: str) -> list:
    """Extract Arabic words from mixed text"""
    arabic_pattern = re.compile(r'[\u0600-\u06FF]+')
    return arabic_pattern.findall(text)


def clean_ocr_noise(text: str) -> str:
    """
    Clean common OCR noise from Arabic text
    
    - Remove isolated punctuation
    - Fix common misrecognitions
    - Remove non-printable characters
    """
    # Remove non-printable characters except Arabic and basic Latin
    text = ''.join(c for c in text if unicodedata.category(c)[0] != 'C' or c in '\n\t')
    
    # Fix common OCR errors
    replacements = {
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
        '|': 'I',  # Common confusion
        'ﷺ': '',   # Remove honorifics (often misrecognized)
    }
    
    for wrong, correct in replacements.items():
        text = text.replace(wrong, correct)
    
    return text


def normalize_for_search(text: str) -> str:
    """
    Aggressive normalization for search/indexing
    
    - All normalizations from normalize_arabic_text
    - Convert to lowercase for Latin text
    - Remove all non-alphanumeric
    """
    text = normalize_arabic_text(text)
    text = text.lower()
    # Keep Arabic, Latin letters, and numbers
    text = re.sub(r'[^\u0600-\u06FFa-z0-9\s]', '', text)
    return text.strip()
