import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { Shield, Users, FileText, AlertTriangle, LayoutDashboard } from 'lucide-react'
import AdminDashboard from '../components/admin/AdminDashboard'
import UserManagement from '../components/admin/UserManagement'
import SecurityEvents from '../components/admin/SecurityEvents'
import ProtectedRoute from '../components/ProtectedRoute'

/**
 * Admin page with role-based access control
 * Only accessible to users with admin role
 */
export default function AdminPage() {
  const { currentUser } = useAuth()
  const [activeTab, setActiveTab] = useState('dashboard')

  // Check if user has admin role
  if (currentUser?.role !== 'admin') {
    return (
      <div className="p-6">
        <div className="p-4 bg-danger/10 border border-danger/20 rounded-lg">
          <p className="text-danger-light">Access denied. Admin role required.</p>
        </div>
      </div>
    )
  }

  const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard className="w-5 h-5" /> },
    { id: 'users', label: 'Users', icon: <Users className="w-5 h-5" /> },
    { id: 'security', label: 'Security', icon: <Shield className="w-5 h-5" /> },
  ]

  return (
    <div className="min-h-screen bg-neutral-900">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="border-b border-neutral-800">
          <div className="px-6 py-4">
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Shield className="w-8 h-8 text-primary" />
              Admin Console
            </h1>
          </div>

          {/* Tabs */}
          <div className="px-6">
            <nav className="flex gap-1">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                    activeTab === tab.id
                      ? 'bg-primary text-white'
                      : 'text-neutral-400 hover:bg-neutral-800'
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>
        </div>

        {/* Content */}
        <div className="p-6">
          {activeTab === 'dashboard' && <AdminDashboard />}
          {activeTab === 'users' && <UserManagement />}
          {activeTab === 'security' && <SecurityEvents />}
        </div>
      </div>
    </div>
  )
}
