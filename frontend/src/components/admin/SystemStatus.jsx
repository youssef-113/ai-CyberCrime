import { useHealth } from '../../hooks/useHealth'
import { Database, Server, Activity, RefreshCw, CheckCircle, XCircle, AlertCircle } from 'lucide-react'

/**
 * System status component showing API and Supabase connection health
 */
export default function SystemStatus() {
  const { status, loading, error, isHealthy, isSupabaseConnected, refetch } = useHealth()

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy':
      case 'connected':
        return <CheckCircle className="w-5 h-5 text-success" />
      case 'unhealthy':
      case 'disconnected':
        return <XCircle className="w-5 h-5 text-danger" />
      case 'unreachable':
        return <AlertCircle className="w-5 h-5 text-warning" />
      default:
        return <Activity className="w-5 h-5 text-neutral-500" />
    }
  }

  if (loading && !status.gateway) {
    return (
      <div className="p-4 bg-neutral-900/50 rounded-lg">
        <div className="flex items-center gap-2 text-neutral-400">
          <RefreshCw className="w-5 h-5 animate-spin" />
          <span>Checking system status...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 bg-neutral-900/50 rounded-lg space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Activity className="w-5 h-5" />
          System Status
        </h3>
        <button
          onClick={refetch}
          className="btn-ghost btn-icon"
          title="Refresh status"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {error && (
        <div className="p-3 bg-danger/10 border border-danger/20 rounded-lg">
          <p className="text-danger-light text-sm">Error: {error}</p>
        </div>
      )}

      {/* API Gateway */}
      <div className="flex items-center justify-between p-3 bg-neutral-800/50 rounded-lg">
        <div className="flex items-center gap-3">
          <Server className="w-5 h-5 text-primary" />
          <span>API Gateway</span>
        </div>
        {getStatusIcon(status.gateway)}
      </div>

      {/* Supabase Database */}
      <div className="flex items-center justify-between p-3 bg-neutral-800/50 rounded-lg">
        <div className="flex items-center gap-3">
          <Database className="w-5 h-5 text-accent-purple" />
          <span>Supabase Database</span>
        </div>
        <div className="flex items-center gap-2">
          {getStatusIcon(status.database)}
          <span className={`text-sm ${isSupabaseConnected ? 'text-success' : 'text-danger'}`}>
            {isSupabaseConnected ? 'Connected' : status.supabase}
          </span>
        </div>
      </div>

      {/* Services */}
      {Object.keys(status.services).length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-neutral-400">Microservices</h4>
          {Object.entries(status.services).map(([name, serviceStatus]) => (
            <div
              key={name}
              className="flex items-center justify-between p-2 bg-neutral-800/30 rounded text-sm"
            >
              <span className="capitalize">{name}</span>
              {getStatusIcon(serviceStatus)}
            </div>
          ))}
        </div>
      )}

      {/* Overall Status */}
      <div className={`p-3 rounded-lg text-center ${isHealthy ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'}`}>
        <p className="font-medium">
          {isHealthy ? 'All systems operational' : 'Some systems are experiencing issues'}
        </p>
      </div>
    </div>
  )
}
