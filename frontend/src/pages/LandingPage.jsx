import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Shield, Upload, Cpu, Scale, FileText, MessageSquare, ArrowRight, CheckCircle, Zap } from 'lucide-react'
import Button from '../components/ui/Button'
import { useTheme } from '../context/ThemeContext'
import { useAuth } from '../context/AuthContext'
import { getTranslation } from '../utils/translations'
import { useNavigate } from 'react-router-dom'
import { toastSuccess } from '../components/ui/Alert'

const features = [
  {
    icon: Upload,
    titleKey: 'landing.uploadEvidence',
    descriptionKey: 'landing.uploadEvidenceDesc',
  },
  {
    icon: Cpu,
    titleKey: 'landing.aiAnalysis',
    descriptionKey: 'landing.aiAnalysisDesc',
  },
  {
    icon: Scale,
    titleKey: 'landing.legalRag',
    descriptionKey: 'landing.legalRagDesc',
  },
  {
    icon: Shield,
    titleKey: 'landing.multiAgent',
    descriptionKey: 'landing.multiAgentDesc',
  },
  {
    icon: FileText,
    titleKey: 'landing.pdfReport',
    descriptionKey: 'landing.pdfReportDesc',
  },
  {
    icon: MessageSquare,
    titleKey: 'landing.legalChatbot',
    descriptionKey: 'landing.legalChatbotDesc',
  },
]

const steps = [
  { num: '01', labelKey: 'landing.uploadEvidence' },
  { num: '02', labelKey: 'landing.aiAnalysis' },
  { num: '03', labelKey: 'landing.multiAgent' },
  { num: '04', labelKey: 'landing.pdfReport' },
]

export default function LandingPage() {
  const { language, isRtl } = useTheme()
  const { loginAsDemo } = useAuth()
  const navigate = useNavigate()
  
  const t = (key) => getTranslation(language, key)

  return (
    <div className="relative z-10" dir={isRtl ? 'rtl' : 'ltr'}>
      {/* Hero Section with Banner Image */}
      <section className="relative">
        {/* Background Banner Image */}
        <div className="absolute inset-0 overflow-hidden">
          <img
            src="/images/a-cinematic-high-tech-startup-poster-fea_LgTTcXLOTAuD74ES1Dq5mA_TGuuJNbMRGusz7UyZ_TJnw.jpeg"
            alt="Cybersecurity Banner"
            className="w-full h-full object-cover opacity-30"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-neutral-950/50 via-neutral-950/80 to-neutral-950" />
        </div>

        <div className="container mx-auto px-6 pt-12 pb-20 relative">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="max-w-4xl"
          >
            {/* Logo */}
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.1, duration: 0.5 }}
              className="mb-8"
            >
              <img
                src="/images/a-cinematic-high-tech-startup-poster-fea_LgTTcXLOTAuD74ES1Dq5mA_TGuuJNbMRGusz7UyZ_TJnw.jpeg"
                alt="Cybercrime AI Logo"
                className="w-24 h-24 object-cover rounded-xl shadow-glow"
              />
            </motion.div>

            <h1 className="text-4xl md:text-6xl font-display font-bold mb-6 leading-tight">
              {t('landing.heroTitle')}{' '}
              <span className="gradient-text">{t('landing.heroTitleHighlight')}</span>
            </h1>
            <p className="text-lg md:text-xl text-neutral-300 max-w-2xl mb-8 leading-relaxed">
              {t('landing.heroSubtitle')}
            </p>
            <div className="flex flex-wrap gap-4">
              <Link to="/signup">
                <Button size="lg" className="gap-2">
                  {t('auth.getStarted')}
                  <ArrowRight className={`w-5 h-5 ${isRtl ? 'rotate-180' : ''}`} />
                </Button>
              </Link>
              <Link to="/login">
                <Button variant="outline" size="lg">
                  {t('auth.signIn')}
                </Button>
              </Link>
              <Button
                variant="secondary"
                size="lg"
                className="gap-2"
                onClick={() => {
                  loginAsDemo()
                  toastSuccess(t('auth.loginSuccess'))
                  navigate('/dashboard')
                }}
              >
                <Zap className="w-5 h-5 text-warning" />
                {t('auth.tryDemo')}
              </Button>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3, duration: 0.6 }}
            className="mt-16 grid grid-cols-2 md:grid-cols-4 gap-4"
          >
            {steps.map((step, i) => (
              <motion.div
                key={step.num}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 + i * 0.1 }}
                className="perspective-card-glass p-6 text-center backdrop-blur-sm"
              >
                <span className="text-3xl font-display font-bold gradient-text">{step.num}</span>
                <p className="text-sm text-neutral-400 mt-2">{t(step.labelKey)}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      <section className="container mx-auto px-6 py-16">
        <h2 className="section-title mb-2">{t('landing.howItWorks')}</h2>
        <p className="section-subtitle mb-10">{t('landing.howItWorksSubtitle')}</p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, i) => (
            <motion.div
              key={feature.titleKey}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
              className="perspective-card p-6"
            >
              <feature.icon className="w-10 h-10 text-primary mb-4" />
              <h3 className="text-lg font-semibold mb-2">{t(feature.titleKey)}</h3>
              <p className="text-sm text-neutral-400 leading-relaxed">{t(feature.descriptionKey)}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Architecture Banner Section */}
      <section className="container mx-auto px-6 py-16">
        <div className="perspective-card-elevated overflow-hidden">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-0">
            <div className="p-8 md:p-12 flex flex-col justify-center">
              <h2 className="text-2xl md:text-3xl font-display font-bold mb-4">
                {t('landing.architectureTitle')}
              </h2>
              <p className="text-neutral-400 mb-6 leading-relaxed">
                {t('landing.architectureDesc')}
              </p>
              <ul className="space-y-3 text-sm text-neutral-300">
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-primary shrink-0" />
                  {t('landing.zeroHallucination')}
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-primary shrink-0" />
                  {t('landing.autoDeletion')}
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-primary shrink-0" />
                  {t('landing.lawCoverage')}
                </li>
              </ul>
            </div>
            <div className="relative h-110 lg:h-auto min-h-[500px]">
              <img
                src="/images/a-sleek-corporate-poster-design-featurin_FOcW3B5jRbKDVIj4LNrtYw_ng88QlxlTCCU7uzM4BL7Fg.jpeg"
                alt="Cybercrime AI Architecture"
                className="absolute inset-0 w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-r from-neutral-950 via-neutral-950/50 to-transparent lg:bg-gradient-to-l" />
            </div>
          </div>
        </div>
      </section>

      <section className="container mx-auto px-6 py-16">
        <div className="perspective-card-elevated p-8 md:p-12 text-center relative overflow-hidden">
          {/* Background Pattern */}
          <div className="absolute inset-0 perspective-grid opacity-50" />
          <div className="relative">
            <h2 className="text-2xl md:text-3xl font-display font-bold mb-4">
              {t('landing.readyToBuild')}
            </h2>
            <p className="text-neutral-400 max-w-xl mx-auto mb-8">
              {t('landing.readyToBuildDesc')}
            </p>
            <Link to="/signup">
              <Button size="lg" className="gap-2">
                {t('auth.getStarted')}
                <ArrowRight className={`w-5 h-5 ${isRtl ? 'rotate-180' : ''}`} />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <footer className="container mx-auto px-6 py-8 border-t border-neutral-800/50">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-neutral-500">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-primary" />
            <span>{t('landing.footer')}</span>
          </div>
          <p>{t('landing.footerLaw')}</p>
        </div>
      </footer>
    </div>
  )
}
