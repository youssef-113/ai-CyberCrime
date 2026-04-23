import { Link, useLocation } from 'react-router-dom'
import { Globe, Menu } from 'lucide-react'
import { useTheme } from '../../context/ThemeContext'
import { getTranslation } from '../../utils/translations'
import { motion } from 'framer-motion'

export default function Header({ onMenuToggle }) {
  const { language, setLanguage, isRtl } = useTheme()
  const location = useLocation()
  
  const t = (key) => getTranslation(language, key)

  const isLanding = location.pathname === '/'

  return (
    <header className="sticky top-0 z-40 border-b border-neutral-800/50 bg-neutral-950/80 backdrop-blur-xl">
      <div className="flex items-center justify-between h-16 px-4 lg:px-6">
        <div className="flex items-center gap-3">
          {!isLanding && (
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
        </div>
      </div>
    </header>
  )
}
