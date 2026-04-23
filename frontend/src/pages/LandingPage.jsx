import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Shield, Upload, Cpu, Scale, FileText, MessageSquare, ArrowRight, CheckCircle } from 'lucide-react'
import Button from '../components/ui/Button'

const features = [
  {
    icon: Upload,
    title: 'Upload Evidence',
    description: 'Upload screenshots, images, and PDFs of digital crime evidence.',
  },
  {
    icon: Cpu,
    title: 'AI Analysis',
    description: 'OCR extracts text, entities, and builds a chronological timeline automatically.',
  },
  {
    icon: Scale,
    title: 'Legal RAG',
    description: 'Retrieves relevant Egyptian law articles (Law 175/2018, Penal Code) via semantic search.',
  },
  {
    icon: Shield,
    title: 'Multi-Agent Verification',
    description: 'Attacker & Judge agents verify every claim against evidence — zero hallucination.',
  },
  {
    icon: FileText,
    title: 'PDF Report',
    description: 'Generates a ready-to-submit complaint report with timeline, articles, and score.',
  },
  {
    icon: MessageSquare,
    title: 'Legal Chatbot',
    description: 'Ask questions about your case and get answers grounded in retrieved law articles.',
  },
]

const steps = [
  { num: '01', label: 'Upload' },
  { num: '02', label: 'Analyze' },
  { num: '03', label: 'Verify' },
  { num: '04', label: 'Report' },
]

export default function LandingPage() {
  return (
    <div className="relative z-10">
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
              Transform Digital Evidence{' '}
              <span className="gradient-text">Into Legal Power</span>
            </h1>
            <p className="text-lg md:text-xl text-neutral-300 max-w-2xl mb-8 leading-relaxed">
              AI-powered system that structures, verifies, and prepares legally supported
              complaint reports under Egyptian cybercrime law. Upload evidence. Get results.
            </p>
            <div className="flex flex-wrap gap-4">
              <Link to="/analyze">
                <Button size="lg" className="gap-2">
                  Start New Case
                  <ArrowRight className="w-5 h-5" />
                </Button>
              </Link>
              <Link to="/dashboard">
                <Button variant="outline" size="lg">
                  View Dashboard
                </Button>
              </Link>
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
                <p className="text-sm text-neutral-400 mt-2">{step.label}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      <section className="container mx-auto px-6 py-16">
        <h2 className="section-title mb-2">How It Works</h2>
        <p className="section-subtitle mb-10">Six-stage AI pipeline with zero-hallucination guarantees</p>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, i) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
              className="perspective-card p-6"
            >
              <feature.icon className="w-10 h-10 text-primary mb-4" />
              <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
              <p className="text-sm text-neutral-400 leading-relaxed">{feature.description}</p>
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
                Enterprise-Grade Architecture
              </h2>
              <p className="text-neutral-400 mb-6 leading-relaxed">
                Built on a microservices architecture with OCR processing, multi-agent verification,
                and RAG-powered legal retrieval. Every claim is traceable to evidence.
              </p>
              <ul className="space-y-3 text-sm text-neutral-300">
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-primary shrink-0" />
                  Zero hallucination via multi-agent verification
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-primary shrink-0" />
                  24-hour auto-deletion of sensitive evidence
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-primary shrink-0" />
                  Egyptian Law 175/2018 + Penal Code coverage
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
              Ready to Build Your Case?
            </h2>
            <p className="text-neutral-400 max-w-xl mx-auto mb-8">
              Upload your evidence and let AI transform it into a structured, legally supported
              complaint report ready for submission to Egyptian authorities.
            </p>
            <Link to="/analyze">
              <Button size="lg" className="gap-2">
                Get Started
                <ArrowRight className="w-5 h-5" />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <footer className="container mx-auto px-6 py-8 border-t border-neutral-800/50">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-neutral-500">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-primary" />
            <span>Cybercrime AI — AI Cybercrime Evidence Builder</span>
          </div>
          <p>Egyptian Law No. 175/2018 · Built for Digital Justice</p>
        </div>
      </footer>
    </div>
  )
}
