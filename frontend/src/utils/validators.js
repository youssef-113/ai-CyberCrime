import { FILE_CONSTRAINTS } from './constants'

export function validateFile(file) {
  const errors = []

  const maxSize = FILE_CONSTRAINTS.MAX_SIZE_MB * 1024 * 1024
  if (file.size > maxSize) {
    errors.push(`File exceeds ${FILE_CONSTRAINTS.MAX_SIZE_MB}MB limit`)
  }

  if (!FILE_CONSTRAINTS.ACCEPTED_TYPES.includes(file.type)) {
    const ext = file.name.split('.').pop().toLowerCase()
    if (!FILE_CONSTRAINTS.ACCEPTED_EXTENSIONS.includes(`.${ext}`)) {
      errors.push('Unsupported file type. Accepted: PNG, JPG, PDF')
    }
  }

  return { valid: errors.length === 0, errors }
}

export function validateFileList(files) {
  if (files.length === 0) {
    return { valid: false, errors: ['No files selected'] }
  }

  if (files.length > FILE_CONSTRAINTS.MAX_FILES) {
    return { valid: false, errors: [`Maximum ${FILE_CONSTRAINTS.MAX_FILES} files allowed`] }
  }

  const results = files.map((f) => ({ file: f, ...validateFile(f) }))
  const invalidFiles = results.filter((r) => !r.valid)

  return {
    valid: invalidFiles.length === 0,
    errors: invalidFiles.flatMap((f) => f.errors),
    results,
  }
}

export function validateEmail(email) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return re.test(email)
}

export function validatePhone(phone) {
  const egPhone = /^(\+20|0)(10|11|12|15)\d{8}$/
  return egPhone.test(phone.replace(/\s/g, ''))
}

export function validatePasswordStrength(password) {
  const errors = []
  const MIN_LENGTH = 8

  if (!password) {
    return { valid: false, errors: ['Password is required'], strength: 0 }
  }

  if (password.length < MIN_LENGTH) {
    errors.push(`Password must be at least ${MIN_LENGTH} characters long`)
  }
  if (password.length > 128) {
    errors.push('Password must not exceed 128 characters')
  }
  if (!/[A-Z]/.test(password)) {
    errors.push('Password must contain at least one uppercase letter')
  }
  if (!/[a-z]/.test(password)) {
    errors.push('Password must contain at least one lowercase letter')
  }
  if (!/\d/.test(password)) {
    errors.push('Password must contain at least one digit')
  }
  if (!/[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`]/.test(password)) {
    errors.push('Password must contain at least one special character')
  }

  // Check common passwords
  const commonPasswords = [
    'password', 'password1', 'password123', '12345678', 'qwerty12',
    'abc12345', 'admin123', 'letmein1', 'welcome1', 'monkey123',
  ]
  if (commonPasswords.includes(password.toLowerCase())) {
    errors.push('This password is too common. Choose a more unique password')
  }

  // Calculate strength score (0-5)
  let strength = 0
  if (password.length >= MIN_LENGTH) strength++
  if (/[A-Z]/.test(password)) strength++
  if (/[a-z]/.test(password)) strength++
  if (/\d/.test(password)) strength++
  if (/[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`]/.test(password)) strength++

  return { valid: errors.length === 0, errors, strength }
}
