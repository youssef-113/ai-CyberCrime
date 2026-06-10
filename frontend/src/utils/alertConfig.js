import Swal from 'sweetalert2'

/**
 * System color palette matching theme
 */
export const ALERT_COLORS = {
  primary: '#00BD7D',
  primaryLight: '#1AD79F',
  primaryDark: '#009746',
  success: '#16A34A',
  warning: '#D97706',
  danger: '#DC2626',
  info: '#0EA5E9',
  surface: '#FFFFFF',
  dark: '#111827',
  neutral900: '#111827',
  neutral950: '#030712',
}

/**
 * Error message mapping - converts API errors to user-friendly messages
 */
export const ERROR_MESSAGES = {
  // Authentication errors
  'invalid_credentials': 'Email or password is incorrect',
  'user_not_found': 'User account not found',
  'user_already_exists': 'This email is already registered',
  'invalid_email': 'Please enter a valid email address',
  'password_too_weak': 'Password must be at least 8 characters long',
  'password_mismatch': 'Passwords do not match',
  'unauthorized': 'Your session has expired. Please login again',
  'forbidden': 'You do not have permission to perform this action',
  'token_expired': 'Your session has expired. Please login again',
  'invalid_token': 'Invalid authentication token',

  // Validation errors
  'validation_error': 'Please check your input and try again',
  'invalid_input': 'Invalid input provided',
  'missing_required_field': 'Please fill in all required fields',
  'field_required': 'This field is required',

  // File upload errors
  'file_too_large': 'File size exceeds the maximum limit (50MB)',
  'invalid_file_type': 'This file type is not supported. Allowed: PDF, DOC, DOCX, JPG, PNG, TIF',
  'file_upload_failed': 'Failed to upload file. Please try again',
  'no_file_selected': 'Please select at least one file',
  'file_scan_failed': 'Failed to scan file. Please try again',

  // OCR errors
  'ocr_service_unavailable': 'OCR service is currently unavailable',
  'ocr_failed': 'Failed to extract text from file',
  'low_ocr_confidence': 'Extracted text has low confidence. Please review results',
  'invalid_image_format': 'Invalid image format. Please use JPG, PNG, or TIF',

  // RAG/Classification errors
  'rag_service_unavailable': 'Legal knowledge base service is unavailable',
  'classification_failed': 'Failed to classify case. Please try again',
  'retrieval_failed': 'Failed to retrieve legal articles',
  'index_failed': 'Failed to index documents',

  // Case/Chat errors
  'case_not_found': 'Case not found',
  'case_creation_failed': 'Failed to create case',
  'case_update_failed': 'Failed to update case',
  'chat_failed': 'Failed to send message',
  'session_not_found': 'Chat session not found',
  'chat_service_unavailable': 'Chat service is currently unavailable',

  // Verification errors
  'verification_failed': 'Failed to verify case',
  'verification_service_unavailable': 'Verification service is unavailable',
  'insufficient_evidence': 'Insufficient evidence to verify case',

  // Database errors
  'database_error': 'Database error occurred. Please try again',
  'connection_error': 'Failed to connect to server',
  'timeout': 'Request timed out. Please try again',

  // Server errors
  'server_error': 'Server error occurred. Please try again later',
  'service_unavailable': 'Service is currently unavailable',
  'too_many_requests': 'Too many requests. Please wait a moment and try again',

  // Network errors
  'network_error': 'Network connection error. Please check your internet',
  'offline': 'You are offline. Please check your internet connection',

  // Generic fallback
  'unknown_error': 'An unexpected error occurred. Please try again',
}

/**
 * Get user-friendly error message from error object or code
 */
export function mapErrorMessage(error) {
  if (!error) return ERROR_MESSAGES.unknown_error

  // If error is a string, check the mapping
  if (typeof error === 'string') {
    return ERROR_MESSAGES[error.toLowerCase()] || error
  }

  // If error is an object with response data
  if (error.response?.data?.detail) {
    const detail = error.response.data.detail
    if (typeof detail === 'string') {
      return ERROR_MESSAGES[detail.toLowerCase()] || detail
    }
    if (detail.message) {
      return ERROR_MESSAGES[detail.message.toLowerCase()] || detail.message
    }
  }

  // Check for common error property names
  if (error.message) {
    const messageLower = error.message.toLowerCase()
    return ERROR_MESSAGES[messageLower] || error.message
  }

  if (error.error) {
    const errorLower = error.error.toLowerCase()
    return ERROR_MESSAGES[errorLower] || error.error
  }

  // Check status code patterns
  if (error.response?.status === 401 || error.response?.status === 403) {
    return ERROR_MESSAGES.unauthorized
  }

  if (error.response?.status === 404) {
    return 'Resource not found'
  }

  if (error.response?.status === 429) {
    return ERROR_MESSAGES.too_many_requests
  }

  if (error.response?.status >= 500) {
    return ERROR_MESSAGES.server_error
  }

  return ERROR_MESSAGES.unknown_error
}

/**
 * Configure SweetAlert2 with system theme
 */
export function getAlertConfig(type = 'info') {
  const config = {
    background: ALERT_COLORS.neutral900,
    color: '#FFFFFF',
    confirmButtonColor: ALERT_COLORS.primary,
    cancelButtonColor: ALERT_COLORS.neutral900,
    allowOutsideClick: false,
    allowEscapeKey: true,
    customClass: {
      popup: 'alert-popup',
      title: 'alert-title',
      htmlContainer: 'alert-message',
      confirmButton: 'alert-confirm-btn',
      cancelButton: 'alert-cancel-btn',
      icon: 'alert-icon',
    },
    didOpen: (modal) => {
      modal.classList.add('alert-animate-in')
    },
  }

  // Type-specific styling
  const typeConfigs = {
    success: {
      icon: 'success',
      confirmButtonColor: ALERT_COLORS.success,
    },
    error: {
      icon: 'error',
      confirmButtonColor: ALERT_COLORS.danger,
    },
    warning: {
      icon: 'warning',
      confirmButtonColor: ALERT_COLORS.warning,
    },
    info: {
      icon: 'info',
      confirmButtonColor: ALERT_COLORS.info,
    },
  }

  return { ...config, ...typeConfigs[type] }
}

/**
 * Success alert
 */
export async function showSuccess(title, message = '', options = {}) {
  return Swal.fire({
    ...getAlertConfig('success'),
    title: title || 'Success!',
    html: message,
    timer: options.timer || 3000,
    timerProgressBar: true,
    ...options,
  })
}

/**
 * Error alert
 */
export async function showError(title, message = '', options = {}) {
  const errorMsg = typeof message === 'object' ? mapErrorMessage(message) : message

  return Swal.fire({
    ...getAlertConfig('error'),
    title: title || 'Error!',
    html: errorMsg,
    ...options,
  })
}

/**
 * Warning alert
 */
export async function showWarning(title, message = '', options = {}) {
  return Swal.fire({
    ...getAlertConfig('warning'),
    title: title || 'Warning!',
    html: message,
    ...options,
  })
}

/**
 * Info alert
 */
export async function showInfo(title, message = '', options = {}) {
  return Swal.fire({
    ...getAlertConfig('info'),
    title: title || 'Information',
    html: message,
    ...options,
  })
}

/**
 * Confirmation dialog
 */
export async function showConfirm(title, message = '', options = {}) {
  return Swal.fire({
    ...getAlertConfig('info'),
    title: title || 'Confirm',
    html: message,
    showCancelButton: true,
    confirmButtonText: options.confirmText || 'Yes, proceed',
    cancelButtonText: options.cancelText || 'Cancel',
    ...options,
  })
}

/**
 * Loading alert (spinner)
 */
export function showLoading(title = 'Processing...', message = '') {
  return Swal.fire({
    ...getAlertConfig('info'),
    title: title,
    html: message,
    allowOutsideClick: false,
    allowEscapeKey: false,
    didOpen: async () => {
      Swal.showLoading()
    },
  })
}

/**
 * Close current alert
 */
export function closeAlert() {
  return Swal.close()
}

/**
 * Update alert content (for dynamic updates)
 */
export function updateAlert(title = null, message = null) {
  if (title !== null) {
    Swal.update({ title })
  }
  if (message !== null) {
    Swal.update({ html: message })
  }
}

/**
 * Action-specific alerts with context
 */
export const ActionAlerts = {
  // Auth actions
  loginSuccess: () => showSuccess(
    '👋 Welcome Back!',
    'You have successfully logged in',
    { timer: 2500 }
  ),

  logoutSuccess: () => showSuccess(
    '👋 Goodbye!',
    'You have been successfully logged out',
    { timer: 2500 }
  ),

  registerSuccess: () => showSuccess(
    '🎉 Account Created!',
    'Your account has been successfully created. Please log in.',
    { timer: 3000 }
  ),

  passwordChangeSuccess: () => showSuccess(
    '✅ Password Updated!',
    'Your password has been successfully changed',
    { timer: 2500 }
  ),

  // Case actions
  caseCreated: (caseId) => showSuccess(
    '📋 Case Created!',
    `Your case has been created successfully<br><small>Case ID: ${caseId}</small>`,
    { timer: 3000 }
  ),

  caseUpdated: () => showSuccess(
    '✏️ Case Updated!',
    'Case information has been updated successfully',
    { timer: 2500 }
  ),

  // File upload
  uploadStart: () => showLoading(
    '📤 Uploading Files',
    'Please wait while your files are being uploaded...'
  ),

  uploadSuccess: (count) => showSuccess(
    '📤 Upload Complete!',
    `${count} file(s) have been uploaded successfully`,
    { timer: 3000 }
  ),

  // Analysis/Pipeline
  analysisStart: () => showLoading(
    '🔍 Analyzing Case',
    'Running OCR, classification, retrieval, and verification...'
  ),

  analysisComplete: (progress) => showSuccess(
    '✅ Analysis Complete!',
    `Case analysis finished successfully<br><small>${progress}% complete</small>`,
    { timer: 3000 }
  ),

  // Chat actions
  chatSent: () => showSuccess(
    '💬 Message Sent!',
    'Your message has been sent',
    { timer: 1500 }
  ),

  // Verification
  verificationStart: () => showLoading(
    '🔐 Verifying Case',
    'Running verification analysis...'
  ),

  verificationComplete: (score) => showSuccess(
    '✅ Verification Complete!',
    `Verification finished<br><small>Score: ${score}%</small>`,
    { timer: 3000 }
  ),

  // Error alerts with action context
  authError: (error) => showError(
    '❌ Authentication Failed',
    mapErrorMessage(error)
  ),

  uploadError: (error) => showError(
    '❌ Upload Failed',
    mapErrorMessage(error)
  ),

  analysisError: (error) => showError(
    '❌ Analysis Failed',
    mapErrorMessage(error)
  ),

  verificationError: (error) => showError(
    '❌ Verification Failed',
    mapErrorMessage(error)
  ),

  networkError: () => showError(
    '❌ Connection Error',
    'Failed to connect to server. Please check your internet connection.'
  ),

  serviceUnavailable: (service) => showError(
    '⚠️ Service Unavailable',
    `${service} is currently unavailable. Please try again later.`
  ),

  confirmDelete: (itemName) => showConfirm(
    '⚠️ Confirm Delete',
    `Are you sure you want to delete <strong>${itemName}</strong>?<br><small>This action cannot be undone.</small>`,
    {
      confirmText: 'Yes, delete it',
      cancelText: 'Cancel',
      confirmButtonColor: ALERT_COLORS.danger,
    }
  ),
}

/**
 * Toast notification style alerts (top-right corner, auto-dismiss)
 */
export async function showToast(type = 'info', title = '', message = '') {
  return Swal.mixin({
    toast: true,
    position: 'top-end',
    showConfirmButton: false,
    timer: 3000,
    timerProgressBar: true,
    didOpen: (toast) => {
      toast.addEventListener('mouseenter', Swal.stopTimer)
      toast.addEventListener('mouseleave', Swal.resumeTimer)
    },
  }).fire({
    icon: type,
    title: title,
    text: message,
  })
}

/**
 * Add custom CSS for alerts
 */
export function initializeAlertStyles() {
  const style = document.createElement('style')
  style.textContent = `
    /* Alert animations */
    .alert-animate-in {
      animation: alertSlideIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
    }

    @keyframes alertSlideIn {
      from {
        opacity: 0;
        transform: scale(0.95) translateY(-20px);
      }
      to {
        opacity: 1;
        transform: scale(1) translateY(0);
      }
    }

    /* Alert popup styling */
    .alert-popup {
      border: 1px solid rgba(0, 189, 125, 0.2);
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3), 0 0 40px rgba(0, 189, 125, 0.1);
      border-radius: 0.875rem;
      backdrop-filter: blur(10px);
    }

    .alert-title {
      font-size: 1.5rem;
      font-weight: 700;
      margin-bottom: 0.75rem;
      color: #FFFFFF;
      font-family: 'Poppins', sans-serif;
    }

    .alert-message {
      font-size: 1rem;
      line-height: 1.6;
      color: #D1D5DB;
      margin: 1rem 0;
      font-family: 'Poppins', sans-serif;
    }

    .alert-message small {
      display: block;
      font-size: 0.875rem;
      color: #9CA3AF;
      margin-top: 0.5rem;
    }

    .alert-confirm-btn,
    .alert-cancel-btn {
      font-family: 'Poppins', sans-serif;
      font-weight: 600;
      padding: 0.625rem 1.5rem;
      border-radius: 0.5rem;
      border: none;
      cursor: pointer;
      transition: all 0.3s ease;
      font-size: 1rem;
    }

    .alert-confirm-btn {
      background: linear-gradient(135deg, #00BD7D 0%, #1AD79F 100%);
      color: #FFFFFF;
    }

    .alert-confirm-btn:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 16px rgba(0, 189, 125, 0.3);
    }

    .alert-cancel-btn {
      background: #374151;
      color: #FFFFFF;
      margin-left: 0.5rem;
    }

    .alert-cancel-btn:hover {
      background: #4B5563;
      transform: translateY(-2px);
    }

    /* Icon styling */
    .alert-icon {
      font-size: 3rem;
      margin-bottom: 1rem;
    }

    /* Toast styling */
    .swal2-toast {
      background: rgba(17, 24, 39, 0.95);
      backdrop-filter: blur(10px);
      border: 1px solid rgba(0, 189, 125, 0.2);
      border-radius: 0.5rem;
    }

    .swal2-toast .swal2-title {
      font-size: 1rem;
      font-weight: 600;
      color: #FFFFFF;
    }

    .swal2-toast .swal2-icon {
      font-size: 1.5rem;
    }

    /* Loading spinner color */
    .swal2-loading::after {
      border-color: #00BD7D transparent #00BD7D transparent !important;
    }

    /* RTL support */
    [dir="rtl"] .alert-cancel-btn {
      margin-left: 0;
      margin-right: 0.5rem;
    }

    [dir="rtl"] .swal2-toast {
      right: auto;
      left: 1rem;
    }
  `
  document.head.appendChild(style)
}
