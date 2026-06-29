import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { authApi } from '../api/auth'
import { ActionAlerts, mapErrorMessage, forceCloseAllAlerts, showToast } from '../utils/alertConfig'
import Swal from 'sweetalert2'

const AuthContext = createContext(null)

const TOKEN_KEY = 'cybercrime_access_token'
const REFRESH_KEY = 'cybercrime_refresh_token'
const USER_KEY = 'cybercrime_user'
const SESSION_ID_KEY = 'cybercrime_session_id'
const TENANT_ID_KEY = 'cybercrime_tenant_id'
const DEMO_KEY = 'cybercrime_demo_mode'

const DEMO_USER = {
  id: 'demo-00000000-0000-0000-0000-000000000000',
  email: 'demo@cybercrime-ai.local',
  full_name: 'Demo User',
  is_active: true,
  is_verified: true,
  created_at: new Date().toISOString(),
}

const DEMO_TOKEN = 'demo-access-token'
const DEMO_REFRESH = 'demo-refresh-token'

function getStoredAuth() {
  try {
    const isDemo = localStorage.getItem(DEMO_KEY) === 'true'
    if (isDemo) {
      return {
        token: DEMO_TOKEN,
        refreshToken: DEMO_REFRESH,
        user: DEMO_USER,
        sessionId: 'demo-session',
        tenantId: `user_${DEMO_USER.id}`,
        isAuthenticated: true,
        isDemo: true,
      }
    }
    const token = localStorage.getItem(TOKEN_KEY)
    const refreshToken = localStorage.getItem(REFRESH_KEY)
    const userJson = localStorage.getItem(USER_KEY)
    const sessionId = localStorage.getItem(SESSION_ID_KEY)
    const user = userJson ? JSON.parse(userJson) : null
    const tenantId = user ? `user_${user.id}` : localStorage.getItem(TENANT_ID_KEY)
    
    return {
      token,
      refreshToken,
      user,
      sessionId,
      tenantId,
      isAuthenticated: !!token,
      isDemo: false,
    }
  } catch {
    return {
      token: null,
      refreshToken: null,
      user: null,
      sessionId: null,
      tenantId: null,
      isAuthenticated: false,
      isDemo: false,
    }
  }
}

export function AuthProvider({ children }) {
  const location = useLocation()
  const [auth, setAuth] = useState(getStoredAuth)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [sessionValidated, setSessionValidated] = useState(false)

  // Force-close any open SweetAlert modals on route change to prevent blocking interactions
  useEffect(() => {
    Swal.close()
    forceCloseAllAlerts()
  }, [location.pathname])

  const persistAuth = useCallback((token, refreshToken, user) => {
    const tenantId = `user_${user.id}`
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(REFRESH_KEY, refreshToken)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
    localStorage.setItem(TENANT_ID_KEY, tenantId)
    setAuth({
      token,
      refreshToken,
      user,
      sessionId: localStorage.getItem(SESSION_ID_KEY),
      tenantId,
      isAuthenticated: true,
      isDemo: false,
    })
    setError(null)
  }, [])

  const clearAuth = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(SESSION_ID_KEY)
    localStorage.removeItem(TENANT_ID_KEY)
    localStorage.removeItem(DEMO_KEY)
    setAuth({
      token: null,
      refreshToken: null,
      user: null,
      sessionId: null,
      tenantId: null,
      isAuthenticated: false,
      isDemo: false,
    })
    setSessionValidated(false)
  }, [])

  const login = useCallback(
    async (email, password) => {
      setLoading(true)
      setError(null)
      try {
        const data = await authApi.login(email, password)
        persistAuth(data.access_token, data.refresh_token, data.user)

        // Create initial session
        try {
          const sessionResponse = await authApi.createSession()
          localStorage.setItem(SESSION_ID_KEY, sessionResponse.session_id)
          setAuth((prev) => ({
            ...prev,
            sessionId: sessionResponse.session_id,
          }))
        } catch (err) {
          console.warn('Could not create session:', err)
        }

        ActionAlerts.loginSuccess()
        return data
      } catch (err) {
        const message = mapErrorMessage(err)
        setError(message)
        showToast('error', 'Authentication Failed', message)
        throw err
      } finally {
        setLoading(false)
      }
    },
    [persistAuth]
  )

  const register = useCallback(
    async (email, password, fullName) => {
      setLoading(true)
      setError(null)
      try {
        const data = await authApi.register(email, password, fullName)
        persistAuth(data.access_token, data.refresh_token, data.user)

        // Create initial session
        try {
          const sessionResponse = await authApi.createSession()
          localStorage.setItem(SESSION_ID_KEY, sessionResponse.session_id)
          setAuth((prev) => ({
            ...prev,
            sessionId: sessionResponse.session_id,
          }))
        } catch (err) {
          console.warn('Could not create session:', err)
        }

        ActionAlerts.registerSuccess()
        return data
      } catch (err) {
        const message = mapErrorMessage(err)
        setError(message)
        showToast('error', 'Authentication Failed', message)
        throw err
      } finally {
        setLoading(false)
      }
    },
    [persistAuth]
  )

  const loginAsDemo = useCallback(() => {
    setLoading(false)
    localStorage.setItem(DEMO_KEY, 'true')
    localStorage.setItem(USER_KEY, JSON.stringify(DEMO_USER))
    localStorage.setItem(SESSION_ID_KEY, 'demo-session')
    localStorage.setItem(TENANT_ID_KEY, `user_${DEMO_USER.id}`)
    setAuth({
      token: DEMO_TOKEN,
      refreshToken: DEMO_REFRESH,
      user: DEMO_USER,
      sessionId: 'demo-session',
      tenantId: `user_${DEMO_USER.id}`,
      isAuthenticated: true,
      isDemo: true,
    })
    setError(null)
    setSessionValidated(true)
    ActionAlerts.loginSuccess()
  }, [])

  const logout = useCallback(async () => {
    if (!auth.isDemo) {
      try {
        await authApi.logout(auth.token)
      } catch {
        // Ignore logout API errors
      }
    }
    clearAuth()
    ActionAlerts.logoutSuccess()
  }, [auth.isDemo, auth.token, clearAuth])

  const refreshTokens = useCallback(async () => {
    if (!auth.refreshToken) {
      clearAuth()
      return null
    }
    try {
      const data = await authApi.refresh(auth.refreshToken)
      const newUser = auth.user
      persistAuth(data.access_token, data.refresh_token || auth.refreshToken, newUser)
      return data.access_token
    } catch {
      clearAuth()
      return null
    }
  }, [auth.refreshToken, auth.user, persistAuth, clearAuth])

  const updateProfile = useCallback(async (updates) => {
    const updatedUser = { ...auth.user, ...updates }
    localStorage.setItem(USER_KEY, JSON.stringify(updatedUser))
    setAuth((prev) => ({ ...prev, user: updatedUser }))
  }, [auth.user])

  const createChatSession = useCallback(async (caseId = null) => {
    try {
      const response = await authApi.createSession({ case_id: caseId })
      localStorage.setItem(SESSION_ID_KEY, response.session_id)
      setAuth((prev) => ({
        ...prev,
        sessionId: response.session_id,
      }))
      return response.session_id
    } catch (err) {
      console.error('Failed to create chat session:', err)
      throw err
    }
  }, [])

  const getCurrentSessionId = useCallback(() => {
    return auth.sessionId || localStorage.getItem(SESSION_ID_KEY)
  }, [auth.sessionId])

  const getTenantId = useCallback(() => {
    return auth.tenantId || localStorage.getItem(TENANT_ID_KEY)
  }, [auth.tenantId])

  const verifySession = useCallback(async () => {
    if (auth.isDemo) {
      setSessionValidated(true)
      return true
    }

    if (!auth.token || !auth.user) {
      setSessionValidated(true)
      return false
    }

    try {
      const data = await authApi.verify()
      // Store session_id and tenant_id from verify response
      if (data.session_id) {
        localStorage.setItem(SESSION_ID_KEY, data.session_id)
        setAuth((prev) => ({ ...prev, sessionId: data.session_id }))
      }
      if (data.tenant_id) {
        localStorage.setItem(TENANT_ID_KEY, data.tenant_id)
        setAuth((prev) => ({ ...prev, tenantId: data.tenant_id }))
      }
      setSessionValidated(true)
      return true
    } catch (err) {
      console.warn('Session verification failed:', err)
      clearAuth()
      setSessionValidated(true)
      return false
    }
  }, [auth.isDemo, auth.token, auth.user, clearAuth])

  // Auto-refresh token before expiry (skip for demo mode)
  useEffect(() => {
    if (!auth.token || auth.isDemo) return

    const interval = setInterval(async () => {
      await refreshTokens()
    }, 25 * 60 * 1000)

    return () => clearInterval(interval)
  }, [auth.token, auth.isDemo, refreshTokens])

  // Validate session on mount
  useEffect(() => {
    verifySession()
  }, [])

  const value = {
    // State
    user: auth.user,
    token: auth.token,
    refreshToken: auth.refreshToken,
    sessionId: auth.sessionId,
    tenantId: auth.tenantId,
    isAuthenticated: auth.isAuthenticated,
    isDemo: auth.isDemo,
    loading,
    error,
    sessionValidated,

    // Methods
    login,
    register,
    logout,
    loginAsDemo,
    refreshTokens,
    updateProfile,
    createChatSession,
    getCurrentSessionId,
    getTenantId,
    verifySession,
    setError,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

export default AuthContext
