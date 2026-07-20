from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

try:
    from arabic_utils import normalize_arabic_text
    from models import ExtractedEntity, EntityCollection
except ImportError:
    ExtractedEntity = None
    EntityCollection = None

PHONE_PATTERNS = [
    (r'(\+20|0020)(10|11|12|15)\d{8}', 'international'),
    (r'0(10|11|12|15)\d{8}', 'local'),
    (r'0(10|11|12|15)[\s\-]?\d{4}[\s\-]?\d{4}', 'formatted'),
]

AMOUNT_PATTERNS = [
    (r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:EGP|L\.E|LE|ج\.م|جنيه|جنية|الف|K|k)', 'egp'),
    (r'[٠-٩]{1,}(?:\.[٠-٩]{2})?\s*(?:جنيه|جنية)', 'arabic_nums'),
    (r'(\d{1,3}(?:,\d{3})*)\s*(?:إلى|ل|to|-)\s*(\d{1,3}(?:,\d{3})*)\s*(?:جنيه|EGP)', 'range'),
]

DATE_PATTERNS = [
    (r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', 'standard'),
    (r'[٠-٩]{1,2}[/-][٠-٩]{1,2}[/-][٠-٩]{2,4}', 'arabic_numerals'),
    (r'\d{1,2}\s+(?:يناير|فبراير|مارس|أبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر|January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}', 'written'),
]

ACCOUNT_PATTERNS = [
    (r'@[\w_\.]+', 'mention'),
    (r'(?:facebook\.com|fb\.com)/([\w\.]+)', 'facebook'),
    (r'instagram\.com/([\w\.]+)', 'instagram'),
    (r'(?:twitter\.com|x\.com)/([\w\.]+)', 'twitter'),
    (r'tiktok\.com/@([\w\.]+)', 'tiktok'),
    (r'wa\.me/(\+?\d+)', 'whatsapp'),
]

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
URL_PATTERN = r'https?://\S+|www\.\S+'
IBAN_PATTERN = r'EG\d{27}'
BANK_ACCOUNT_PATTERN = r'\b\d{8,20}\b'


def extract_entities(text: str, block_id: Optional[str] = None) -> dict:
    entities = {
        "persons": [],
        "phones": [],
        "emails": [],
        "urls": [],
        "social_accounts": [],
        "bank_accounts": [],
        "iban": [],
        "amounts": [],
        "dates": [],
    }

    for pattern, _ in PHONE_PATTERNS:
        for match in re.finditer(pattern, text):
            val = re.sub(r'[\s\-]', '', match.group())
            if val not in entities["phones"]:
                entities["phones"].append(val)

    for pattern, _ in AMOUNT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            val = match.group()
            if val not in entities["amounts"]:
                entities["amounts"].append(val)

    for pattern, _ in DATE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            val = match.group()
            if val not in entities["dates"]:
                entities["dates"].append(val)

    for pattern, _ in ACCOUNT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            val = match.group()
            if val not in entities["social_accounts"]:
                entities["social_accounts"].append(val)

    for match in re.finditer(EMAIL_PATTERN, text, re.IGNORECASE):
        val = match.group()
        if val not in entities["emails"]:
            entities["emails"].append(val)

    for match in re.finditer(URL_PATTERN, text):
        val = match.group()
        if val not in entities["urls"]:
            entities["urls"].append(val)

    for match in re.finditer(IBAN_PATTERN, text):
        val = match.group()
        if val not in entities["iban"]:
            entities["iban"].append(val)

    for match in re.finditer(BANK_ACCOUNT_PATTERN, text):
        val = match.group()
        if val not in entities["bank_accounts"]:
            entities["bank_accounts"].append(val)

    return entities


def merge_entities(entity_list: List[dict]) -> dict:
    merged = {
        "persons": [],
        "phones": [],
        "emails": [],
        "urls": [],
        "social_accounts": [],
        "bank_accounts": [],
        "iban": [],
        "amounts": [],
        "dates": [],
    }
    seen = {k: set() for k in merged}
    for e in entity_list:
        for key in merged:
            for val in e.get(key, []):
                if val not in seen[key]:
                    merged[key].append(val)
                    seen[key].add(val)
    return merged


def check_threat_indicators(text: str) -> Dict[str, Any]:
    keywords = [
        'هنشر', 'هكسر', 'هاجمك', 'هفضحك', 'هبعت',
        'سابعت', 'هاخد', 'هسرق', 'هدمر', 'هقتل',
        'publish', 'share', 'expose', 'hack', 'attack', 'threat',
    ]
    found = [kw for kw in keywords if kw in text.lower()]
    score = min(len(found) / 3, 1.0) if found else 0.0
    return {
        "found_keywords": found,
        "threat_score": score,
        "is_threatening": score > 0.3,
    }
