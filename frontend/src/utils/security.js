/**
 * Security utilities for XSS protection and input sanitization
 */

// Prompt injection detection patterns
const PROMPT_INJECTION_PATTERNS = [
  /ignore previous instructions/gi,
  /system prompt/gi,
  /reveal prompt/gi,
  /developer instructions/gi,
  /developer message/gi,
  /jailbreak/gi,
  /override/gi,
  /bypass/gi,
  /admin mode/gi,
  /root access/gi,
]

// XSS detection patterns
const XSS_PATTERNS = [
  /<script[^>]*>.*?<\/script>/gi,
  /javascript:/gi,
  /on\w+\s*=/gi,
  /<iframe[^>]*>.*?<\/iframe>/gi,
  /<object[^>]*>.*?<\/object>/gi,
  /<embed[^>]*>.*?<\/embed>/gi,
  /<meta[^>]*>/gi,
  /expression\s*\(/gi,
  /@import/gi,
  /data:text\/html/gi,
  /vbscript:/gi,
]

// SQL injection detection patterns
const SQL_INJECTION_PATTERNS = [
  /\b(union|select|insert|update|delete|drop|alter|create|truncate)\b/gi,
  /\b(or|and)\s+\d+\s*=\s*\d+/gi,
  /\b(or|and)\s+['"]\w+['"]\s*=\s*['"]\w+['"]/gi,
  /\b(exec|eval|system)\s*\(/gi,
  /\b(waitfor\s+delay)\b/gi,
  /\b(xp_|sp_)\w+/gi,
  /;\s*(drop|delete|truncate)\b/gi,
  /(\-\-|\/\*|\*\/)/g,
]

/**
 * Detect potential prompt injection in text
 */
export function detectPromptInjection(text) {
  if (typeof text !== 'string') return false
  return PROMPT_INJECTION_PATTERNS.some(pattern => {
    pattern.lastIndex = 0
    return pattern.test(text)
  })
}

/**
 * Detect potential XSS in a string
 */
export function detectXSS(value) {
  if (typeof value !== 'string') return false
  return XSS_PATTERNS.some(pattern => {
    pattern.lastIndex = 0
    return pattern.test(value)
  })
}

/**
 * Detect potential SQL injection in a string
 */
export function detectSQLInjection(value) {
  if (typeof value !== 'string') return false
  return SQL_INJECTION_PATTERNS.some(pattern => {
    pattern.lastIndex = 0
    return pattern.test(value)
  })
}

/**
 * Sanitize HTML by removing dangerous tags and attributes
 */
export function sanitizeHTML(html) {
  if (typeof html !== 'string') return html

  let clean = html

  // Remove script tags and their content
  clean = clean.replace(/<script[^>]*>.*?<\/script>/gi, '')

  // Remove dangerous event handlers
  clean = clean.replace(/on\w+\s*=\s*["'][^"']*["']/gi, '')

  // Remove javascript: protocol
  clean = clean.replace(/javascript:/gi, '')

  // Remove iframe, object, embed tags
  clean = clean.replace(/<(iframe|object|embed)[^>]*>.*?<\/\1>/gi, '')

  return clean
}

/**
 * Escape HTML entities to prevent XSS
 */
export function escapeHTML(str) {
  if (typeof str !== 'string') return str

  const escapeMap = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
    '/': '&#x2F;',
  }

  return str.replace(/[&<>"'/]/g, char => escapeMap[char])
}

/**
 * Validate input and throw error if malicious content detected
 * @param {any} value - The value to validate
 * @param {string} fieldName - The field name for error messages
 * @param {number} depth - Current nesting depth for DoS prevention
 * @returns {any} - The sanitized value
 */
export function validateInput(value, fieldName = 'input', depth = 0) {
  // Prevent DoS via deep nesting
  if (depth > 10) {
    throw new Error(`Maximum nesting depth exceeded in ${fieldName}`)
  }

  if (typeof value === 'string') {
    // Check string length
    if (value.length > 50000) {
      throw new Error(`${fieldName} exceeds maximum length (50,000 characters)`)
    }

    // Check for SQL injection
    if (detectSQLInjection(value)) {
      throw new Error(`Potentially malicious content detected in ${fieldName}`)
    }

    // Check for XSS
    if (detectXSS(value)) {
      throw new Error(`Potentially malicious content detected in ${fieldName}`)
    }

    // Check for prompt injection
    if (detectPromptInjection(value)) {
      throw new Error(`Potential prompt injection detected in ${fieldName}`)
    }

    return escapeHTML(value)
  }

  if (typeof value === 'object' && value !== null) {
    // Prevent huge nested objects
    if (Object.keys(value).length > 100) {
      throw new Error(`${fieldName} exceeds maximum size (100 keys)`)
    }

    // Block prototype pollution
    if (
      '__proto__' in value ||
      'constructor' in value ||
      'prototype' in value
    ) {
      throw new Error(`${fieldName} contains forbidden keys (prototype pollution prevention)`)
    }

    if (Array.isArray(value)) {
      return value.map((item, index) =>
        validateInput(item, `${fieldName}[${index}]`, depth + 1)
      )
    }

    const sanitized = {}
    for (const [key, val] of Object.entries(value)) {
      // Validate key names as well
      const sanitizedKey = validateInput(key, `${fieldName}.key`, depth + 1)
      sanitized[sanitizedKey] = validateInput(val, `${fieldName}.${key}`, depth + 1)
    }

    return sanitized
  }

  return value
}

/**
 * Sanitize URL to prevent XSS
 */
export function sanitizeURL(url) {
  if (typeof url !== 'string') return url

  // Remove javascript: protocol
  const clean = url.replace(/^javascript:/gi, '')

  // Ensure URL starts with http:// or https:// or relative path
  if (clean && !clean.match(/^https?:\/\//i) && !clean.match(/^\//)) {
    return null // Invalid URL
  }

  return clean
}

/**
 * Validate email format
 */
export function validateEmail(email) {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(email)
}

/**
 * Validate phone number format (basic validation)
 */
export function validatePhone(phone) {
  const phoneRegex = /^[\d\s\-\+\(\)]{10,20}$/
  return phoneRegex.test(phone)
}

/**
 * Truncate string to max length
 */
export function truncateString(str, maxLength = 8000) {
  if (typeof str !== 'string') return str
  return str.substring(0, maxLength)
}

/**
 * Comprehensive input sanitization for API requests
 */
export function sanitizeAPIRequest(data) {
  if (data instanceof FormData) {
    return data
  }

  if (typeof data === 'string') {
    return truncateString(escapeHTML(data))
  }

  if (typeof data === 'object' && data !== null) {
    if (Array.isArray(data)) {
      return data.map(item => sanitizeAPIRequest(item))
    }

    const sanitized = {}
    for (const key in data) {
      // Skip file objects
      if (data[key] instanceof File) {
        sanitized[key] = data[key]
      } else {
        sanitized[key] = sanitizeAPIRequest(data[key])
      }
    }
    return sanitized
  }

  return data
}

/**
 * Validate file for ACEB uploads (screenshots, evidence, PDFs)
 */
export function validateFile(file, maxSizeMB = 10) {
  const maxSize = maxSizeMB * 1024 * 1024

  // Check file size
  if (file.size > maxSize) {
    throw new Error(`File too large. Maximum is ${maxSizeMB}MB`)
  }

  // Check file type
  const allowedTypes = [
    'application/pdf',
    'image/png',
    'image/jpeg',
    'image/jpg',
    'image/tiff',
    'image/bmp',
    'text/plain',
  ]

  if (!allowedTypes.includes(file.type)) {
    throw new Error(`Invalid file type: ${file.type}`)
  }

  // Check file extension
  const allowedExtensions = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.txt']
  const fileExtension = '.' + file.name.split('.').pop().toLowerCase()

  if (!allowedExtensions.includes(fileExtension)) {
    throw new Error(`Invalid file extension: ${fileExtension}`)
  }

  return true
}

/**
 * Validate multiple files for batch upload
 */
export function validateFiles(files, maxFiles = 5, maxSizeMB = 10) {
  if (files.length > maxFiles) {
    throw new Error(`Too many files. Maximum is ${maxFiles}`)
  }

  files.forEach(file => validateFile(file, maxSizeMB))

  return true
}

/**
 * Check for prompt injection in OCR text before sending to LLM
 */
export function validateOCRText(text) {
  if (typeof text !== 'string') {
    throw new Error('OCR text must be a string')
  }

  // Check length
  if (text.length > 100000) {
    throw new Error('OCR text too large (max 100,000 characters)')
  }

  // Check for prompt injection
  if (detectPromptInjection(text)) {
    throw new Error('Potential prompt injection detected in OCR text')
  }

  return true
}

/**
 * Validate chat message for prompt injection
 */
export function validateChatMessage(message) {
  if (typeof message !== 'string') {
    throw new Error('Message must be a string')
  }

  // Check length
  if (message.length > 10000) {
    throw new Error('Message too long (max 10,000 characters)')
  }

  // Check for prompt injection
  if (detectPromptInjection(message)) {
    throw new Error('Potential prompt injection detected in message')
  }

  // Check for XSS
  if (detectXSS(message)) {
    throw new Error('Potentially malicious content detected in message')
  }

  return true
}
