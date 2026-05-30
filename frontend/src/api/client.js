import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
})

client.interceptors.request.use(
  (config) => {
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
