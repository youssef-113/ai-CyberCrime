"""Arabic text processing utilities

Handles Arabic-specific text normalization and reshaping:
- Normalize inconsistent characters (ا/أ/إ, ة/ه, ى/ي)
- Remove diacritics (tashkeel)
- Remove tatweel (ـ)
- Normalize Arabic ↔ English numbers
- Fix spacing issues
- Standardize phone formats
- Reshape Arabic text for display
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


# ─── Character Normalization Maps ──────────────────────────────────────

ALEF_VARIANTS = {
    'أ': 'ا',
    'إ': 'ا',
    'آ': 'ا',
    'ٱ': 'ا',
}

TA_MARBUTA_VARIANTS = {
    'ة': 'ه',
}

ALEF_MAQSURA_VARIANTS = {
    'ى': 'ي',
}

# Common OCR confusion fixes
OCR_CONFUSION_MAP = {
    'ﻭ': 'و',   # Presentation form → standard waw
    'ﻱ': 'ي',   # Presentation form → standard yeh
    'ﻻ': 'لا',  # Lam-alef ligature
    'ﻼ': 'لا',  # Lam-alef ligature
}

# Arabic numeral → English digit mapping
ARABIC_TO_ENGLISH_NUMS = {
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
    '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
}

# English digit → Arabic numeral mapping
ENGLISH_TO_ARABIC_NUMS = {v: k for k, v in ARABIC_TO_ENGLISH_NUMS.items()}


def normalize_arabic_text(text: str) -> str:
    """
    Full Arabic text normalization pipeline

    Steps:
    1. Remove diacritics (tashkeel/fatha/kasra/damma)
    2. Remove tatweel (ـ)
    3. Unify Alef variants (أ/إ/آ/ٱ → ا)
    4. Unify Ta marbuta (ة → ه)
    5. Unify Alef maqsura (ى → ي)
    6. Fix common OCR confusions
    7. Clean OCR noise
    8. Normalize Arabic numbers to English digits
    9. Fix spacing issues
    10. Remove non-Arabic noise (isolated symbols)

    Args:
        text: Raw Arabic text

    Returns:
        Normalized text
    """
    if not text:
        return ""

    # Step 1: Remove diacritics (tashkeel)
    text = remove_diacritics(text)

    # Step 2: Remove tatweel (kashida)
    text = remove_tatweel(text)

    # Step 3: Normalize Alef variants
    for variant, standard in ALEF_VARIANTS.items():
        text = text.replace(variant, standard)

    # Step 4: Normalize Ta marbuta
    for variant, standard in TA_MARBUTA_VARIANTS.items():
        text = text.replace(variant, standard)

    # Step 5: Normalize Alef maqsura (ى → ي)
    for variant, standard in ALEF_MAQSURA_VARIANTS.items():
        text = text.replace(variant, standard)

    # Step 6: Fix OCR confusion characters
    for wrong, correct in OCR_CONFUSION_MAP.items():
        text = text.replace(wrong, correct)

    # Step 7: Clean OCR noise
    text = clean_ocr_noise(text)

    # Step 8: Normalize Arabic numbers to English digits
    text = normalize_numbers_to_english(text)

    # Step 9: Fix spacing issues
    text = fix_spacing(text)

    return text


def remove_diacritics(text: str) -> str:
    """Remove Arabic diacritics (tashkeel/fatha/kasra/damma/shadda/sukun)"""
    # Unicode range: \u064B-\u065F\u0670
    return re.sub(r'[\u064B-\u065F\u0670]', '', text)


def remove_tatweel(text: str) -> str:
    """Remove tatweel/kashida (ـ) — elongation character used in Arabic text"""
    return text.replace('\u0640', '')  # ـ


def fix_spacing(text: str) -> str:
    """
    Fix spacing issues in Arabic text

    - Collapse multiple spaces to single
    - Remove spaces before punctuation
    - Fix spaces around Arabic text
    """
    # Collapse multiple whitespace to single space
    text = re.sub(r'\s+', ' ', text)
    # Remove spaces before Arabic/English punctuation
    text = re.sub(r'\s+([،؛:!؟.,;:!?])', r'\1', text)
    return text.strip()


def normalize_numbers_to_english(text: str) -> str:
    """Convert Arabic-Indic digits to English digits (٠→0, ١→1, ...)"""
    for ar_num, en_num in ARABIC_TO_ENGLISH_NUMS.items():
        text = text.replace(ar_num, en_num)
    return text


def normalize_numbers_to_arabic(text: str) -> str:
    """Convert English digits to Arabic-Indic digits (0→٠, 1→١, ...)"""
    for en_num, ar_num in ENGLISH_TO_ARABIC_NUMS.items():
        text = text.replace(en_num, ar_num)
    return text


def clean_ocr_noise(text: str) -> str:
    """
    Clean common OCR noise from Arabic text

    - Remove non-printable characters
    - Remove isolated symbols (single chars surrounded by spaces)
    - Fix common misrecognitions
    """
    # Remove non-printable characters except Arabic, Latin, numbers, basic punctuation
    text = ''.join(
        c for c in text
        if unicodedata.category(c)[0] != 'C' or c in '\n\t'
    )

    # Remove isolated single non-alphanumeric characters (OCR noise)
    text = re.sub(r'\s[^a-zA-Z0-9\u0600-\u06FF\u0621-\u064A]\s', ' ', text)

    return text


def standardize_phone_format(text: str) -> str:
    """
    Standardize Egyptian phone number formats in text

    Converts all variations to: +20XXXXXXXXXX
    - 01012345678 → +201012345678
    - +201012345678 → +201012345678
    - 00201012345678 → +201012345678
    """
    # International format: +20 or 0020
    text = re.sub(
        r'(?:\+20|0020)(10|11|12|15)(\d{8})',
        r'+20\1\2',
        text
    )

    # Local format: 01012345678
    text = re.sub(
        r'(?<!\d)0(10|11|12|15)(\d{8})(?!\d)',
        r'+20\1\2',
        text
    )

    # Formatted: 010-1234-5678 or 010 1234 5678
    text = re.sub(
        r'(?<!\d)0(10|11|12|15)[\s\-]?(\d{4})[\s\-]?(\d{4})(?!\d)',
        r'+20\1\2\3',
        text
    )

    return text


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
