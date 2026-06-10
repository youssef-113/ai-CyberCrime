import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Shield, Eye, EyeOff, ArrowRight, ArrowLeft, Zap } from 'lucide-react'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { getTranslation } from '../utils/translations'
import { showError } from '../utils/alertConfig'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const { login, loginAsDemo, loading } = useAuth()
  const { language, isRtl } = useTheme()
  const navigate = useNavigate()

  const t = (key) => getTranslation(language, key)

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!email.trim()) {
      showError('❌ Validation Error', 'Please enter your email address')
      return
    }
    if (!password) {
      showError('❌ Validation Error', 'Please enter your password')
      return
    }

    try {
      await login(email, password)
      // Delay navigation to let the alert be visible
      setTimeout(() => navigate('/dashboard'), 2500)
    } catch (err) {
      // Error alert is already shown by ActionAlerts.authError in AuthContext
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center relative" dir={isRtl ? 'rtl' : 'ltr'}>
      {/* Background — same banner image + gradient overlay as LandingPage hero */}
      <div className="absolute inset-0 overflow-hidden">
        <img
          src="/images/hero cybercrime.png"
          alt=""
          className="w-full h-full object-cover opacity-20"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-neutral-950/60 via-neutral-950/90 to-neutral-950" />
        <div className="absolute inset-0 perspective-grid opacity-30" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary/5 rounded-full blur-3xl" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="relative z-10 w-full max-w-md mx-4"
      >
        <div className="perspective-card-elevated p-8 md:p-10">
          {/* Back to Home */}
          <motion.div
            initial={{ opacity: 0, x: isRtl ? 10 : -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2, duration: 0.4 }}
          >
            <Link
              to="/"
              className="inline-flex items-center gap-1.5 text-sm text-neutral-400 hover:text-primary transition-colors mb-6 group"
            >
              <ArrowLeft className={`w-4 h-4 transition-transform group-hover:${isRtl ? 'translate-x-1' : '-translate-x-1'}`} />
              {t('auth.backToHome')}
            </Link>
          </motion.div>

          {/* Logo + Header */}
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.15, duration: 0.5 }}
            className="text-center mb-8"
          >
            <Link to="/" className="inline-flex items-center gap-3 mb-6">
              <img
                src="/images/logo cybercrime.png"
                alt="Cybercrime AI Logo"
                className="w-12 h-12 rounded-xl object-cover shadow-glow"
              />
              <span className="text-xl font-display font-bold gradient-text">Cybercrime AI</span>
            </Link>
            <h1 className="text-2xl md:text-3xl font-display font-bold mb-2">
              {t('auth.welcomeBack')}
            </h1>
            <p className="text-neutral-400 text-sm">
              {t('auth.loginSubtitle')}
            </p>
          </motion.div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.4 }}
            >
              <Input
                label={t('auth.email')}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
              />
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.4 }}
              className="relative"
            >
              <Input
                label={t('auth.password')}
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                autoComplete="current-password"
                required
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-9 text-neutral-500 hover:text-primary transition-colors"
                tabIndex={-1}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5, duration: 0.4 }}
            >
              <Button
                type="submit"
                loading={loading}
                className="w-full"
                size="lg"
              >
                {t('auth.signIn')}
                <ArrowRight className={`w-5 h-5 ${isRtl ? 'rotate-180' : ''}`} />
              </Button>
            </motion.div>
          </form>

          {/* Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-neutral-800" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="px-3 bg-neutral-900/90 text-neutral-500">or</span>
            </div>
          </div>

          {/* Demo Mode */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.55, duration: 0.4 }}
            className="space-y-3"
          >
            <Button
              variant="secondary"
              className="w-full gap-2"
              size="lg"
              onClick={() => {
                loginAsDemo()
                setTimeout(() => navigate('/dashboard'), 1500)
              }}
            >
              <Zap className="w-5 h-5 text-warning" />
              {t('auth.tryDemo')}
            </Button>
            <p className="text-neutral-500 text-xs text-center">
              {t('auth.demoHint')}
            </p>
          </motion.div>

          {/* Second Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-neutral-800" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="px-3 bg-neutral-900/90 text-neutral-500">or</span>
            </div>
          </div>

          {/* Switch to Signup */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6, duration: 0.4 }}
            className="text-center"
          >
            <p className="text-neutral-400 text-sm mb-3">
              {t('auth.noAccount')}
            </p>
            <Link to="/signup">
              <Button variant="outline" className="w-full gap-2">
                {t('auth.createAccount')}
                <ArrowRight className={`w-4 h-4 ${isRtl ? 'rotate-180' : ''}`} />
              </Button>
            </Link>
          </motion.div>
        </div>
      </motion.div>
    </div>
  )
}
