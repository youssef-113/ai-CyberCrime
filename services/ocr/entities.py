"""Entity extraction for Egyptian cybercrime evidence

Extracts structured entities from OCR text:
- Phone numbers (Egyptian format)
- Amounts in EGP
- Dates
- Social media accounts
- Email addresses
- IBAN numbers
"""
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from models import ExtractedEntity, EntityCollection
from arabic_utils import normalize_arabic_text


# Egyptian phone number patterns
PHONE_PATTERNS = [
    # International format: +201012345678
    (r'(\+20|0020)(10|11|12|15)\d{8}', 'international'),
    # Local format: 01012345678
    (r'0(10|11|12|15)\d{8}', 'local'),
    # Format with spaces/dashes: 010 1234 5678
    (r'0(10|11|12|15)[\s\-]?\d{4}[\s\-]?\d{4}', 'formatted'),
]

# Amount patterns (EGP)
AMOUNT_PATTERNS = [
    # Numbers with EGP/Sterling: 5000 EGP, 1000 جنيه
    (r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:EGP|L\.E|LE|ج\.م|جنيه|جنية|الف|K|k)', 'egp'),
    # Arabic numbers: ٥٠٠٠
    (r'[٠-٩]{1,}(?:\.[٠-٩]{2})?\s*(?:جنيه|جنية)', 'arabic_nums'),
    # Range amounts: 5000-10000 جنيه
    (r'(\d{1,3}(?:,\d{3})*)\s*(?:إلى|ل|to|-)\s*(\d{1,3}(?:,\d{3})*)\s*(?:جنيه|EGP)', 'range'),
]

# Date patterns
DATE_PATTERNS = [
    # DD/MM/YYYY or DD-MM-YYYY
    (r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', 'standard'),
    # Arabic dates: ١٥/١١/٢٠٢٤
    (r'[٠-٩]{1,2}[/-][٠-٩]{1,2}[/-][٠-٩]{2,4}', 'arabic_numerals'),
    # Written months: 15 نوفمبر 2024
    (r'\d{1,2}\s+(?:يناير|فبراير|مارس|أبريل|مايو|يونيو|يوليو|أغسطس|سبتمبر|أكتوبر|نوفمبر|ديسمبر|January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}', 'written'),
]

# Social media account patterns
ACCOUNT_PATTERNS = [
    # @username
    (r'@[\w_\.]+', 'mention'),
    # Facebook: fb.com/username or facebook.com/username
    (r'(?:facebook\.com|fb\.com)/([\w\.]+)', 'facebook'),
    # Instagram: instagram.com/username
    (r'instagram\.com/([\w\.]+)', 'instagram'),
    # Twitter/X: twitter.com/username or x.com/username
    (r'(?:twitter\.com|x\.com)/([\w\.]+)', 'twitter'),
    # TikTok: tiktok.com/@username
    (r'tiktok\.com/@([\w\.]+)', 'tiktok'),
    # WhatsApp link: wa.me/number
    (r'wa\.me/(\+?\d+)', 'whatsapp'),
]

# Email pattern
EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

# URL pattern
URL_PATTERN = r'https?://\S+|www\.\S+'

# Egyptian IBAN pattern
IBAN_PATTERN = r'EG\d{27}'

# Threat keywords (for confidence scoring)
THREAT_KEYWORDS = [
    'هنشر', 'هكسر', 'هاجمك', 'هفضحك', 'هبعت', 'هنشر',
    'سابعت', 'هاخد', 'هسرق', 'هدمر', 'هقتل',
    'publish', 'share', 'expose', 'hack', 'attack'
]


def extract_entities(text: str, block_id: Optional[str] = None) -> EntityCollection:
    """
    Extract all entities from text
    
    Args:
        text: OCR text (normalized)
        block_id: Source evidence block ID
        
    Returns:
        EntityCollection with all found entities
    """
    entities = EntityCollection()
    
    # Extract phone numbers
    entities.phones = extract_phones(text, block_id)
    
    # Extract amounts
    entities.amounts = extract_amounts(text, block_id)
    
    # Extract dates
    entities.dates = extract_dates(text, block_id)
    
    # Extract accounts
    entities.accounts = extract_accounts(text, block_id)
    
    # Extract emails
    entities.emails = extract_emails(text, block_id)
    
    # Extract URLs
    entities.urls = extract_urls(text, block_id)
    
    # Extract IBANs
    entities.ibans = extract_ibans(text, block_id)
    
    return entities


def extract_phones(text: str, block_id: Optional[str] = None) -> List[ExtractedEntity]:
    """Extract Egyptian phone numbers"""
    phones = []
    found = set()
    
    for pattern, pattern_type in PHONE_PATTERNS:
        for match in re.finditer(pattern, text):
            value = match.group()
            # Normalize: remove spaces and dashes
            normalized = re.sub(r'[\s\-]', '', value)
            
            if normalized in found:
                continue
            found.add(normalized)
            
            # Calculate confidence based on format
            if pattern_type == 'international':
                confidence = 0.98
            elif pattern_type == 'local':
                confidence = 0.95
            else:
                confidence = 0.90
            
            phones.append(ExtractedEntity(
                type="phone",
                value=normalized,
                confidence=confidence,
                source_block=block_id
            ))
    
    return phones


def extract_amounts(text: str, block_id: Optional[str] = None) -> List[ExtractedEntity]:
    """Extract monetary amounts in EGP"""
    amounts = []
    found = set()
    
    for pattern, pattern_type in AMOUNT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = match.group()
            
            if value in found:
                continue
            found.add(value)
            
            # Confidence based on pattern type
            if pattern_type == 'egp':
                confidence = 0.92
            elif pattern_type == 'arabic_nums':
                confidence = 0.88
            else:
                confidence = 0.85
            
            amounts.append(ExtractedEntity(
                type="amount",
                value=value,
                confidence=confidence,
                source_block=block_id
            ))
    
    return amounts


def extract_dates(text: str, block_id: Optional[str] = None) -> List[ExtractedEntity]:
    """Extract dates from text"""
    dates = []
    found = set()
    
    for pattern, pattern_type in DATE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = match.group()
            
            if value in found:
                continue
            found.add(value)
            
            # Confidence based on pattern type
            if pattern_type == 'standard':
                confidence = 0.88
            elif pattern_type == 'arabic_numerals':
                confidence = 0.85
            else:
                confidence = 0.80
            
            dates.append(ExtractedEntity(
                type="date",
                value=value,
                confidence=confidence,
                source_block=block_id
            ))
    
    return dates


def extract_accounts(text: str, block_id: Optional[str] = None) -> List[ExtractedEntity]:
    """Extract social media accounts"""
    accounts = []
    found = set()
    
    for pattern, platform in ACCOUNT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if platform == 'mention':
                value = match.group()
                platform_type = 'social_handle'
            else:
                # For platform URLs, extract the username group
                try:
                    value = f"{platform}: {match.group(1)}"
                    platform_type = platform
                except IndexError:
                    value = match.group()
                    platform_type = platform
            
            if value in found:
                continue
            found.add(value)
            
            accounts.append(ExtractedEntity(
                type=f"account_{platform_type}",
                value=value,
                confidence=0.90,
                source_block=block_id
            ))
    
    return accounts


def extract_emails(text: str, block_id: Optional[str] = None) -> List[ExtractedEntity]:
    """Extract email addresses"""
    emails = []
    
    for match in re.finditer(EMAIL_PATTERN, text, re.IGNORECASE):
        value = match.group()
        emails.append(ExtractedEntity(
            type="email",
            value=value,
            confidence=0.95,
            source_block=block_id
        ))
    
    return emails


def extract_urls(text: str, block_id: Optional[str] = None) -> List[ExtractedEntity]:
    """Extract URLs"""
    urls = []
    
    for match in re.finditer(URL_PATTERN, text):
        value = match.group()
        urls.append(ExtractedEntity(
            type="url",
            value=value,
            confidence=0.90,
            source_block=block_id
        ))
    
    return urls


def extract_ibans(text: str, block_id: Optional[str] = None) -> List[ExtractedEntity]:
    """Extract Egyptian IBAN numbers"""
    ibans = []
    
    for match in re.finditer(IBAN_PATTERN, text):
        value = match.group()
        ibans.append(ExtractedEntity(
            type="iban_eg",
            value=value,
            confidence=0.98,
            source_block=block_id
        ))
    
    return ibans


def check_threat_indicators(text: str) -> Dict:
    """
    Check for threat keywords in text
    
    Returns dict with found keywords and threat score
    """
    found_keywords = []
    text_lower = text.lower()
    
    for keyword in THREAT_KEYWORDS:
        if keyword in text or keyword in text_lower:
            found_keywords.append(keyword)
    
    # Calculate threat score (0-1)
    threat_score = min(len(found_keywords) / 3, 1.0) if found_keywords else 0.0
    
    return {
        "found_keywords": found_keywords,
        "threat_score": threat_score,
        "is_threatening": threat_score > 0.3
    }


def merge_entities(entity_collections: List[EntityCollection]) -> EntityCollection:
    """
    Merge multiple entity collections, removing duplicates
    """
    merged = EntityCollection()
    
    seen_phones = set()
    for ec in entity_collections:
        for phone in ec.phones:
            if phone.value not in seen_phones:
                merged.phones.append(phone)
                seen_phones.add(phone.value)
    
    seen_amounts = set()
    for ec in entity_collections:
        for amount in ec.amounts:
            if amount.value not in seen_amounts:
                merged.amounts.append(amount)
                seen_amounts.add(amount.value)
    
    seen_dates = set()
    for ec in entity_collections:
        for date in ec.dates:
            if date.value not in seen_dates:
                merged.dates.append(date)
                seen_dates.add(date.value)
    
    seen_accounts = set()
    for ec in entity_collections:
        for account in ec.accounts:
            if account.value not in seen_accounts:
                merged.accounts.append(account)
                seen_accounts.add(account.value)
    
    seen_emails = set()
    for ec in entity_collections:
        for email in ec.emails:
            if email.value not in seen_emails:
                merged.emails.append(email)
                seen_emails.add(email.value)
    
    seen_urls = set()
    for ec in entity_collections:
        for url in ec.urls:
            if url.value not in seen_urls:
                merged.urls.append(url)
                seen_urls.add(url.value)
    
    seen_ibans = set()
    for ec in entity_collections:
        for iban in ec.ibans:
            if iban.value not in seen_ibans:
                merged.ibans.append(iban)
                seen_ibans.add(iban.value)
    
    return merged
