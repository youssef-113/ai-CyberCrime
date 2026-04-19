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
      <section className="container mx-auto px-6 pt-12 pb-20">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="max-w-4xl"
        >
          <h1 className="text-4xl md:text-6xl font-display font-bold mb-6 leading-tight">
            Transform Digital Evidence{' '}
            <span className="gradient-text">Into Legal Power</span>
          </h1>
          <p className="text-lg md:text-xl text-neutral-400 max-w-2xl mb-8 leading-relaxed">
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
              className="perspective-card-glass p-6 text-center"
            >
              <span className="text-3xl font-display font-bold gradient-text">{step.num}</span>
              <p className="text-sm text-neutral-400 mt-2">{step.label}</p>
            </motion.div>
          ))}
        </motion.div>
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

      <section className="container mx-auto px-6 py-16">
        <div className="perspective-card-elevated p-8 md:p-12 text-center">
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
      </section>

      <footer className="container mx-auto px-6 py-8 border-t border-neutral-800/50">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-neutral-500">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-primary" />
            <span>ACEB — AI Cybercrime Evidence Builder</span>
          </div>
          <p>Egyptian Law No. 175/2018 · Built for Digital Justice</p>
        </div>
      </footer>
    </div>
  )
}
