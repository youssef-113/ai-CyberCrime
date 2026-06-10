import { Link } from 'react-router-dom'
import { motion, useScroll, useTransform } from 'framer-motion'
import {
  Shield, Upload, Cpu, Scale, FileText, MessageSquare,
  ArrowRight, CheckCircle, Zap, ChevronRight,
  Lock, Clock, Eye, Award, Star, Users, Check
} from 'lucide-react'
import { useRef, useState, useEffect } from 'react'
import Button from '../components/ui/Button'
import { useTheme } from '../context/ThemeContext'
import { useAuth } from '../context/AuthContext'
import { getTranslation } from '../utils/translations'
import { useNavigate } from 'react-router-dom'

/* ─── Data ─────────────────────────────────────────────────────────────── */

const typingPhraseKeys = [
  'landing.typing1',
  'landing.typing2',
  'landing.typing3',
  'landing.typing4',
  'landing.typing5',
  'landing.typing6'
]

const trustIndicatorKeys = [
  'landing.trust1',
  'landing.trust4',
  'landing.trust5'
]

const newStatsKeys = [
  { valueKey: 'landing.stat1Value', labelKey: 'landing.stat1Label' },
  { valueKey: 'landing.stat2Value', labelKey: 'landing.stat2Label' },
  { valueKey: 'landing.stat3Value', labelKey: 'landing.stat3Label' },
  { valueKey: 'landing.stat4Value', labelKey: 'landing.stat4Label' }
]

const pipeline = [
  {
    num: '01',
    icon: Upload,
    titleKey: 'landing.uploadEvidence',
    descKey: 'landing.uploadEvidenceDesc',
    color: 'from-emerald-500/20 to-emerald-500/5',
    border: 'border-emerald-500/30',
    glow: 'shadow-emerald-500/20',
  },
  {
    num: '02',
    icon: Cpu,
    titleKey: 'landing.aiAnalysis',
    descKey: 'landing.aiAnalysisDesc',
    color: 'from-cyan-500/20 to-cyan-500/5',
    border: 'border-cyan-500/30',
    glow: 'shadow-cyan-500/20',
  },
  {
    num: '03',
    icon: Scale,
    titleKey: 'landing.legalRag',
    descKey: 'landing.legalRagDesc',
    color: 'from-violet-500/20 to-violet-500/5',
    border: 'border-violet-500/30',
    glow: 'shadow-violet-500/20',
  },
  {
    num: '04',
    icon: Shield,
    titleKey: 'landing.multiAgent',
    descKey: 'landing.multiAgentDesc',
    color: 'from-amber-500/20 to-amber-500/5',
    border: 'border-amber-500/30',
    glow: 'shadow-amber-500/20',
  },
  {
    num: '05',
    icon: FileText,
    titleKey: 'landing.pdfReport',
    descKey: 'landing.pdfReportDesc',
    color: 'from-rose-500/20 to-rose-500/5',
    border: 'border-rose-500/30',
    glow: 'shadow-rose-500/20',
  },
  {
    num: '06',
    icon: MessageSquare,
    titleKey: 'landing.legalChatbot',
    descKey: 'landing.legalChatbotDesc',
    color: 'from-emerald-500/20 to-teal-500/5',
    border: 'border-teal-500/30',
    glow: 'shadow-teal-500/20',
  },
]

const trustItems = [
  { icon: Lock, labelKey: 'landing.zeroHallucination' },
  { icon: Clock, labelKey: 'landing.autoDeletion' },
  { icon: Scale, labelKey: 'landing.lawCoverage' },
]

const stats = [
  { value: '175', label: 'Law 175/2018', sublabel: 'Egyptian Cybercrime Law' },
  { value: '6', label: 'AI Stages', sublabel: 'Full pipeline' },
  { value: '0', label: 'Hallucinations', sublabel: 'Multi-agent verified' },
  { value: '24h', label: 'Auto-Deletion', sublabel: 'Evidence security' },
]

/* ─── Animation Variants ─────────────────────────────────────────────── */

const fadeUp = {
  hidden: { opacity: 0, y: 28 },
  visible: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.08, duration: 0.55, ease: [0.22, 1, 0.36, 1] },
  }),
}

const fadeIn = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.6 } },
}

/* ─── Component ──────────────────────────────────────────────────────── */

function TypingAnimation({ phraseKeys, language, getTranslation }) {
  const [currentPhraseIndex, setCurrentPhraseIndex] = useState(0)
  const [currentText, setCurrentText] = useState('')
  const [isDeleting, setIsDeleting] = useState(false)
  const [showCursor, setShowCursor] = useState(true)

  // Get translated phrases
  const phrases = phraseKeys.map(key => getTranslation(language, key))

  useEffect(() => {
    const timer = setTimeout(() => {
      setShowCursor(!showCursor)
    }, 500)
    return () => clearTimeout(timer)
  }, [showCursor])

  useEffect(() => {
    const phrase = phrases[currentPhraseIndex]
    const speed = isDeleting ? 30 : 80

    const timer = setTimeout(() => {
      if (!isDeleting && currentText === phrase) {
        setTimeout(() => setIsDeleting(true), 2000)
        return
      }

      if (isDeleting && currentText === '') {
        setIsDeleting(false)
        setCurrentPhraseIndex((prev) => (prev + 1) % phrases.length)
        return
      }

      setCurrentText((prev) =>
        isDeleting ? phrase.substring(0, prev.length - 1) : phrase.substring(0, prev.length + 1)
      )
    }, speed)

    return () => clearTimeout(timer)
  }, [currentText, isDeleting, currentPhraseIndex, phrases])

  return (
    <span className="bg-gradient-to-r from-[#00D4FF] to-[#00F5FF] bg-clip-text text-transparent font-semibold">
      {currentText}
      <span className="animate-pulse text-[#00F5FF]">|</span>
    </span>
  )
}

export default function LandingPage() {
  const { language, isRtl } = useTheme()
  const { loginAsDemo } = useAuth()
  const navigate = useNavigate()
  const heroRef = useRef(null)

  const { scrollYProgress } = useScroll({ target: heroRef, offset: ['start start', 'end start'] })
  const bgY = useTransform(scrollYProgress, [0, 1], ['0%', '25%'])
  const bgOpacity = useTransform(scrollYProgress, [0, 0.8], [1, 0])

  const t = (key) => getTranslation(language, key)

  return (
    <div className="relative z-10 overflow-x-hidden" dir={isRtl ? 'rtl' : 'ltr'}>

      {/* ═══════════════════ HERO ═══════════════════ */}
      <section ref={heroRef} className="relative min-h-screen flex items-center overflow-hidden" style={{ backgroundColor: '#050816' }}>

        {/* Parallax Background */}
        <motion.div
          style={{ y: bgY, opacity: bgOpacity }}
          className="absolute inset-0 pointer-events-none"
        >
          <img
            src="/images/hero cybercrime.png"
            alt=""
            aria-hidden="true"
            className="w-full h-full object-cover scale-110"
          />
          {/* Multi-layer gradient vignette */}
          <div className="absolute inset-0 bg-gradient-to-b from-[#050816]/90 via-[#050816]/70 to-[#050816]" />
          <div className="absolute inset-0 bg-gradient-to-r from-[#050816]/95 via-transparent to-[#050816]/95" />
        </motion.div>

        {/* Animated grid overlay */}
        <div className="absolute inset-0 perspective-grid opacity-[0.04] pointer-events-none" />

        {/* Radial glow spots */}
        <div
          className="absolute top-1/4 left-1/4 w-[600px] h-[600px] pointer-events-none"
          style={{
            background: 'radial-gradient(ellipse at center, rgba(0,212,255,0.08) 0%, transparent 70%)',
          }}
        />
        <div
          className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] pointer-events-none"
          style={{
            background: 'radial-gradient(ellipse at center, rgba(123,97,255,0.08) 0%, transparent 70%)',
          }}
        />

        {/* Hero content - 50/50 layout */}
        <div className="container mx-auto px-6 lg:px-12 relative py-20">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            {/* Left side - Text content */}
            <div className="space-y-8">
              {/* Badge pill */}
              <motion.div
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                custom={0}
                className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full
                           border border-[#00D4FF]/40 bg-[#00D4FF]/10 backdrop-blur-sm
                           text-[#00D4FF] text-xs font-mono font-semibold tracking-widest uppercase"
              >
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00D4FF] opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00D4FF]" />
                </span>
                Egyptian Cybercrime Law · AI Platform
              </motion.div>

              {/* H1 */}
              <motion.h1
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                custom={1}
                className="text-4xl md:text-5xl lg:text-6xl font-bold leading-[1.1] mb-4"
                style={{ fontFamily: 'Oswald, sans-serif', color: '#FFFFFF' }}
              >
                {t('landing.newHeroTitle')}
              </motion.h1>

              {/* Typing Animation */}
              <motion.div
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                custom={2}
                className="text-2xl md:text-3xl font-semibold mb-6"
                style={{ textShadow: '0 0 20px rgba(0,212,255,0.5)' }}
              >
                <TypingAnimation phraseKeys={typingPhraseKeys} language={language} getTranslation={getTranslation} />
              </motion.div>

              {/* Description */}
              <motion.p
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                custom={3}
                className="text-lg text-neutral-300 leading-relaxed mb-8"
              >
                {t('landing.newHeroDescription')}
              </motion.p>

              {/* CTAs */}
              <motion.div
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                custom={4}
                className="flex flex-wrap items-center gap-4"
              >
                <Link to="/signup" id="hero-cta-signup">
                  <Button
                    size="lg"
                    className="gap-2 px-8 py-4 text-base font-semibold rounded-full
                               bg-gradient-to-r from-[#00D4FF] to-[#00F5FF] text-[#050816]
                               hover:scale-105 transition-transform duration-200
                               shadow-[0_0_30px_rgba(0,212,255,0.4)]"
                  >
                    {t('auth.getStarted')}
                    <ArrowRight className={`w-5 h-5 ${isRtl ? 'rotate-180' : ''}`} />
                  </Button>
                </Link>

                <Link to="/dashboard" id="hero-cta-explore">
                  <Button
                    variant="secondary"
                    size="lg"
                    className="gap-2 px-8 py-4 text-base font-semibold rounded-full
                               bg-white/5 border border-[#00F5FF] text-[#00F5FF]
                               hover:bg-white/10 hover:shadow-[0_0_20px_rgba(0,245,255,0.3)]
                               transition-all duration-200"
                    onClick={() => {
                      loginAsDemo()
                      setTimeout(() => navigate('/dashboard'), 1500)
                    }}
                  >
                    {t('landing.explorePlatform')}
                  </Button>
                </Link>
              </motion.div>

              {/* Trust Indicators */}
              <motion.div
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                custom={5}
                className="pt-6 space-y-3"
              >
                {trustIndicatorKeys.map((key, index) => (
                  <div key={index} className="flex items-center gap-3 text-neutral-300">
                    <Check className="w-5 h-5 text-[#00F5FF]" />
                    <span className="text-sm">{t(key)}</span>
                  </div>
                ))}
              </motion.div>
            </div>

            {/* Right side - Hero Image */}
            <motion.div
              variants={fadeIn}
              initial="hidden"
              animate="visible"
              transition={{ delay: 0.3 }}
              className="relative hidden lg:block"
            >
            </motion.div>
          </div>

          {/* Stats row */}
          <motion.div
            variants={fadeIn}
            initial="hidden"
            animate="visible"
            transition={{ delay: 0.6 }}
            className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-6"
          >
            {newStatsKeys.map((stat, i) => (
              <motion.div
                key={stat.labelKey}
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                custom={6 + i}
                className="text-center p-4 rounded-xl bg-white/5 border border-[#00D4FF]/20 backdrop-blur-sm"
              >
                <div className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-[#00D4FF] to-[#00F5FF] bg-clip-text text-transparent mb-2">
                  {t(stat.valueKey)}
                </div>
                <div className="text-xs text-neutral-300">{t(stat.labelKey)}</div>
              </motion.div>
            ))}
          </motion.div>

          {/* Scroll indicator */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.2 }}
            className="flex justify-center mt-16"
          >
            <motion.div
              animate={{ y: [0, 8, 0] }}
              transition={{ repeat: Infinity, duration: 1.8, ease: 'easeInOut' }}
              className="w-6 h-10 border-2 border-[#00D4FF]/50 rounded-full flex items-start justify-center p-1.5"
            >
              <div className="w-1 h-2.5 bg-[#00D4FF] rounded-full" />
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* ═══════════════════ PIPELINE ═══════════════════ */}
      <section id="how-it-works" className="relative py-28" style={{ backgroundColor: '#050816' }}>
        {/* Section bg accent */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="perspective-grid opacity-[0.04] h-full" />
          <div
            className="absolute bottom-0 left-0 w-full h-48"
            style={{ background: 'linear-gradient(to top, rgba(0,212,255,0.04), transparent)' }}
          />
        </div>

        <div className="container mx-auto px-6 lg:px-12 relative">
          {/* Section header */}
          <motion.div
            variants={fadeUp}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <span className="inline-block px-3 py-1 mb-4 text-xs font-mono font-semibold uppercase tracking-widest
                             text-[#00D4FF] border border-[#00D4FF]/30 rounded-full bg-[#00D4FF]/5">
              {t('landing.howItWorks')}
            </span>
            <h2 className="text-3xl md:text-5xl font-bold mb-4 text-white"
                style={{ fontFamily: 'Oswald, sans-serif' }}>
              {t('landing.pipelineTitle')}
            </h2>
            <p className="text-neutral-300 max-w-xl mx-auto text-base">
              {t('landing.howItWorksSubtitle')}
            </p>
          </motion.div>

          {/* Cards grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {pipeline.map((step, i) => {
              const Icon = step.icon
              return (
                <motion.div
                  key={step.num}
                  variants={fadeUp}
                  initial="hidden"
                  whileInView="visible"
                  viewport={{ once: true }}
                  custom={i}
                  className="relative group rounded-2xl border border-[#00D4FF]/20 bg-white/5
                               backdrop-blur-xl p-7 hover:shadow-lg hover:shadow-[#00D4FF]/20
                               transition-all duration-300 hover:-translate-y-1 cursor-default overflow-hidden"
                >
                  {/* Step number watermark */}
                  <div className="absolute top-4 right-5 text-6xl font-black text-white/[0.04]
                                  group-hover:text-white/[0.07] transition-colors select-none"
                       style={{ fontFamily: 'Oswald, sans-serif' }}>
                    {step.num}
                  </div>

                  <div className="relative">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-10 h-10 rounded-xl bg-[#00D4FF]/10 border border-[#00D4FF]/30
                                      flex items-center justify-center shrink-0">
                        <Icon className="w-5 h-5 text-[#00D4FF]" />
                      </div>
                      <span className="text-xs font-mono text-neutral-500 font-semibold tracking-widest">
                        STEP {step.num}
                      </span>
                    </div>
                    <h3 className="text-base font-semibold text-white mb-2 leading-snug">
                      {t(step.titleKey)}
                    </h3>
                    <p className="text-sm text-neutral-400 leading-relaxed">
                      {t(step.descKey)}
                    </p>
                  </div>
                </motion.div>
              )
            })}
          </div>
        </div>
      </section>

      {/* ═══════════════════ ARCHITECTURE / PROOF ═══════════════════ */}


      {/* ═══════════════════ TRUST STRIP ═══════════════════ */}
      <section className="py-12 border-y border-neutral-800/50">
        <div className="container mx-auto px-6 lg:px-12">
          <motion.div
            variants={fadeIn}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            className="flex flex-wrap items-center justify-center gap-8 md:gap-16"
          >
            {[
              { icon: Lock, text: 'End-to-End Encrypted' },
              { icon: Eye, text: 'GDPR Compliant' },
              { icon: Award, text: 'Egyptian Law Certified' },
              { icon: Users, text: 'Multi-Tenant SaaS' },
              { icon: Star, text: 'Zero Hallucination AI' },
            ].map(({ icon: Icon, text }) => (
              <div key={text} className="flex items-center gap-2.5 text-neutral-500 hover:text-neutral-300 transition-colors duration-200">
                <Icon className="w-4 h-4 text-primary/70" />
                <span className="text-xs font-semibold tracking-wide">{text}</span>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* ═══════════════════ CTA ═══════════════════ */}
      <section className="py-28 relative overflow-hidden">
        {/* Glow bg */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: 'radial-gradient(ellipse 80% 60% at 50% 50%, rgba(0,189,125,0.07) 0%, transparent 70%)',
          }}
        />
        <div className="absolute inset-0 perspective-grid opacity-[0.04] pointer-events-none" />

        <div className="container mx-auto px-6 lg:px-12 relative">
          <motion.div
            variants={fadeUp}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            className="max-w-3xl mx-auto text-center"
          >
            <span className="inline-block px-3 py-1 mb-6 text-xs font-mono font-semibold uppercase
                             tracking-widest text-primary border border-primary/30 rounded-full bg-primary/5">
              Get Started
            </span>
            <h2 className="text-4xl md:text-6xl font-display font-bold mb-6 leading-tight"
                style={{ fontFamily: 'Oswald, sans-serif' }}>
              {t('landing.readyToBuild')}
            </h2>
            <p className="text-neutral-400 text-base md:text-lg max-w-xl mx-auto mb-10 leading-relaxed">
              {t('landing.readyToBuildDesc')}
            </p>

            <div className="flex flex-wrap items-center justify-center gap-4">
              <Link to="/signup" id="cta-final-signup">
                <Button
                  size="lg"
                  className="gap-2 px-10 py-4 text-base font-semibold shadow-glow
                             hover:scale-[1.04] transition-transform duration-200"
                >
                  {t('auth.getStarted')}
                  <ArrowRight className={`w-5 h-5 ${isRtl ? 'rotate-180' : ''}`} />
                </Button>
              </Link>
              <Button
                variant="outline"
                size="lg"
                id="cta-final-demo"
                className="gap-2 px-10 py-4 text-base hover:scale-[1.02] transition-transform duration-200"
                onClick={() => {
                  loginAsDemo()
                  setTimeout(() => navigate('/dashboard'), 1500)
                }}
              >
                <Zap className="w-5 h-5 text-warning" />
                {t('auth.tryDemo')}
              </Button>
            </div>

            <p className="mt-5 text-xs text-neutral-600 font-mono">
              No credit card required · Instant access
            </p>
          </motion.div>
        </div>
      </section>

      {/* ═══════════════════ FOOTER ═══════════════════ */}
      <footer className="border-t border-neutral-800/60">
        <div className="container mx-auto px-6 lg:px-12 py-10">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            {/* Brand */}
            <div className="flex items-center gap-3">
              <img
                src="/images/logo cybercrime.png"
                alt="Cybercrime AI Logo"
                className="w-8 h-8 rounded-lg object-cover"
              />
              <div>
                <div className="text-sm font-semibold text-neutral-200 leading-none">
                  Cybercrime AI
                </div>
                <div className="text-[10px] text-neutral-600 font-mono mt-0.5">
                  AI Evidence Builder
                </div>
              </div>
            </div>

            {/* Nav links */}
            <nav className="flex items-center gap-6 text-xs text-neutral-500">
              <Link to="/login" className="hover:text-neutral-300 transition-colors">Sign In</Link>
              <Link to="/signup" className="hover:text-neutral-300 transition-colors">Sign Up</Link>
              <span>·</span>
              <span>{t('landing.footerLaw')}</span>
            </nav>
          </div>
        </div>
      </footer>

    </div>
  )
}
