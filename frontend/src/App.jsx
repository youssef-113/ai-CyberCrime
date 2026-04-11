import { useState } from 'react'
import { motion } from 'framer-motion'
import { Shield, Upload, FileText, AlertTriangle, CheckCircle, ArrowRight } from 'lucide-react'
import Scene3D from './components/Scene3D'
import FileUpload from './components/FileUpload'
import EvidenceTimeline from './components/EvidenceTimeline'
import LegalReport from './components/LegalReport'

function App() {
  const [currentStep, setCurrentStep] = useState(0)
  const [evidence, setEvidence] = useState([])
  const [report, setReport] = useState(null)

  const steps = [
    { title: 'Upload Evidence', icon: Upload, description: 'Upload screenshots and documents' },
    { title: 'Analyze Evidence', icon: AlertTriangle, description: 'AI extracts key information' },
    { title: 'Generate Report', icon: FileText, description: 'Create legal complaint report' },
    { title: 'Review & Submit', icon: CheckCircle, description: 'Final verification' }
  ]

  const handleFileUpload = (files) => {
    setEvidence(files)
    setCurrentStep(1)
  }

  const handleAnalysisComplete = (analysisResult) => {
    setCurrentStep(2)
  }

  const handleReportGenerated = (reportData) => {
    setReport(reportData)
    setCurrentStep(3)
  }

  return (
    <div className="min-h-screen bg-cyber-dark relative overflow-hidden">
      <Scene3D />
      
      <div className="relative z-10">
        <nav className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <motion.div 
              className="flex items-center space-x-3"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
            >
              <Shield className="w-10 h-10 text-cyber-blue" />
              <span className="text-2xl font-bold bg-gradient-to-r from-cyber-blue to-cyber-purple bg-clip-text text-transparent">
                AI Cybercrime Evidence Builder
              </span>
            </motion.div>
          </div>
        </nav>

        <main className="container mx-auto px-6 py-8">
          <motion.div 
            className="mb-12"
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <h1 className="text-5xl font-bold mb-4 bg-gradient-to-r from-cyber-blue via-cyber-purple to-cyber-pink bg-clip-text text-transparent">
              Transform Digital Evidence Into Legal Power
            </h1>
            <p className="text-xl text-gray-300 max-w-3xl">
              Upload your evidence and let AI structure it into a professional, legally-supported complaint report ready for submission.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
            {steps.map((step, index) => (
              <motion.div
                key={index}
                className={`glass-card p-6 transition-all duration-300 ${
                  index === currentStep ? 'border-cyber-blue shadow-lg shadow-cyber-blue/20' : 'opacity-60'
                }`}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
              >
                <step.icon className={`w-8 h-8 mb-4 ${index === currentStep ? 'text-cyber-blue' : 'text-gray-400'}`} />
                <h3 className="font-semibold mb-2">{step.title}</h3>
                <p className="text-sm text-gray-400">{step.description}</p>
                {index < currentStep && (
                  <CheckCircle className="w-6 h-6 text-cyber-green mt-4" />
                )}
              </motion.div>
            ))}
          </div>

          <motion.div
            className="glass-card p-8"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.3 }}
          >
            {currentStep === 0 && (
              <FileUpload onUpload={handleFileUpload} />
            )}

            {currentStep === 1 && (
              <EvidenceTimeline 
                evidence={evidence} 
                onComplete={handleAnalysisComplete}
              />
            )}

            {currentStep === 2 && (
              <LegalReport 
                evidence={evidence}
                onGenerate={handleReportGenerated}
              />
            )}

            {currentStep === 3 && report && (
              <div className="space-y-6">
                <div className="text-center">
                  <CheckCircle className="w-16 h-16 text-cyber-green mx-auto mb-4" />
                  <h2 className="text-3xl font-bold mb-2">Report Ready!</h2>
                  <p className="text-gray-300">Your legal complaint report has been generated successfully.</p>
                </div>
                
                <div className="bg-white/5 rounded-lg p-6 space-y-4">
                  <h3 className="text-xl font-semibold text-cyber-blue">Report Summary</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-gray-400 text-sm">Case Type</p>
                      <p className="font-semibold">{report.caseType}</p>
                    </div>
                    <div>
                      <p className="text-gray-400 text-sm">Evidence Strength</p>
                      <p className="font-semibold text-cyber-green">{report.strength}%</p>
                    </div>
                    <div>
                      <p className="text-gray-400 text-sm">Timeline Events</p>
                      <p className="font-semibold">{report.events}</p>
                    </div>
                    <div>
                      <p className="text-gray-400 text-sm">Legal Articles</p>
                      <p className="font-semibold">{report.articles}</p>
                    </div>
                  </div>
                </div>

                <div className="flex justify-center space-x-4">
                  <button className="cyber-button flex items-center space-x-2">
                    <span>Download PDF</span>
                    <ArrowRight className="w-5 h-5" />
                  </button>
                  <button 
                    className="px-6 py-3 border border-white/20 rounded-lg hover:bg-white/10 transition-all"
                    onClick={() => setCurrentStep(0)}
                  >
                    Start New Case
                  </button>
                </div>
              </div>
            )}
          </motion.div>
        </main>
      </div>
    </div>
  )
}

export default App
