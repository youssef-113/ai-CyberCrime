import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { Shield, AlertTriangle, CheckCircle, Clock, Filter, RefreshCw } from 'lucide-react'

/**
 * Security events monitoring component for admin dashboard
 */
export default function SecurityEvents() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    loadEvents()
  }, [filter])

  const loadEvents = async () => {
    try {
      setLoading(true)
      const params = filter ? { severity: filter } : {}
      const data = await adminApi.listSecurityEvents(params)
      setEvents(data.events || [])
      setError(null)
    } catch (err) {
      setError('Failed to load security events')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleResolveEvent = async (eventId) => {
    try {
      await adminApi.resolveSecurityEvent(eventId)
      loadEvents()
    } catch (err) {
      setError('Failed to resolve event')
    }
  }

  const getSeverityColor = (severity) => {
    const colors = {
      info: 'text-neutral-400 bg-neutral-700/50',
      warning: 'text-warning bg-warning/10',
      error: 'text-danger bg-danger/10',
      critical: 'text-danger bg-danger/20 border border-danger/30',
    }
    return colors[severity] || colors.info
  }

  const getSeverityIcon = (severity) => {
    const icons = {
      info: <Clock className="w-4 h-4" />,
      warning: <AlertTriangle className="w-4 h-4" />,
      error: <AlertTriangle className="w-4 h-4" />,
      critical: <AlertTriangle className="w-4 h-4" />,
    }
    return icons[severity] || icons.info
  }

  if (loading) {
    return (
      <div className="p-6">
        <div className="flex items-center gap-2 text-neutral-400">
          <Shield className="w-5 h-5 animate-spin" />
          <span>Loading security events...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold flex items-center gap-2">
          <Shield className="w-6 h-6" />
          Security Events
        </h2>
        <button
          onClick={loadEvents}
          className="btn-ghost btn-icon"
          title="Refresh events"
        >
          <RefreshCw className="w-5 h-5" />
        </button>
      </div>

      {error && (
        <div className="p-3 bg-danger/10 border border-danger/20 rounded-lg">
          <p className="text-danger-light text-sm">{error}</p>
        </div>
      )}

      {/* Filter */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-neutral-400" />
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="px-4 py-2 bg-neutral-800 border border-neutral-700 rounded-lg focus:border-primary focus:outline-none"
          >
            <option value="">All Severities</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="error">Error</option>
            <option value="critical">Critical</option>
          </select>
        </div>
      </div>

      {/* Events List */}
      <div className="space-y-3">
        {events.map((event) => (
          <div
            key={event.id}
            className={`p-4 rounded-lg border ${event.resolved ? 'bg-neutral-800/30 border-neutral-700 opacity-60' : 'bg-neutral-800/50 border-neutral-700'}`}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <span className={`p-2 rounded-lg ${getSeverityColor(event.severity)}`}>
                    {getSeverityIcon(event.severity)}
                  </span>
                  <div>
                    <h3 className="font-semibold capitalize">{event.event_type}</h3>
                    <p className="text-sm text-neutral-400">{event.description}</p>
                  </div>
                </div>
                
                <div className="ml-11 space-y-1 text-sm text-neutral-400">
                  {event.user_id && (
                    <p>User ID: {event.user_id}</p>
                  )}
                  {event.ip_address && (
                    <p>IP: {event.ip_address}</p>
                  )}
                  <p>Time: {new Date(event.created_at).toLocaleString()}</p>
                </div>
              </div>

              {!event.resolved && (
                <button
                  onClick={() => handleResolveEvent(event.id)}
                  className="ml-4 px-3 py-1.5 bg-success/20 text-success rounded-lg hover:bg-success/30 transition-colors flex items-center gap-1"
                >
                  <CheckCircle className="w-4 h-4" />
                  Resolve
                </button>
              )}
              
              {event.resolved && (
                <span className="ml-4 px-3 py-1.5 bg-neutral-700 text-neutral-400 rounded-lg flex items-center gap-1">
                  <CheckCircle className="w-4 h-4" />
                  Resolved
                </span>
              )}
            </div>
          </div>
        ))}

        {events.length === 0 && (
          <div className="p-8 text-center text-neutral-400">
            No security events found
          </div>
        )}
      </div>
    </div>
  )
}
