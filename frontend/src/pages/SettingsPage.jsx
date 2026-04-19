import { Globe, Shield, Server, Info } from 'lucide-react'
import { Card, CardBody } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import Badge from '../components/ui/Badge'
import { useTheme } from '../context/ThemeContext'
import { LANGUAGES } from '../utils/constants'
import toast from 'react-hot-toast'

export default function SettingsPage() {
  const { language, setLanguage, isRtl } = useTheme()

  const handleLanguageChange = (code) => {
    setLanguage(code)
    const lang = LANGUAGES.find((l) => l.code === code)
    toast.success(`Language changed to ${lang?.label}`)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="section-title">Settings</h1>
        <p className="section-subtitle">Configure your preferences</p>
      </div>

      <Card>
        <div className="px-6 py-4 border-b border-neutral-800 flex items-center gap-2">
          <Globe className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold">Language</h2>
        </div>
        <CardBody>
          <p className="text-sm text-neutral-400 mb-4">
            Select your preferred language. Arabic enables RTL layout.
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
                {lang.dir === 'rtl' && <Badge variant="primary">RTL</Badge>}
              </button>
            ))}
          </div>
        </CardBody>
      </Card>

      <Card>
        <div className="px-6 py-4 border-b border-neutral-800 flex items-center gap-2">
          <Server className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold">API Configuration</h2>
        </div>
        <CardBody className="space-y-4">
          <Input
            label="API Base URL"
            id="api-url"
            value={import.meta.env.VITE_API_URL || 'http://localhost:8000'}
            disabled
            hint="Set via VITE_API_URL environment variable"
          />
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={async () => {
                try {
                  const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/health`)
                  if (res.ok) toast.success('API is healthy')
                  else toast.error('API returned error')
                } catch {
                  toast.error('Cannot reach API server')
                }
              }}
            >
              Test Connection
            </Button>
          </div>
        </CardBody>
      </Card>

      <Card>
        <div className="px-6 py-4 border-b border-neutral-800 flex items-center gap-2">
          <Shield className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold">Privacy & Security</h2>
        </div>
        <CardBody>
          <ul className="space-y-3 text-sm text-neutral-400">
            <li className="flex items-start gap-2">
              <Badge variant="success">Active</Badge>
              <span>Case files processed in memory, auto-deleted after 24 hours</span>
            </li>
            <li className="flex items-start gap-2">
              <Badge variant="success">Active</Badge>
              <span>No logging of evidence content — only metadata is stored</span>
            </li>
            <li className="flex items-start gap-2">
              <Badge variant="success">Active</Badge>
              <span>File type validation with magic bytes check</span>
            </li>
            <li className="flex items-start gap-2">
              <Badge variant="success">Active</Badge>
              <span>Rate limiting: 10 requests/minute per IP</span>
            </li>
          </ul>
        </CardBody>
      </Card>

      <Card>
        <div className="px-6 py-4 border-b border-neutral-800 flex items-center gap-2">
          <Info className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold">About</h2>
        </div>
        <CardBody>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-neutral-500">Version</p>
              <p className="font-medium">1.0.0</p>
            </div>
            <div>
              <p className="text-neutral-500">Status</p>
              <Badge variant="primary">TRL 1 → TRL 4</Badge>
            </div>
            <div>
              <p className="text-neutral-500">Legal Framework</p>
              <p className="font-medium">Law No. 175/2018</p>
            </div>
            <div>
              <p className="text-neutral-500">Pipeline</p>
              <p className="font-medium">RAG + Multi-Agent AI</p>
            </div>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}
