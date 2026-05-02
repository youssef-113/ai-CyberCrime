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
  // Custom CSS animations
  customClass: {
    popup: 'cyber-alert-popup',
    title: 'cyber-alert-title',
    htmlContainer: 'cyber-alert-content',
    confirmButton: 'cyber-alert-btn cyber-alert-btn-confirm',
    cancelButton: 'cyber-alert-btn cyber-alert-btn-cancel',
    denyButton: 'cyber-alert-btn cyber-alert-btn-deny',
    icon: 'cyber-alert-icon',
    closeButton: 'cyber-alert-close',
  },
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

// ─── Toast-style (non-blocking, top-right) ────────────────────────────

export function toastSuccess(title, options = {}) {
  return Swal.fire({
    ...THEME,
    toast: true,
    position: 'top-end',
    icon: 'success',
    title,
    showConfirmButton: false,
    timer: options.timer || 2500,
    timerProgressBar: true,
    ...options,
  })
}

export function toastError(title, options = {}) {
  return Swal.fire({
    ...THEME,
    toast: true,
    position: 'top-end',
    icon: 'error',
    title,
    showConfirmButton: false,
    timer: options.timer || 3500,
    timerProgressBar: true,
    ...options,
  })
}

export function toastWarning(title, options = {}) {
  return Swal.fire({
    ...THEME,
    toast: true,
    position: 'top-end',
    icon: 'warning',
    title,
    showConfirmButton: false,
    timer: options.timer || 3000,
    timerProgressBar: true,
    ...options,
  })
}

export function toastInfo(title, options = {}) {
  return Swal.fire({
    ...THEME,
    toast: true,
    position: 'top-end',
    icon: 'info',
    title,
    showConfirmButton: false,
    timer: options.timer || 3000,
    timerProgressBar: true,
    ...options,
  })
}

// Direct access for advanced usage
export { Swal }
export default Swal
