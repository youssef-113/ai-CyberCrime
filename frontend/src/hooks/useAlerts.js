import { useCallback } from 'react'
import { ActionAlerts, mapErrorMessage, showError, showSuccess, showConfirm, showLoading, closeAlert, updateAlert } from '../utils/alertConfig'

/**
 * Hook for using alerts throughout the app
 * Provides common action alerts and utility functions
 */
export function useAlerts() {
  // Auth alerts
  const loginSuccess = useCallback(() => ActionAlerts.loginSuccess(), [])
  const logoutSuccess = useCallback(() => ActionAlerts.logoutSuccess(), [])
  const registerSuccess = useCallback(() => ActionAlerts.registerSuccess(), [])
  const passwordChangeSuccess = useCallback(() => ActionAlerts.passwordChangeSuccess(), [])

  // Case alerts
  const caseCreated = useCallback((caseId) => ActionAlerts.caseCreated(caseId), [])
  const caseUpdated = useCallback(() => ActionAlerts.caseUpdated(), [])
  const caseFailed = useCallback((error) => ActionAlerts.analysisError(error), [])

  // Upload alerts
  const uploadStart = useCallback(() => ActionAlerts.uploadStart(), [])
  const uploadSuccess = useCallback((count) => ActionAlerts.uploadSuccess(count), [])
  const uploadFailed = useCallback((error) => ActionAlerts.uploadError(error), [])

  // Analysis/Pipeline alerts
  const analysisStart = useCallback(() => ActionAlerts.analysisStart(), [])
  const analysisComplete = useCallback((progress) => ActionAlerts.analysisComplete(progress), [])
  const analysisFailed = useCallback((error) => ActionAlerts.analysisError(error), [])

  // Chat alerts
  const chatSent = useCallback(() => ActionAlerts.chatSent(), [])
  const chatFailed = useCallback((error) => ActionAlerts.analysisError(error), [])

  // Verification alerts
  const verificationStart = useCallback(() => ActionAlerts.verificationStart(), [])
  const verificationComplete = useCallback((score) => ActionAlerts.verificationComplete(score), [])
  const verificationFailed = useCallback((error) => ActionAlerts.verificationError(error), [])

  // Error alerts
  const networkError = useCallback(() => ActionAlerts.networkError(), [])
  const serviceUnavailable = useCallback((service) => ActionAlerts.serviceUnavailable(service), [])
  const confirmDelete = useCallback((itemName) => ActionAlerts.confirmDelete(itemName), [])

  // Generic alerts
  const error = useCallback((title, message) => showError(title, message), [])
  const success = useCallback((title, message, options) => showSuccess(title, message, options), [])
  const confirm = useCallback((title, message, options) => showConfirm(title, message, options), [])
  const loading = useCallback((title, message) => showLoading(title, message), [])
  const close = useCallback(() => closeAlert(), [])
  const update = useCallback((title, message) => updateAlert(title, message), [])

  return {
    // Auth
    loginSuccess,
    logoutSuccess,
    registerSuccess,
    passwordChangeSuccess,

    // Case
    caseCreated,
    caseUpdated,
    caseFailed,

    // Upload
    uploadStart,
    uploadSuccess,
    uploadFailed,

    // Analysis
    analysisStart,
    analysisComplete,
    analysisFailed,

    // Chat
    chatSent,
    chatFailed,

    // Verification
    verificationStart,
    verificationComplete,
    verificationFailed,

    // Error handling
    networkError,
    serviceUnavailable,
    confirmDelete,

    // Generic
    error,
    success,
    confirm,
    loading,
    close,
    update,
  }
}

export default useAlerts
