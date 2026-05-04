/**
 * SweetAlert2 wrapper themed for Cybercrime AI
 *
 * Usage:
 *   import { alertSuccess, alertError, alertWarning, alertInfo, alertConfirm } from '../components/ui/Alert'
 *
 * Colors match the app's design system:
 *   Primary: #00BD7D (green)
 *   Success: #16A34A
 *   Warning: #D97706
 *   Danger:  #DC2626
 *   Surface: #171717 / #0A0A0A
 */
import Swal from 'sweetalert2'

// ─── Shared Theme Config ─────────────────────────────────────────────
const THEME = {
  background: '#0A0A0A',
  color: '#FAFAFA',
  confirmButtonColor: '#00BD7D',
  cancelButtonColor: '#404040',
  denyButtonColor: '#DC2626',
  // Smooth animations
  showClass: {
    popup: 'swal2-animate-show',
    backdrop: 'swal2-backdrop-show'
  },
  hideClass: {
    popup: 'swal2-animate-hide',
    backdrop: 'swal2-backdrop-hide'
  },
  // Custom CSS styling
  customClass: {
    popup: 'cyber-alert-popup',
    title: 'cyber-alert-title',
    htmlContainer: 'cyber-alert-content',
    confirmButton: 'cyber-alert-btn cyber-alert-btn-confirm',
    cancelButton: 'cyber-alert-btn cyber-alert-btn-cancel',
    denyButton: 'cyber-alert-btn cyber-alert-btn-deny',
    icon: 'cyber-alert-icon',
    closeButton: 'cyber-alert-close',
    timerProgressBar: 'cyber-progress-bar',
  },
  // Backdrop styling
  backdrop: `
    rgba(0,0,0,0.8)
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='40' height='40' viewBox='0 0 40 40'%3E%3Cg fill-rule='evenodd'%3E%3Cg fill='%2300BD7D' fill-opacity='0.05'%3E%3Cpath d='M0 40L40 0H20L0 20V40z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")
  `,
}

// ─── Alert Functions ──────────────────────────────────────────────────

export function alertSuccess(title, text = '', options = {}) {
  return Swal.fire({
    ...THEME,
    icon: 'success',
    title,
    text,
    timer: options.timer || 2500,
    timerProgressBar: true,
    showConfirmButton: options.showConfirmButton ?? false,
    ...options,
  })
}

export function alertError(title, text = '', options = {}) {
  return Swal.fire({
    ...THEME,
    icon: 'error',
    title,
    text,
    showConfirmButton: true,
    confirmButtonText: options.confirmButtonText || 'OK',
    ...options,
  })
}

export function alertWarning(title, text = '', options = {}) {
  return Swal.fire({
    ...THEME,
    icon: 'warning',
    title,
    text,
    showConfirmButton: true,
    confirmButtonText: options.confirmButtonText || 'OK',
    ...options,
  })
}

export function alertInfo(title, text = '', options = {}) {
  return Swal.fire({
    ...THEME,
    icon: 'info',
    title,
    text,
    timer: options.timer || 3000,
    timerProgressBar: true,
    showConfirmButton: options.showConfirmButton ?? false,
    ...options,
  })
}

export function alertConfirm(title, text = '', options = {}) {
  return Swal.fire({
    ...THEME,
    icon: 'warning',
    title,
    text,
    showConfirmButton: true,
    showCancelButton: true,
    confirmButtonText: options.confirmButtonText || 'Confirm',
    cancelButtonText: options.cancelButtonText || 'Cancel',
    ...options,
  })
}

export function alertDeleteConfirm(title = 'Are you sure?', text = 'This action cannot be undone.') {
  return Swal.fire({
    ...THEME,
    icon: 'warning',
    title,
    text,
    showConfirmButton: true,
    showCancelButton: true,
    confirmButtonText: 'Delete',
    confirmButtonColor: '#DC2626',
    cancelButtonText: 'Cancel',
  })
}

// ─── Toast Config ─────────────────────────────────────────────────────
const TOAST_THEME = {
  background: 'rgba(10, 10, 10, 0.95)',
  color: '#FAFAFA',
  showClass: {
    popup: 'swal2-toast-animate-show'
  },
  hideClass: {
    popup: 'swal2-toast-animate-hide'
  },
  customClass: {
    popup: 'cyber-toast-popup',
    title: 'cyber-toast-title',
    icon: 'cyber-toast-icon',
    timerProgressBar: 'cyber-toast-progress',
  },
}

// ─── Toast-style (non-blocking, top-right) ────────────────────────────

export function toastSuccess(title, options = {}) {
  return Swal.fire({
    ...TOAST_THEME,
    toast: true,
    position: 'top-end',
    icon: 'success',
    iconColor: '#00BD7D',
    title,
    showConfirmButton: false,
    timer: options.timer || 2500,
    timerProgressBar: true,
    showCloseButton: true,
    padding: '1em',
    ...options,
  })
}

export function toastError(title, options = {}) {
  return Swal.fire({
    ...TOAST_THEME,
    toast: true,
    position: 'top-end',
    icon: 'error',
    iconColor: '#DC2626',
    title,
    showConfirmButton: false,
    timer: options.timer || 3500,
    timerProgressBar: true,
    showCloseButton: true,
    padding: '1em',
    ...options,
  })
}

export function toastWarning(title, options = {}) {
  return Swal.fire({
    ...TOAST_THEME,
    toast: true,
    position: 'top-end',
    icon: 'warning',
    iconColor: '#D97706',
    title,
    showConfirmButton: false,
    timer: options.timer || 3000,
    timerProgressBar: true,
    showCloseButton: true,
    padding: '1em',
    ...options,
  })
}

export function toastInfo(title, options = {}) {
  return Swal.fire({
    ...TOAST_THEME,
    toast: true,
    position: 'top-end',
    icon: 'info',
    iconColor: '#3B82F6',
    title,
    showConfirmButton: false,
    timer: options.timer || 3000,
    timerProgressBar: true,
    showCloseButton: true,
    padding: '1em',
    ...options,
  })
}

// Direct access for advanced usage
export { Swal }
export default Swal
