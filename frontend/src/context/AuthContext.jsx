import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { authApi } from '../api/auth'

const AuthContext = createContext(null)

const TOKEN_KEY = 'cybercrime_access_token'
const REFRESH_KEY = 'cybercrime_refresh_token'
const USER_KEY = 'cybercrime_user'
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
      return { token: DEMO_TOKEN, refreshToken: DEMO_REFRESH, user: DEMO_USER, isAuthenticated: true, isDemo: true }
    }
    const token = localStorage.getItem(TOKEN_KEY)
    const refreshToken = localStorage.getItem(REFRESH_KEY)
    const userJson = localStorage.getItem(USER_KEY)
    const user = userJson ? JSON.parse(userJson) : null
    return { token, refreshToken, user, isAuthenticated: !!token, isDemo: false }
  } catch {
    return { token: null, refreshToken: null, user: null, isAuthenticated: false, isDemo: false }
  }
}

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(getStoredAuth)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const persistAuth = useCallback((token, refreshToken, user) => {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(REFRESH_KEY, refreshToken)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
    setAuth({ token, refreshToken, user, isAuthenticated: true })
    setError(null)
  }, [])

  const clearAuth = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(DEMO_KEY)
    setAuth({ token: null, refreshToken: null, user: null, isAuthenticated: false, isDemo: false })
  }, [])

  const login = useCallback(async (email, password) => {
    setLoading(true)
    setError(null)
    try {
      const data = await authApi.login(email, password)
      persistAuth(data.access_token, data.refresh_token, data.user)
      return data
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Login failed'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [persistAuth])

  const register = useCallback(async (email, password, fullName) => {
    setLoading(true)
    setError(null)
    try {
      const data = await authApi.register(email, password, fullName)
      persistAuth(data.access_token, data.refresh_token, data.user)
      return data
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Registration failed'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [persistAuth])

  const loginAsDemo = useCallback(() => {
    localStorage.setItem(DEMO_KEY, 'true')
    setAuth({ token: DEMO_TOKEN, refreshToken: DEMO_REFRESH, user: DEMO_USER, isAuthenticated: true, isDemo: true })
    setError(null)
  }, [])

  const logout = useCallback(async () => {
    if (!auth.isDemo) {
      try {
        if (auth.token) {
          await authApi.logout(auth.token)
        }
      } catch {
        // Ignore logout API errors
      }
    }
    clearAuth()
  }, [auth.token, auth.isDemo, clearAuth])

  const refreshTokens = useCallback(async () => {
    if (!auth.refreshToken) {
      clearAuth()
      return null
    }
    try {
      const data = await authApi.refresh(auth.refreshToken)
      const newUser = auth.user
      persistAuth(data.access_token, data.refresh_token, newUser)
      return data.access_token
    } catch {
      clearAuth()
      return null
    }
  }, [auth.refreshToken, auth.user, persistAuth, clearAuth])

  const updateProfile = useCallback(async (updates) => {
    // Update local user data
    const updatedUser = { ...auth.user, ...updates }
    localStorage.setItem(USER_KEY, JSON.stringify(updatedUser))
    setAuth((prev) => ({ ...prev, user: updatedUser }))
  }, [auth.user])

  // Auto-refresh token before expiry (skip for demo mode)
  useEffect(() => {
    if (!auth.token || auth.isDemo) return

    const interval = setInterval(async () => {
      await refreshTokens()
    }, 25 * 60 * 1000)

    return () => clearInterval(interval)
  }, [auth.token, auth.isDemo, refreshTokens])

  const value = {
    ...auth,
    loading,
    error,
    login,
    register,
    loginAsDemo,
    logout,
    refreshTokens,
    updateProfile,
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
