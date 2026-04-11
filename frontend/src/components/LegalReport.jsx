import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { FileText, Scale, AlertCircle, CheckCircle, Download } from 'lucide-react'

function LegalReport({ evidence, onGenerate }) {
  const [generating, setGenerating] = useState(true)
  const [report, setReport] = useState(null)

  useEffect(() => {
    const generateReport = async () => {
      await new Promise(resolve => setTimeout(resolve, 3000))
      
      setReport({
        caseType: 'Blackmail & Extortion (Article 176)',
        strength: 87,
        events: 3,
        articles: 5,
        summary: 'Based on the evidence provided, this case involves systematic blackmail and extortion attempts through digital communications. The perpetrator has made explicit threats and financial demands, which constitutes a violation of Egyptian Penal Code Article 176.',
        legalReferences: [
          {
            article: 'Article 176',
            title: 'Blackmail and Threats',
            description: 'Anyone who threatens others with exposing or attributing to them matters that would punish them or contempt them, in order to force them to do or abstain from doing something, shall be punished with imprisonment.'
          },
          {
            article: 'Article 325',
            title: 'Extortion',
            description: 'Anyone who obtains money or documents by using threats or violence shall be punished with imprisonment and a fine.'
          },
          {
            article: 'Article 182',
            title: 'Cybercrime Provisions',
            description: 'The provisions of this law apply to any crime committed through the use of information networks or information technology tools.'
          }
        ],
        missingEvidence: [
          'Recorded audio conversations (if available)',
          'Witness statements',
          'Police report number (if previously filed)',
          'Bank transaction records'
        ]
      })
      setGenerating(false)
    }

    generateReport()
  }, [evidence])

  if (generating) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-cyber-blue">Generating Legal Report...</h2>
        <div className="flex flex-col items-center justify-center py-12">
          <motion.div
            className="w-20 h-20 border-4 border-cyber-purple border-t-transparent rounded-full"
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
          />
          <p className="mt-6 text-gray-300">AI is retrieving relevant legal articles and structuring your report...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-cyber-blue">Legal Report Generated</h2>

      <div className="glass-card p-6">
        <div className="flex items-center space-x-3 mb-6">
          <Scale className="w-8 h-8 text-cyber-blue" />
          <h3 className="text-xl font-semibold">Case Classification</h3>
        </div>
        
        <div className="bg-gradient-to-r from-cyber-blue/20 to-cyber-purple/20 p-4 rounded-lg mb-6">
          <p className="text-lg font-semibold">{report.caseType}</p>
        </div>

        <div className="mb-6">
          <h4 className="font-semibold mb-3">Case Summary</h4>
          <p className="text-gray-300 leading-relaxed">{report.summary}</p>
        </div>

        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="text-center p-4 bg-white/5 rounded-lg">
            <p className="text-3xl font-bold text-cyber-blue">{report.strength}%</p>
            <p className="text-sm text-gray-400">Evidence Strength</p>
          </div>
          <div className="text-center p-4 bg-white/5 rounded-lg">
            <p className="text-3xl font-bold text-cyber-purple">{report.events}</p>
            <p className="text-sm text-gray-400">Timeline Events</p>
          </div>
          <div className="text-center p-4 bg-white/5 rounded-lg">
            <p className="text-3xl font-bold text-cyber-pink">{report.articles}</p>
            <p className="text-sm text-gray-400">Legal Articles</p>
          </div>
        </div>
      </div>

      <div className="glass-card p-6">
        <div className="flex items-center space-x-3 mb-6">
          <FileText className="w-8 h-8 text-cyber-purple" />
          <h3 className="text-xl font-semibold">Relevant Legal Articles</h3>
        </div>
        
        <div className="space-y-4">
          {report.legalReferences.map((ref, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className="bg-white/5 p-4 rounded-lg border-l-4 border-cyber-purple"
            >
              <h4 className="font-semibold text-cyber-purple mb-2">
                {ref.article}: {ref.title}
              </h4>
              <p className="text-gray-300 text-sm">{ref.description}</p>
            </motion.div>
          ))}
        </div>
      </div>

      <div className="glass-card p-6 border-l-4 border-yellow-500">
        <div className="flex items-center space-x-3 mb-4">
          <AlertCircle className="w-6 h-6 text-yellow-500" />
          <h3 className="text-lg font-semibold text-yellow-500">Suggestions for Stronger Evidence</h3>
        </div>
        
        <ul className="space-y-2">
          {report.missingEvidence.map((item, index) => (
            <li key={index} className="flex items-start space-x-2 text-gray-300">
              <span className="text-yellow-500 mt-1">-</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex justify-center space-x-4 mt-6">
        <button
          onClick={() => onGenerate(report)}
          className="cyber-button flex items-center space-x-2 text-lg px-8 py-4"
        >
          <CheckCircle className="w-5 h-5" />
          <span>Review & Finalize</span>
        </button>
      </div>
    </div>
  )
}

export default LegalReport
