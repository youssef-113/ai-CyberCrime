import os
import re
import html
import json
import hashlib
import time
import secrets
import logging
from typing import Any, Optional, Dict, List

logger = logging.getLogger("aceb.security")
from fastapi import HTTPException, UploadFile, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta
import ipaddress

MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", "10485760"))
MAX_UPLOAD_FILES = int(os.getenv("MAX_UPLOAD_FILES", "5"))
MAX_REQUEST_SIZE_BYTES = int(os.getenv("MAX_REQUEST_SIZE_BYTES", "10485760"))  # 10MB default
MAX_JSON_PAYLOAD_SIZE = int(os.getenv("MAX_JSON_PAYLOAD_SIZE", "1048576"))  # 1MB default
MAX_OCR_PAGES = int(os.getenv("MAX_OCR_PAGES", "20"))
MAX_OCR_TIMEOUT = int(os.getenv("MAX_OCR_TIMEOUT", "30"))
ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".txt"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/bmp",
    "text/plain",
}

# Rate limiting configuration
RATE_LIMIT_CONFIG = {
    "default": {"requests": 100, "window": 60},  # 100 requests per minute
    "auth": {"requests": 5, "window": 60},  # 5 auth requests per minute
    "upload": {"requests": 10, "window": 3600},  # 10 uploads per hour
    "api": {"requests": 1000, "window": 3600},  # 1000 API requests per hour
}

# IP-based blocking
BLOCKED_IPS = set()
SUSPICIOUS_IPS = defaultdict(int)  # Track failed attempts per IP
MAX_FAILED_ATTEMPTS = 10
BLOCK_DURATION_MINUTES = 30

# In-memory rate limiter (use Redis in production)
rate_limit_store: Dict[str, List[float]] = defaultdict(list)

# Blocked patterns for SQL injection and XSS
SQL_INJECTION_PATTERNS = [
    r"(?i)\b(union|select|insert|update|delete|drop|alter|create|truncate)\b",
    r"(?i)\b(or|and)\s+\d+\s*=\s*\d+",
    r"(?i)\b(or|and)\s+['\"]\w+['\"]\s*=\s*['\"]\w+['\"]",
    r"(?i)\b(exec|eval|system)\s*\(",
    r"(?i)\b(waitfor\s+delay)\b",
    r"(?i)\b(xp_|sp_)\w+",
    r"(?i);\s*(drop|delete|truncate)\b",
    r"(?i)\b(\-\-|\/\*|\*\/)",
]

XSS_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"javascript:",
    r"on\w+\s*=",
    r"<iframe[^>]*>.*?</iframe>",
    r"<object[^>]*>.*?</object>",
    r"<embed[^>]*>.*?</embed>",
    r"<meta[^>]*>",
    r"expression\s*\(",
    r"@import",
    r"data:text/html",
    r"vbscript:",
]

# Prompt injection detection patterns
PROMPT_INJECTION_PATTERNS = [
    r"ignore previous instructions",
    r"system prompt",
    r"reveal prompt",
    r"developer instructions",
    r"developer message",
    r"jailbreak",
    r"override",
    r"bypass",
    r"admin mode",
    r"root access",
]

# CSRF Protection
CSRF_TOKENS = {}  # In-memory storage (use Redis in production)
CSRF_TOKEN_EXPIRY = 3600  # 1 hour


def generate_csrf_token(user_id: str) -> str:
    """Generate a CSRF token for a user"""
    token = secrets.token_urlsafe(32)
    CSRF_TOKENS[token] = {
        "user_id": user_id,
        "expires_at": time.time() + CSRF_TOKEN_EXPIRY
    }
    return token


def validate_csrf_token(token: str, user_id: str) -> bool:
    """Validate a CSRF token"""
    if token not in CSRF_TOKENS:
        return False
    
    token_data = CSRF_TOKENS[token]
    
    # Check if token belongs to user
    if token_data["user_id"] != user_id:
        return False
    
    # Check if token is expired
    if time.time() > token_data["expires_at"]:
        del CSRF_TOKENS[token]
        return False
    
    return True


def cleanup_expired_csrf_tokens():
    """Remove expired CSRF tokens"""
    current_time = time.time()
    expired_tokens = [
        token for token, data in CSRF_TOKENS.items()
        if current_time > data["expires_at"]
    ]
    for token in expired_tokens:
        del CSRF_TOKENS[token]


# Allowed HTML tags (whitelist)
ALLOWED_HTML_TAGS = {
    'p', 'br', 'strong', 'em', 'u', 'b', 'i', 'a', 'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'code', 'pre'
}

# Allowed HTML attributes
ALLOWED_HTML_ATTRS = {
    'href', 'title', 'alt', 'class', 'id'
}


def sanitize_string(value: str, max_length: int = 8000) -> str:
    """Sanitize string input to prevent XSS attacks"""
    if not isinstance(value, str):
        return value
    
    # Strip leading/trailing whitespace
    clean = value.strip()
    
    # Remove null bytes and control characters
    clean = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]+", "", clean)
    
    # HTML escape
    clean = html.escape(clean)
    
    # Truncate to max length
    return clean[:max_length]


def sanitize_html(value: str) -> str:
    """Sanitize HTML input by removing dangerous tags and attributes"""
    if not isinstance(value, str):
        return value
    
    # Remove script tags and their content
    clean = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove dangerous event handlers
    clean = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '', clean, flags=re.IGNORECASE)
    
    # Remove javascript: protocol
    clean = re.sub(r'javascript:', '', clean, flags=re.IGNORECASE)
    
    # Remove iframe, object, embed tags
    clean = re.sub(r'<(iframe|object|embed)[^>]*>.*?</\1>', '', clean, flags=re.IGNORECASE | re.DOTALL)
    
    return clean


def detect_sql_injection(value: str) -> bool:
    """Detect potential SQL injection patterns"""
    if not isinstance(value, str):
        return False
    
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, value):
            return True
    return False


def detect_xss(value: str) -> bool:
    """Detect potential XSS patterns"""
    if not isinstance(value, str):
        return False
    
    for pattern in XSS_PATTERNS:
        if re.search(pattern, value):
            return True
    return False


def detect_prompt_injection(value: str) -> bool:
    """Detect potential prompt injection patterns"""
    if not isinstance(value, str):
        return False
    
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            return True
    return False


def validate_input(value: Any, field_name: str = "input", depth: int = 0) -> Any:
    """Validate and sanitize input, raise HTTPException if malicious content detected"""
    # Prevent DoS via deep nesting
    if depth > 10:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum nesting depth exceeded in {field_name}"
        )
    
    if isinstance(value, str):
        # Check string length
        if len(value) > 50000:
            raise HTTPException(
                status_code=400,
                detail=f"{field_name} exceeds maximum length (50,000 characters)"
            )
        
        # Check for SQL injection
        if detect_sql_injection(value):
            raise HTTPException(
                status_code=400,
                detail=f"Potentially malicious content detected in {field_name}"
            )
        
        # Check for XSS
        if detect_xss(value):
            raise HTTPException(
                status_code=400,
                detail=f"Potentially malicious content detected in {field_name}"
            )
        
        # Check for prompt injection
        if detect_prompt_injection(value):
            raise HTTPException(
                status_code=400,
                detail=f"Potential prompt injection detected in {field_name}"
            )
        
        # Sanitize
        return sanitize_string(value)
    
    if isinstance(value, dict):
        # Prevent huge nested objects
        if len(value) > 100:
            raise HTTPException(
                status_code=400,
                detail=f"{field_name} exceeds maximum size (100 keys)"
            )
        
        # Block prototype pollution
        if "__proto__" in value or "constructor" in value or "prototype" in value:
            raise HTTPException(
                status_code=400,
                detail=f"{field_name} contains forbidden keys (prototype pollution prevention)"
            )
        
        return {k: validate_input(v, f"{field_name}.{k}", depth + 1) for k, v in value.items()}
    
    if isinstance(value, list):
        return [validate_input(v, f"{field_name}[{i}]", depth + 1) for i, v in enumerate(value)]
    
    return value


def sanitize_payload(payload: Any) -> Any:
    """Recursively sanitize payload"""
    if isinstance(payload, str):
        return sanitize_string(payload)
    if isinstance(payload, dict):
        return {k: sanitize_payload(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [sanitize_payload(v) for v in payload]
    return payload


def get_client_ip(request: Request) -> str:
    """Get client IP address from request, handling proxies"""
    # Check for forwarded headers (behind proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"


def is_ip_blocked(ip: str) -> bool:
    """Check if IP is blocked"""
    return ip in BLOCKED_IPS


def block_ip(ip: str, duration_minutes: int = BLOCK_DURATION_MINUTES):
    """Block an IP address for specified duration"""
    BLOCKED_IPS.add(ip)
    # In production, use Redis with expiration
    # For now, this is in-memory and will reset on restart
    

def unblock_ip(ip: str):
    """Unblock an IP address"""
    BLOCKED_IPS.discard(ip)


def record_failed_attempt(ip: str):
    """Record a failed authentication attempt for an IP"""
    SUSPICIOUS_IPS[ip] += 1
    if SUSPICIOUS_IPS[ip] >= MAX_FAILED_ATTEMPTS:
        block_ip(ip)
        return True  # IP was blocked
    return False


def reset_failed_attempts(ip: str):
    """Reset failed attempt counter for an IP (on successful auth)"""
    SUSPICIOUS_IPS[ip] = 0


def check_rate_limit(identifier: str, limit_type: str = "default") -> bool:
    """Check if request is within rate limits"""
    config = RATE_LIMIT_CONFIG.get(limit_type, RATE_LIMIT_CONFIG["default"])
    max_requests = config["requests"]
    window_seconds = config["window"]
    
    current_time = time.time()
    
    # Get existing timestamps for this identifier
    timestamps = rate_limit_store.get(identifier, [])
    
    # Filter out timestamps outside the current window
    timestamps = [ts for ts in timestamps if current_time - ts < window_seconds]
    
    # Check if limit exceeded
    if len(timestamps) >= max_requests:
        return False
    
    # Add current timestamp
    timestamps.append(current_time)
    rate_limit_store[identifier] = timestamps
    
    return True


def get_rate_limit_headers(identifier: str, limit_type: str = "default") -> Dict[str, str]:
    """Get rate limit headers for response"""
    config = RATE_LIMIT_CONFIG.get(limit_type, RATE_LIMIT_CONFIG["default"])
    max_requests = config["requests"]
    window_seconds = config["window"]
    
    current_time = time.time()
    timestamps = rate_limit_store.get(identifier, [])
    
    # Filter out timestamps outside the current window
    timestamps = [ts for ts in timestamps if current_time - ts < window_seconds]
    
    remaining = max(0, max_requests - len(timestamps))
    reset_time = int(min(timestamps) + window_seconds) if timestamps else int(current_time + window_seconds)
    
    return {
        "X-RateLimit-Limit": str(max_requests),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Reset": str(reset_time),
    }


def get_security_headers() -> Dict[str, str]:
    """Get security headers for all responses"""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        ),
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=()"
        ),
    }


def log_security_event(event_type: str, details: Dict[str, Any], ip: str = "unknown"):
    """Log security event for monitoring"""
    # In production, send to logging service or database
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "ip_address": ip,
        "details": details,
    }
    # For now, just print (in production, use proper logging)
    print(f"SECURITY EVENT: {json.dumps(log_entry)}")


async def validate_upload_file(file: UploadFile, max_size: Optional[int] = None) -> bytes:
    """Validate uploaded file for ACEB (screenshots, evidence, PDFs)"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename")

    _, ext = os.path.splitext(file.filename.lower())
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file extension: {ext}")

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

    max_size = max_size or MAX_UPLOAD_SIZE_BYTES
    file_bytes = await file.read()
    if len(file_bytes) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(file_bytes)} bytes. Maximum is {max_size} bytes."
        )

    # Validate magic bytes
    validate_magic_bytes(file_bytes, file.content_type)

    # Scan for viruses
    scan_for_virus(file_bytes)

    # Reset the stream for later consumption
    try:
        file.file.seek(0)
    except Exception:
        pass

    return file_bytes


def validate_ocr_text(text: str, max_pages: int = None, max_chars: int = 100000) -> bool:
    """Validate OCR text before sending to LLM with security checks"""
    if not isinstance(text, str):
        raise HTTPException(status_code=400, detail="OCR text must be a string")
    
    # Check length
    if len(text) > max_chars:
        raise HTTPException(
            status_code=400,
            detail=f"OCR text too large (max {max_chars} characters)"
        )
    
    # Check for prompt injection
    if detect_prompt_injection(text):
        raise HTTPException(
            status_code=400,
            detail="Potential prompt injection detected in OCR text"
        )
    
    # Check for SQL injection
    if detect_sql_injection(text):
        raise HTTPException(
            status_code=400,
            detail="Potential SQL injection detected in OCR text"
        )
    
    # Check for XSS
    if detect_xss(text):
        raise HTTPException(
            status_code=400,
            detail="Potential XSS detected in OCR text"
        )
    
    return True


def sanitize_text_for_llm(text: str) -> str:
    """Sanitize text before sending to LLM to prevent prompt injection"""
    if not isinstance(text, str):
        return str(text)
    
    # Remove common prompt injection patterns
    sanitized = text
    
    # Remove instructions to ignore previous context
    sanitized = re.sub(r'(?i)ignore\s+(previous|all|the)\s+(instructions|prompts|context)', '', sanitized)
    sanitized = re.sub(r'(?i)system\s+prompt', '', sanitized)
    sanitized = re.sub(r'(?i)reveal\s+(system|your)\s+prompt', '', sanitized)
    sanitized = re.sub(r'(?i)developer\s+(instructions|message)', '', sanitized)
    sanitized = re.sub(r'(?i)jailbreak', '', sanitized)
    sanitized = re.sub(r'(?i)override', '', sanitized)
    sanitized = re.sub(r'(?i)bypass', '', sanitized)
    
    # Remove excessive whitespace
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    return sanitized


def validate_chat_message(message: str) -> bool:
    """Validate chat message for prompt injection"""
    if not isinstance(message, str):
        raise HTTPException(status_code=400, detail="Message must be a string")
    
    # Check length
    if len(message) > 10000:
        raise HTTPException(
            status_code=400,
            detail="Message too long (max 10,000 characters)"
        )
    
    # Check for prompt injection
    if detect_prompt_injection(message):
        raise HTTPException(
            status_code=400,
            detail="Potential prompt injection detected in message"
        )
    
    # Check for XSS
    if detect_xss(message):
        raise HTTPException(
            status_code=400,
            detail="Potentially malicious content detected in message"
        )
    
    return True


# File upload security with magic byte validation and virus scanning
MAGIC_BYTE_MAP = {
    b'\x89PNG': 'image/png',
    b'\xff\xd8\xff': 'image/jpeg',
    b'GIF87a': 'image/gif',
    b'GIF89a': 'image/gif',
    b'%PDF': 'application/pdf',
    b'BM': 'image/bmp',
    b'II*\x00': 'image/tiff',
    b'MM\x00\x2a': 'image/tiff',
}


def validate_magic_bytes(file_bytes: bytes, expected_type: str) -> bool:
    """Validate file magic bytes match expected content type"""
    for magic_bytes, content_type in MAGIC_BYTE_MAP.items():
        if file_bytes.startswith(magic_bytes):
            if content_type == expected_type:
                return True
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"File magic bytes indicate {content_type}, but expected {expected_type}"
                )
    
    # If no magic bytes match, check if it's plain text
    try:
        file_bytes.decode('utf-8')
        if expected_type == 'text/plain':
            return True
    except UnicodeDecodeError:
        pass
    
    raise HTTPException(
        status_code=400,
        detail="Invalid file format: magic bytes do not match declared content type"
    )


def scan_for_virus(file_bytes: bytes) -> bool:
    """Scan file for viruses using ClamAV (if available)"""
    try:
        import pyclamd
        clamav = pyclamd.ClamdUnixSocket()
        scan_result = clamav.scan_stream(file_bytes)
        
        if scan_result and scan_result.get('FOUND'):
            log_security_event("virus_detected", {"virus_name": str(scan_result)}, "unknown")
            raise HTTPException(
                status_code=403,
                detail="Virus detected in uploaded file"
            )
        
        return True
    except ImportError:
        # ClamAV not available, skip virus scanning
        logger.warning("ClamAV not available, skipping virus scan")
        return True
    except Exception as e:
        logger.error(f"Virus scan failed: {str(e)}")
        # Don't block upload if virus scan fails, but log it
        return True
