import { useState } from 'react'
import { Globe, Shield, Server, Info, RefreshCw, CheckCircle2, XCircle, AlertCircle } from 'lucide-react'
import { Card, CardBody } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Badge from '../components/ui/Badge'
import { useTheme } from '../context/ThemeContext'
import { useHealthCheck } from '../api/hooks'
import { LANGUAGES } from '../utils/constants'
import { getTranslation } from '../utils/translations'
import toast from 'react-hot-toast'

export default function SettingsPage() {
  const { language, setLanguage, isRtl } = useTheme()
  const { health, checkHealth, loading } = useHealthCheck()
  
  const t = (key) => getTranslation(language, key)

  const handleLanguageChange = (code) => {
    setLanguage(code)
    const lang = LANGUAGES.find((l) => l.code === code)
    toast.success(t('settings.languageDesc'))
  }

  const handleTestConnection = async () => {
    try {
      await checkHealth()
      toast.success('API is healthy')
    } catch {
      toast.error('Cannot reach API server')
    }
  }

  const getServiceIcon = (status) => {
    if (status === 'healthy') return <CheckCircle2 className="w-4 h-4 text-success-light" />
    if (status === 'unhealthy') return <XCircle className="w-4 h-4 text-danger-light" />
    return <AlertCircle className="w-4 h-4 text-warning-light" />
  }

  const getServiceBadge = (status) => {
    if (status === 'healthy') return <Badge variant="success">Healthy</Badge>
    if (status === 'unhealthy') return <Badge variant="danger">Unhealthy</Badge>
    return <Badge variant="warning">Unreachable</Badge>
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
