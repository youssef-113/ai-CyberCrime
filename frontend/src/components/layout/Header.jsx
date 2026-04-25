import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Globe, Menu, LogOut, User } from 'lucide-react'
import { useTheme } from '../../context/ThemeContext'
import { useAuth } from '../../context/AuthContext'
import { getTranslation } from '../../utils/translations'
import { motion } from 'framer-motion'

export default function Header({ onMenuToggle }) {
  const { language, setLanguage, isRtl } = useTheme()
  const { isAuthenticated, isDemo, user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  const t = (key) => getTranslation(language, key)

  const isLanding = location.pathname === '/'
  const isAuthPage = location.pathname === '/login' || location.pathname === '/signup'

  const handleLogout = async () => {
    await logout()
    navigate('/')
  }

  return (
    <header className="sticky top-0 z-40 border-b border-neutral-800/50 bg-neutral-950/80 backdrop-blur-xl">
      <div className="flex items-center justify-between h-16 px-4 lg:px-6">
        <div className="flex items-center gap-3">
          {!isLanding && !isAuthPage && (
            <button
              onClick={onMenuToggle}
              className="btn-ghost btn-icon lg:hidden"
              aria-label="Toggle menu"
            >
              <Menu className="w-5 h-5" />
            </button>
          )}
          <Link to="/" className="flex items-center gap-2.5 group">
            <motion.img
              src="/images/a-cinematic-high-tech-startup-poster-fea_LgTTcXLOTAuD74ES1Dq5mA_TGuuJNbMRGusz7UyZ_TJnw.jpeg"
              alt="Cybercrime AI Logo"
              className="w-10 h-10 rounded-lg object-cover"
              whileHover={{ rotate: 10 }}
              transition={{ type: 'spring', stiffness: 300 }}
            />
            <span className="text-lg font-display font-bold gradient-text hidden sm:inline">
              Cybercrime AI
            </span>
          </Link>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setLanguage(isRtl ? 'en' : 'ar')}
            className="btn-ghost btn-icon flex items-center gap-1.5"
            aria-label={isRtl ? 'Switch to English' : 'التبديل للعربية'}
          >
            <Globe className="w-4 h-4" />
            <span className="text-xs font-medium">{isRtl ? 'EN' : 'عربي'}</span>
          </button>

          {isAuthenticated ? (
            <div className="flex items-center gap-3">
              <div className="hidden sm:flex items-center gap-2 text-sm text-neutral-300">
                <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center">
                  <User className="w-4 h-4 text-primary" />
                </div>
                <span className="max-w-[150px] truncate">{user?.full_name || user?.email}</span>
                {isDemo && (
                  <span className="badge-warning text-[10px] px-1.5 py-0.5">{t('auth.demoBadge')}</span>
                )}
              </div>
              <button
                onClick={handleLogout}
                className="btn-ghost btn-icon"
                aria-label="Logout"
                title="Logout"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            !isAuthPage && (
              <div className="flex items-center gap-2">
                <Link to="/login" className="btn-ghost text-sm px-3 py-1.5">
                  {t('auth.signIn')}
                </Link>
                <Link to="/signup" className="btn-primary text-sm px-3 py-1.5">
                  {t('auth.signUp')}
                </Link>
              </div>
            )
          )}
        </div>
      </div>
    </header>
  )
}
