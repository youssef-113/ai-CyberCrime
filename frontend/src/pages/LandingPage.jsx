import { Link } from 'react-router-dom'
import { motion, useScroll, useTransform } from 'framer-motion'
import {
  Shield, Upload, Cpu, Scale, FileText, MessageSquare,
  ArrowRight, CheckCircle, Zap, ChevronRight,
  Lock, Clock, Eye, Award, Star, Users
} from 'lucide-react'
import { useRef } from 'react'
import Button from '../components/ui/Button'
import { useTheme } from '../context/ThemeContext'
import { useAuth } from '../context/AuthContext'
import { getTranslation } from '../utils/translations'
import { useNavigate } from 'react-router-dom'
import { toastSuccess } from '../components/ui/Alert'

/* ─── Data ─────────────────────────────────────────────────────────────── */

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
      <section ref={heroRef} className="relative min-h-screen flex flex-col justify-center overflow-hidden">

        {/* Parallax Background */}
        <motion.div
          style={{ y: bgY, opacity: bgOpacity }}
          className="absolute inset-0 pointer-events-none"
        >
          <img
            src="/images/hero-bg.png"
            alt=""
            aria-hidden="true"
            className="w-full h-full object-cover scale-110"
          />
          {/* Multi-layer gradient vignette */}
          <div className="absolute inset-0 bg-gradient-to-b from-neutral-950/60 via-neutral-950/40 to-neutral-950" />
          <div className="absolute inset-0 bg-gradient-to-r from-neutral-950/80 via-transparent to-neutral-950/80" />
        </motion.div>

        {/* Animated grid overlay */}
        <div className="absolute inset-0 perspective-grid opacity-[0.04] pointer-events-none" />

        {/* Radial glow spot */}
        <div
          className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] pointer-events-none"
          style={{
            background: 'radial-gradient(ellipse at center, rgba(0,189,125,0.12) 0%, transparent 70%)',
          }}
        />

        {/* Hero content */}
        <div className="container mx-auto px-6 lg:px-12 relative pt-24 pb-28">
          <div className="max-w-5xl mx-auto text-center">

            {/* Badge pill */}
            <motion.div
              variants={fadeUp}
              initial="hidden"
              animate="visible"
              custom={0}
              className="inline-flex items-center gap-2 px-4 py-1.5 mb-8 rounded-full
                         border border-primary/40 bg-primary/10 backdrop-blur-sm
                         text-primary text-xs font-mono font-semibold tracking-widest uppercase"
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
              </span>
              Egyptian Cybercrime Law · AI Platform
            </motion.div>

            {/* H1 */}
            <motion.h1
              variants={fadeUp}
              initial="hidden"
              animate="visible"
              custom={1}
              className="text-5xl md:text-7xl font-display font-bold leading-[1.05] tracking-tight mb-6"
              style={{ fontFamily: 'Oswald, sans-serif' }}
            >
              {t('landing.heroTitle')}{' '}
              <span className="gradient-text">{t('landing.heroTitleHighlight')}</span>
            </motion.h1>

            {/* Subtitle */}
            <motion.p
              variants={fadeUp}
              initial="hidden"
              animate="visible"
              custom={2}
              className="text-lg md:text-xl text-neutral-300 max-w-2xl mx-auto mb-10 leading-relaxed"
            >
              {t('landing.heroSubtitle')}
            </motion.p>

            {/* CTAs */}
            <motion.div
              variants={fadeUp}
              initial="hidden"
              animate="visible"
              custom={3}
              className="flex flex-wrap items-center justify-center gap-4"
            >
              <Link to="/signup" id="hero-cta-signup">
                <Button
                  size="lg"
                  className="gap-2 px-8 py-4 text-base font-semibold shadow-glow
                             hover:scale-[1.04] transition-transform duration-200"
                >
                  {t('auth.getStarted')}
                  <ArrowRight className={`w-5 h-5 ${isRtl ? 'rotate-180' : ''}`} />
                </Button>
              </Link>

              <Button
                variant="secondary"
                size="lg"
                id="hero-cta-demo"
                className="gap-2 px-8 py-4 text-base font-semibold border border-neutral-700
                           hover:border-primary/40 hover:scale-[1.02] transition-all duration-200"
                onClick={() => {
                  loginAsDemo()
                  toastSuccess(t('auth.loginSuccess'))
                  navigate('/dashboard')
                }}
              >
                <Zap className="w-5 h-5 text-warning" />
                {t('auth.tryDemo')}
              </Button>

              <Link to="/login" id="hero-cta-signin">
                <Button variant="ghost" size="lg" className="text-neutral-400 hover:text-white px-4 py-4">
                  {t('auth.signIn')}
                  <ChevronRight className={`w-4 h-4 ml-1 ${isRtl ? 'rotate-180' : ''}`} />
                </Button>
              </Link>
            </motion.div>

            {/* Trust micro-text */}
            <motion.p
              variants={fadeUp}
              initial="hidden"
              animate="visible"
              custom={4}
              className="mt-5 text-xs text-neutral-500 font-mono"
            >
              {t('auth.demoHint')}
            </motion.p>
          </div>

          {/* Stats row */}
          <motion.div
            variants={fadeIn}
            initial="hidden"
            animate="visible"
            transition={{ delay: 0.6 }}
            className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto"
          >
            {stats.map((s, i) => (
              <motion.div
                key={s.label}
                variants={fadeUp}
                initial="hidden"
                animate="visible"
                custom={5 + i}
                className="perspective-card-glass rounded-2xl p-5 text-center group hover:border-primary/40 transition-all duration-300"
              >
                <div className="text-3xl md:text-4xl font-display font-bold gradient-text" style={{ fontFamily: 'Oswald, sans-serif' }}>
                  {s.value}
                </div>
                <div className="text-xs font-semibold text-neutral-300 mt-1">{s.label}</div>
                <div className="text-[10px] text-neutral-600 mt-0.5 font-mono uppercase tracking-wider">{s.sublabel}</div>
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
              className="w-6 h-10 border-2 border-neutral-700 rounded-full flex items-start justify-center p-1.5"
            >
              <div className="w-1 h-2.5 bg-primary rounded-full" />
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* ═══════════════════ PIPELINE ═══════════════════ */}
      <section id="how-it-works" className="relative py-28">
        {/* Section bg accent */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="perspective-grid opacity-[0.035] h-full" />
          <div
            className="absolute bottom-0 left-0 w-full h-48"
            style={{ background: 'linear-gradient(to top, rgba(0,189,125,0.04), transparent)' }}
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
                             text-primary border border-primary/30 rounded-full bg-primary/5">
              {t('landing.howItWorks')}
            </span>
            <h2 className="text-3xl md:text-5xl font-display font-bold mb-4"
                style={{ fontFamily: 'Oswald, sans-serif' }}>
              Six-Stage AI Pipeline
            </h2>
            <p className="section-subtitle max-w-xl mx-auto text-base">
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
                  className={`relative group rounded-2xl border ${step.border} bg-gradient-to-br ${step.color}
                               backdrop-blur-xl p-7 hover:shadow-lg ${step.glow}
                               transition-all duration-300 hover:-translate-y-1 cursor-default overflow-hidden`}
                >
                  {/* Step number watermark */}
                  <div className="absolute top-4 right-5 text-6xl font-display font-black text-white/[0.04]
                                  group-hover:text-white/[0.07] transition-colors select-none"
                       style={{ fontFamily: 'Oswald, sans-serif' }}>
                    {step.num}
                  </div>

                  <div className="relative">
                    <div className="flex items-center gap-3 mb-4">
                      <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10
                                      flex items-center justify-center shrink-0">
                        <Icon className="w-5 h-5 text-primary" />
                      </div>
                      <span className="text-xs font-mono text-neutral-500 font-semibold tracking-widest">
                        STEP {step.num}
                      </span>
                    </div>
                    <h3 className="text-base font-semibold text-neutral-100 mb-2 leading-snug">
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
      <section className="py-24">
        <div className="container mx-auto px-6 lg:px-12">
          <div className="perspective-card-elevated rounded-3xl overflow-hidden">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-0">

              {/* Text side */}
              <div className="p-10 md:p-14 flex flex-col justify-center order-2 lg:order-1">
                <motion.div
                  variants={fadeUp}
                  initial="hidden"
                  whileInView="visible"
                  viewport={{ once: true }}
                >
                  <span className="inline-block px-3 py-1 mb-5 text-xs font-mono font-semibold uppercase
                                   tracking-widest text-primary border border-primary/30 rounded-full bg-primary/5">
                    Architecture
                  </span>
                  <h2 className="text-3xl md:text-4xl font-display font-bold mb-5 leading-tight"
                      style={{ fontFamily: 'Oswald, sans-serif' }}>
                    {t('landing.architectureTitle')}
                  </h2>
                  <p className="text-neutral-400 mb-8 leading-relaxed text-sm md:text-base">
                    {t('landing.architectureDesc')}
                  </p>

                  <ul className="space-y-4">
                    {trustItems.map(({ icon: Icon, labelKey }, i) => (
                      <motion.li
                        key={labelKey}
                        variants={fadeUp}
                        initial="hidden"
                        whileInView="visible"
                        viewport={{ once: true }}
                        custom={i}
                        className="flex items-start gap-3"
                      >
                        <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/20
                                        flex items-center justify-center shrink-0 mt-0.5">
                          <Icon className="w-4 h-4 text-primary" />
                        </div>
                        <span className="text-sm text-neutral-300 leading-relaxed">{t(labelKey)}</span>
                      </motion.li>
                    ))}
                  </ul>

                  <div className="mt-8">
                    <Link to="/signup" id="arch-cta-signup">
                      <Button size="md" className="gap-2 hover:scale-[1.02] transition-transform duration-200">
                        {t('auth.getStarted')}
                        <ArrowRight className={`w-4 h-4 ${isRtl ? 'rotate-180' : ''}`} />
                      </Button>
                    </Link>
                  </div>
                </motion.div>
              </div>

              {/* Image side */}
              <div className="relative min-h-[400px] lg:min-h-[500px] order-1 lg:order-2 overflow-hidden">
                <img
                  src="/images/a-cinematic-high-tech-startup-poster-fea_LgTTcXLOTAuD74ES1Dq5mA_TGuuJNbMRGusz7UyZ_TJnw.jpeg"
                  alt="Cybercrime AI Architecture"
                  className="absolute inset-0 w-full h-full object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-neutral-900 via-neutral-900/40 to-transparent lg:bg-gradient-to-r lg:from-transparent lg:via-neutral-900/30 lg:to-neutral-900/80" />

                {/* Floating badge */}
                <div className="absolute bottom-6 left-6 right-6 lg:left-8 lg:right-auto lg:bottom-8">
                  <div className="inline-flex items-center gap-2 px-4 py-2 rounded-xl
                                  bg-neutral-900/90 border border-primary/30 backdrop-blur-sm">
                    <Shield className="w-4 h-4 text-primary" />
                    <span className="text-xs font-mono text-neutral-300 font-semibold">
                      Law 175/2018 · Zero Hallucination
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

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
                  toastSuccess(t('auth.loginSuccess'))
                  navigate('/dashboard')
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
              <div className="w-8 h-8 rounded-lg bg-primary/10 border border-primary/30
                              flex items-center justify-center">
                <Shield className="w-4 h-4 text-primary" />
              </div>
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
