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
