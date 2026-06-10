import { useState, useEffect } from 'react'
import { adminApi } from '../../api/admin'
import { Users, FileText, Shield, Activity, TrendingUp, AlertTriangle } from 'lucide-react'

/**
 * Admin dashboard showing system statistics and management overview
 */
export default function AdminDashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    try {
      setLoading(true)
      const data = await adminApi.getStats()
      setStats(data)
      setError(null)
    } catch (err) {
      setError('Failed to load statistics')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="p-6">
        <div className="flex items-center gap-2 text-neutral-400">
          <Activity className="w-5 h-5 animate-spin" />
          <span>Loading admin dashboard...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="p-4 bg-danger/10 border border-danger/20 rounded-lg">
          <p className="text-danger-light">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Admin Dashboard</h2>
        <button
          onClick={loadStats}
          className="btn-ghost btn-icon"
          title="Refresh statistics"
        >
          <Activity className="w-5 h-5" />
        </button>
      </div>

      {error && (
        <div className="p-3 bg-danger/10 border border-danger/20 rounded-lg">
          <p className="text-danger-light text-sm">{error}</p>
        </div>
      )}

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Users"
          value={stats?.users?.total || 0}
          icon={<Users className="w-6 h-6" />}
          color="primary"
          subtitle={`${stats?.users?.active || 0} active`}
        />
        <StatCard
          title="Total Cases"
          value={stats?.cases?.total || 0}
          icon={<FileText className="w-6 h-6" />}
          color="accent-purple"
          subtitle={`${stats?.cases?.completed || 0} completed`}
        />
        <StatCard
          title="Verifications"
          value={stats?.verifications?.total || 0}
          icon={<Shield className="w-6 h-6" />}
          color="success"
          subtitle={`${stats?.verifications?.approved || 0} approved`}
        />
        <StatCard
          title="Admin Users"
          value={stats?.users?.admins || 0}
          icon={<TrendingUp className="w-6 h-6" />}
          color="warning"
          subtitle="System administrators"
        />
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <QuickActionCard
          title="Manage Users"
          description="View and manage user accounts"
          icon={<Users className="w-8 h-8" />}
          href="/admin/users"
        />
        <QuickActionCard
          title="View Cases"
          description="Browse all system cases"
          icon={<FileText className="w-8 h-8" />}
          href="/admin/cases"
        />
        <QuickActionCard
          title="Security Events"
          description="Monitor security incidents"
          icon={<AlertTriangle className="w-8 h-8" />}
          href="/admin/security"
        />
      </div>
    </div>
  )
}

function StatCard({ title, value, icon, color, subtitle }) {
  const colorClasses = {
    primary: 'text-primary',
    'accent-purple': 'text-accent-purple',
    success: 'text-success',
    warning: 'text-warning',
  }

  return (
    <div className="p-4 bg-neutral-800/50 rounded-lg border border-neutral-700">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-neutral-400">{title}</p>
          <p className="text-3xl font-bold mt-1">{value}</p>
          <p className="text-xs text-neutral-500 mt-1">{subtitle}</p>
        </div>
        <div className={`${colorClasses[color]}`}>
          {icon}
        </div>
      </div>
    </div>
  )
}

function QuickActionCard({ title, description, icon, href }) {
  return (
    <a
      href={href}
      className="block p-4 bg-neutral-800/50 rounded-lg border border-neutral-700 hover:border-primary transition-colors"
    >
      <div className="flex items-start gap-3">
        <div className="text-primary">
          {icon}
        </div>
        <div>
          <h3 className="font-semibold">{title}</h3>
          <p className="text-sm text-neutral-400 mt-1">{description}</p>
        </div>
      </div>
    </a>
  )
}
