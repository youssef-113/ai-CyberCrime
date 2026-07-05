import { NavLink, useNavigate } from 'react-router-dom'
import { Search, LayoutDashboard, MessageSquare, Settings, FileText, ChevronLeft, ChevronRight, LogOut } from 'lucide-react'
import { useTheme } from '../../context/ThemeContext'
import { useAuth } from '../../context/AuthContext'
import { getTranslation } from '../../utils/translations'
import clsx from 'clsx'

const navItems = [
  { path: '/dashboard', icon: LayoutDashboard, labelKey: 'nav.dashboard' },
  { path: '/analyze', icon: Search, labelKey: 'nav.newCase' },
  { path: '/history', icon: FileText, labelKey: 'nav.caseHistory' },
  { path: '/chatbot', icon: MessageSquare, labelKey: 'nav.legalChat' },
  { path: '/settings', icon: Settings, labelKey: 'nav.settings' },
]

export default function Sidebar() {
  const { sidebarCollapsed, toggleSidebar, isRtl, language } = useTheme()
  const { logout } = useAuth()
  const navigate = useNavigate()
  
  const t = (key) => getTranslation(language, key)

  const handleLogout = async () => {
    try {
      await logout()
      navigate('/login')
    } catch {
      // Logout error is handled in AuthContext
    }
  }

  return (
    <aside
      className={clsx(
        'hidden lg:flex flex-col border-r border-neutral-800/50 bg-neutral-950/50 transition-all duration-300',
        sidebarCollapsed ? 'w-16' : 'w-56'
      )}
    >
      <div className="p-3 border-b border-neutral-800/50">
        <img
          src="/images/logo cybercrime.png"
          alt="Cybercrime AI Logo"
          className={clsx(
            'rounded-lg object-cover mx-auto',
            sidebarCollapsed ? 'w-10 h-10' : 'w-12 h-12'
          )}
        />
      </div>
      <nav className="flex-1 py-4 px-2 space-y-1">
        {navItems.map(({ path, icon: Icon, labelKey }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-neutral-400 hover:bg-neutral-800/50 hover:text-neutral-200'
              )
            }
          >
            <Icon className="w-5 h-5 shrink-0" />
            {!sidebarCollapsed && <span>{t(labelKey)}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="p-2 border-t border-neutral-800/50 space-y-2">
        {/* Logout Button */}
        <button
          onClick={handleLogout}
          className={clsx(
            'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 w-full',
            'text-neutral-400 hover:bg-danger/10 hover:text-danger-light'
          )}
          aria-label={t('auth.signOut')}
          title={t('auth.signOut')}
        >
          <LogOut className="w-5 h-5 shrink-0" />
          {!sidebarCollapsed && <span>{t('auth.signOut')}</span>}
        </button>

        {/* Collapse Toggle */}
        <button
          onClick={toggleSidebar}
          className="btn-ghost btn-icon w-full flex items-center justify-center"
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {sidebarCollapsed ? (
            isRtl ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />
          ) : (
            isRtl ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />
          )}
        </button>
      </div>
    </aside>
  )
}
