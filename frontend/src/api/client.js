import axios from 'axios'
import { sanitizeAPIRequest, validateInput } from '../utils/security'

// VITE_API_URL points at the monolith host (e.g. https://cyber-crime-production.up.railway.app/).
// All frontend traffic is routed through the API gateway, which is mounted
// at /api on the monolith and is the only layer that enforces auth + persists
// to the database. Sub-app mounts (/chat, /ocr, /rag, ...) bypass that layer,
// so the client must always target /api.
function resolveApiUrl() {
  const configured = import.meta.env.VITE_API_URL
  if (configured) return configured.replace(/\/+$/, '')

  // In production (Vercel), try to reach the backend at the same origin + /api
  // or fall back to the hardcoded dev default
  if (import.meta.env.PROD) {
    const origin = window.location.origin
    const hostname = window.location.hostname
    // If deployed on Vercel, use relative path (backend proxied on same domain)
    if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
      return origin
    }
  }
  return 'https://cyber-crime-production.up.railway.app/'
}

const RAW_API_URL = resolveApiUrl()
const API_BASE_URL = RAW_API_URL.endsWith('/api') ? RAW_API_URL : `${RAW_API_URL}/api`

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
})

client.interceptors.request.use(
  (config) => {
    // Sanitize request data to prevent XSS and injection attacks
    if (config.data) {
      try {
        config.data = sanitizeAPIRequest(config.data)
      } catch (error) {
        console.error('Request sanitization error:', error)
        return Promise.reject(error)
      }
    }

    const token = localStorage.getItem('cybercrime_access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    // Inject session ID if available
    const sessionId = localStorage.getItem('cybercrime_session_id')
    if (sessionId) {
      config.headers['X-Session-ID'] = sessionId
    }

    // Inject tenant ID for RAG isolation
    const tenantId = localStorage.getItem('cybercrime_tenant_id')
    if (tenantId) {
      config.headers['X-Tenant-ID'] = tenantId
    }

    return config
  },
  (error) => Promise.reject(error)
)

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 429) {
      console.warn('Rate limit exceeded. Please wait before retrying.')
    }
    if (error.response?.status === 413) {
      console.warn('File too large. Maximum 10MB per file.')
    }

    // Auto-refresh on 401 (unless already retrying, refresh endpoint, or demo mode)
    const isDemo = localStorage.getItem('cybercrime_demo_mode') === 'true'
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/') &&
      !isDemo
    ) {
      originalRequest._retry = true
      const refreshToken = localStorage.getItem('cybercrime_refresh_token')
      if (refreshToken) {
        try {
          const resp = await client.post('/auth/refresh', { refresh_token: refreshToken })
          const { access_token, refresh_token: newRefresh } = resp.data
          localStorage.setItem('cybercrime_access_token', access_token)
          localStorage.setItem('cybercrime_refresh_token', newRefresh || refreshToken)
          originalRequest.headers.Authorization = `Bearer ${access_token}`
          return client(originalRequest)
        } catch {
          // Refresh failed, redirect to login
          localStorage.removeItem('cybercrime_access_token')
          localStorage.removeItem('cybercrime_refresh_token')
          localStorage.removeItem('cybercrime_user')
          localStorage.removeItem('cybercrime_session_id')
          localStorage.removeItem('cybercrime_tenant_id')
          window.location.href = '/login'
        }
      }
    }

    return Promise.reject(error)
  }
)

export default client
