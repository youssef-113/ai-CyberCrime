import { useState } from 'react'
import { Globe, Shield, Info, Database } from 'lucide-react'
import { Card, CardBody } from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import { useTheme } from '../context/ThemeContext'
import { LANGUAGES } from '../utils/constants'
import { getTranslation } from '../utils/translations'
import SystemStatus from '../components/admin/SystemStatus'
import useAlerts from '../hooks/useAlerts'

export default function SettingsPage() {
  const { language, setLanguage, isRtl } = useTheme()
  const alerts = useAlerts()
  
  const t = (key) => getTranslation(language, key)

  const handleLanguageChange = (code) => {
    setLanguage(code)
    const lang = LANGUAGES.find((l) => l.code === code)
    alerts.success(
      '🌐 Language Changed',
      `Interface language has been changed to ${lang.label}`,
      { timer: 2000 }
    )
  }

  return (
    <div className="space-y-6" dir={isRtl ? 'rtl' : 'ltr'}>
      <div>
        <h1 className="section-title">{t('settings.title')}</h1>
        <p className="section-subtitle">{t('settings.subtitle')}</p>
      </div>

      <Card>
        <div className="px-6 py-4 border-b border-neutral-800 flex items-center gap-2">
          <Globe className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold">{t('settings.language')}</h2>
        </div>
        <CardBody>
          <p className="text-sm text-neutral-400 mb-4">
            {t('settings.languageDesc')}
          </p>
          <div className="flex gap-3">
            {LANGUAGES.map((lang) => (
              <button
                key={lang.code}
                onClick={() => handleLanguageChange(lang.code)}
                className={`flex items-center gap-2 px-4 py-3 rounded-lg border transition-all ${
                  language === lang.code
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-neutral-700 bg-neutral-800/50 text-neutral-400 hover:border-neutral-600'
                }`}
              >
                <span className="text-sm font-medium">{lang.label}</span>
                {lang.dir === 'rtl' && <Badge variant="primary">{t('settings.rtl')}</Badge>}
              </button>
            ))}
          </div>
        </CardBody>
      </Card>

      <Card>
        <div className="px-6 py-4 border-b border-neutral-800 flex items-center gap-2">
          <Shield className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold">{t('settings.privacy')}</h2>
        </div>
        <CardBody>
          <ul className="space-y-3 text-sm text-neutral-400">
            <li className="flex items-start gap-2">
              <Badge variant="success">{t('settings.active')}</Badge>
              <span>{t('settings.privacy1')}</span>
            </li>
            <li className="flex items-start gap-2">
              <Badge variant="success">{t('settings.active')}</Badge>
              <span>{t('settings.privacy2')}</span>
            </li>
            <li className="flex items-start gap-2">
              <Badge variant="success">{t('settings.active')}</Badge>
              <span>{t('settings.privacy3')}</span>
            </li>
            <li className="flex items-start gap-2">
              <Badge variant="success">{t('settings.active')}</Badge>
              <span>{t('settings.privacy4')}</span>
            </li>
          </ul>
        </CardBody>
      </Card>

      <Card>
        <div className="px-6 py-4 border-b border-neutral-800 flex items-center gap-2">
          <Database className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold">System Status</h2>
        </div>
        <CardBody>
          <SystemStatus />
        </CardBody>
      </Card>

      <Card>
        <div className="px-6 py-4 border-b border-neutral-800 flex items-center gap-2">
          <Info className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold">{t('settings.about')}</h2>
        </div>
        <CardBody>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-neutral-500">{t('settings.version')}</p>
              <p className="font-medium">1.0.0</p>
            </div>
            <div>
              <p className="text-neutral-500">{t('settings.status')}</p>
              <Badge variant="primary">{t('settings.trlStatus')}</Badge>
            </div>
            <div>
              <p className="text-neutral-500">{t('settings.legalFramework')}</p>
              <p className="font-medium">{t('settings.law175')}</p>
            </div>
            <div>
              <p className="text-neutral-500">{t('settings.pipeline')}</p>
              <p className="font-medium">{t('settings.ragPipeline')}</p>
            </div>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}
