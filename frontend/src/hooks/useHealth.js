import { useState, useEffect, useCallback } from 'react'
import client from '../api/client'

/**
 * Hook to check API and Supabase health status
 */
export function useHealth() {
  const [status, setStatus] = useState({
    gateway: 'unknown',
    database: 'unknown',
    supabase: 'unknown',
    services: {},
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const checkHealth = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await client.get('/health')
      setStatus(response.data)
    } catch (err) {
      setError(err.message)
      setStatus({
        gateway: 'unreachable',
        database: 'unknown',
        supabase: 'unknown',
        services: {},
      })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    checkHealth()

    // Auto-refresh every 30 seconds
    const interval = setInterval(checkHealth, 30000)
    return () => clearInterval(interval)
  }, [checkHealth])

  const isHealthy = status.gateway === 'healthy' && status.database === 'connected'
  const isSupabaseConnected = status.supabase === 'connected'

  return {
    status,
    loading,
    error,
    isHealthy,
    isSupabaseConnected,
    refetch: checkHealth,
  }
}
