import { useState, useMemo, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Eye, EyeOff, ArrowRight, ArrowLeft, Check, X, Zap } from 'lucide-react'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { getTranslation } from '../utils/translations'
import { validatePasswordStrength } from '../utils/validators'
import { showError, closeAlert } from '../utils/alertConfig'
import Swal from 'sweetalert2'

const PASSWORD_RULES = [
  { key: 'length', label: 'At least 8 characters', test: (p) => p.length >= 8 },
  { key: 'uppercase', label: 'One uppercase letter', test: (p) => /[A-Z]/.test(p) },
  { key: 'lowercase', label: 'One lowercase letter', test: (p) => /[a-z]/.test(p) },
  { key: 'digit', label: 'One digit', test: (p) => /\d/.test(p) },
  { key: 'special', label: 'One special character', test: (p) => /[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`]/.test(p) },
]

export default function SignupPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const { register, loginAsDemo, loading } = useAuth()
  const { language, isRtl } = useTheme()
  const navigate = useNavigate()

  const t = (key) => getTranslation(language, key)

  // Force-clean any leftover SweetAlert overlays on mount
  useEffect(() => {
    Swal.close()
    closeAlert()
    document.querySelectorAll('.swal2-container, .swal2-backdrop-show').forEach(el => el.remove())
  }, [])

  const passwordValidation = useMemo(() => {
    return validatePasswordStrength(password)
  }, [password])

  const passwordRules = useMemo(() => {
    return PASSWORD_RULES.map((rule) => ({
      ...rule,
      passed: rule.test(password),
    }))
  }, [password])

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!email.trim()) {
      showError('❌ Validation Error', 'Please enter your email address')
      return
    }
    if (!passwordValidation.valid) {
      showError('❌ Weak Password', 'Your password does not meet the security requirements')
      return
    }
    if (password !== confirmPassword) {
      showError('❌ Password Mismatch', 'The passwords you entered do not match')
      return
    }

    try {
      await register(email, password, fullName || null)
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
              {t('auth.createAccount')}
            </h1>
            <p className="text-neutral-400 text-sm">
              {t('auth.signupSubtitle')}
            </p>
          </motion.div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25, duration: 0.4 }}
            >
              <Input
                label={t('auth.fullName')}
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Joe"
                autoComplete="name"
              />
            </motion.div>

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
              transition={{ delay: 0.35, duration: 0.4 }}
              className="relative"
            >
              <Input
                label={t('auth.password')}
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Create a strong password"
                autoComplete="new-password"
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

            {/* Password Strength Indicator */}
            {password && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="space-y-2 overflow-hidden"
              >
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((level) => (
                    <div
                      key={level}
                      className={`h-1 flex-1 rounded-full transition-colors duration-300 ${
                        passwordRules.filter((r) => r.passed).length >= level
                          ? level <= 2 ? 'bg-danger-light' : level <= 4 ? 'bg-warning-light' : 'bg-success-light'
                          : 'bg-neutral-700'
                      }`}
                    />
                  ))}
                </div>
                <div className="space-y-1">
                  {passwordRules.map((rule) => (
                    <div key={rule.key} className="flex items-center gap-2 text-xs">
                      {rule.passed ? (
                        <Check className="w-3 h-3 text-success-light shrink-0" />
                      ) : (
                        <X className="w-3 h-3 text-neutral-600 shrink-0" />
                      )}
                      <span className={rule.passed ? 'text-success-light' : 'text-neutral-500'}>
                        {rule.label}
                      </span>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4, duration: 0.4 }}
            >
              <Input
                label={t('auth.confirmPassword')}
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter your password"
                autoComplete="new-password"
                required
                error={confirmPassword && password !== confirmPassword ? 'Passwords do not match' : undefined}
              />
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.45, duration: 0.4 }}
            >
              <Button
                type="submit"
                loading={loading}
                className="w-full"
                size="lg"
                disabled={!passwordValidation.valid || password !== confirmPassword}
              >
                {t('auth.createAccount')}
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
            transition={{ delay: 0.5, duration: 0.4 }}
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

          {/* Switch to Login */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.55, duration: 0.4 }}
            className="text-center"
          >
            <p className="text-neutral-400 text-sm mb-3">
              {t('auth.hasAccount')}
            </p>
            <Link to="/login">
              <Button variant="outline" className="w-full gap-2">
                {t('auth.signIn')}
                <ArrowRight className={`w-4 h-4 ${isRtl ? 'rotate-180' : ''}`} />
              </Button>
            </Link>
          </motion.div>
        </div>
      </motion.div>
    </div>
  )
}
