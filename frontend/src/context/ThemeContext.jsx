import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { LANGUAGES } from '../utils/constants'

const ThemeContext = createContext(null)

export function ThemeProvider({ children }) {
  const [language, setLanguageState] = useState(() => {
    return localStorage.getItem('Cybercrime AI_lang') || 'en'
  })

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const setLanguage = useCallback((code) => {
    const lang = LANGUAGES.find((l) => l.code === code)
    if (lang) {
      setLanguageState(lang.code)
      localStorage.setItem('Cybercrime AI_lang', lang.code)
      document.documentElement.lang = lang.code
      document.documentElement.dir = lang.dir
    }
  }, [])

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => !prev)
  }, [])

  useEffect(() => {
    const lang = LANGUAGES.find((l) => l.code === language)
    if (lang) {
      document.documentElement.lang = lang.code
      document.documentElement.dir = lang.dir
    }
  }, [language])

  const isRtl = language === 'ar'

  const value = {
    language,
    setLanguage,
    isRtl,
    sidebarCollapsed,
    setSidebarCollapsed,
    toggleSidebar,
  }

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}

export default ThemeContext
