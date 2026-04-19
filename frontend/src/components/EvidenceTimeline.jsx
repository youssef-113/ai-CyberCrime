import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Clock, Phone, User, DollarSign, FileText, CheckCircle } from 'lucide-react'

function EvidenceTimeline({ evidence, onComplete }) {
  const [analyzing, setAnalyzing] = useState(true)
  const [extractedData, setExtractedData] = useState(null)

  useEffect(() => {
    const analyzeEvidence = async () => {
      await new Promise(resolve => setTimeout(resolve, 3000))
      
      setExtractedData({
        events: [
          {
            id: 1,
            date: '2024-01-15',
            time: '14:30',
            type: 'message',
            description: 'Initial contact received',
            details: {
              sender: '+20 123 456 7890',
              content: 'First threatening message'
            }
          },
          {
            id: 2,
            date: '2024-01-16',
            time: '09:15',
            type: 'financial',
            description: 'Financial demand made',
            details: {
              amount: 'EGP 50,000',
              account: 'Bank of Egypt - **** 4521'
            }
          },
          {
            id: 3,
            date: '2024-01-17',
            time: '16:45',
            type: 'threat',
            description: 'Escalation with explicit threats',
            details: {
              severity: 'high',
              content: 'Direct threats to personal safety'
            }
          }
        ],
        extractedInfo: {
          phoneNumbers: ['+20 123 456 7890', '+20 987 654 3210'],
          names: ['Unknown Perpetrator'],
          bankAccounts: ['Bank of Egypt - **** 4521'],
          financialAmounts: ['EGP 50,000', 'EGP 25,000'],
          dates: ['2024-01-15', '2024-01-16', '2024-01-17']
        },
        caseType: 'Blackmail & Extortion',
        confidenceScore: 87
      })
      setAnalyzing(false)
    }

    analyzeEvidence()
  }, [evidence])

  if (analyzing) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold text-cyber-blue">Analyzing Evidence...</h2>
        <div className="flex flex-col items-center justify-center py-12">
          <motion.div
            className="w-20 h-20 border-4 border-cyber-blue border-t-transparent rounded-full"
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
          />
          <p className="mt-6 text-gray-300">AI is extracting key information from your evidence...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-cyber-blue">Evidence Analysis Complete</h2>
        <div className="flex items-center space-x-2 bg-cyber-green/20 px-4 py-2 rounded-lg">
          <CheckCircle className="w-5 h-5 text-cyber-green" />
          <span className="text-cyber-green font-semibold">
            {extractedData.confidenceScore}% Confidence
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="glass-card p-6">
          <h3 className="font-semibold mb-4 flex items-center space-x-2">
            <User className="w-5 h-5 text-cyber-blue" />
            <span>Identified Names</span>
          </h3>
          <div className="space-y-2">
            {extractedData.extractedInfo.names.map((name, i) => (
              <div key={i} className="bg-white/5 px-3 py-2 rounded">{name}</div>
            ))}
          </div>
        </div>

        <div className="glass-card p-6">
          <h3 className="font-semibold mb-4 flex items-center space-x-2">
            <Phone className="w-5 h-5 text-cyber-purple" />
            <span>Phone Numbers</span>
          </h3>
          <div className="space-y-2">
            {extractedData.extractedInfo.phoneNumbers.map((phone, i) => (
              <div key={i} className="bg-white/5 px-3 py-2 rounded font-mono">{phone}</div>
            ))}
          </div>
        </div>

        <div className="glass-card p-6">
          <h3 className="font-semibold mb-4 flex items-center space-x-2">
            <DollarSign className="w-5 h-5 text-cyber-pink" />
            <span>Financial Amounts</span>
          </h3>
          <div className="space-y-2">
            {extractedData.extractedInfo.financialAmounts.map((amount, i) => (
              <div key={i} className="bg-white/5 px-3 py-2 rounded">{amount}</div>
            ))}
          </div>
        </div>

        <div className="glass-card p-6">
          <h3 className="font-semibold mb-4 flex items-center space-x-2">
            <FileText className="w-5 h-5 text-cyber-green" />
            <span>Bank Accounts</span>
          </h3>
          <div className="space-y-2">
            {extractedData.extractedInfo.bankAccounts.map((account, i) => (
              <div key={i} className="bg-white/5 px-3 py-2 rounded font-mono">{account}</div>
            ))}
          </div>
        </div>
      </div>

      <div className="glass-card p-6">
        <h3 className="font-semibold mb-6 flex items-center space-x-2">
          <Clock className="w-5 h-5 text-cyber-blue" />
          <span>Event Timeline</span>
        </h3>
        
        <div className="relative">
          <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gradient-to-b from-cyber-blue via-cyber-purple to-cyber-pink" />
          
          <div className="space-y-6">
            {extractedData.events.map((event, index) => (
              <motion.div
                key={event.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.2 }}
                className="relative pl-10"
              >
                <div className="absolute left-2 w-5 h-5 rounded-full bg-cyber-dark border-2 border-cyber-blue" />
                
                <div className="glass-card p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-cyber-blue font-mono">
                      {event.date} - {event.time}
                    </span>
                    <span className="px-2 py-1 bg-cyber-blue/20 rounded text-xs text-cyber-blue">
                      {event.type}
                    </span>
                  </div>
                  <h4 className="font-semibold mb-2">{event.description}</h4>
                  <div className="text-sm text-gray-400 space-y-1">
                    {Object.entries(event.details).map(([key, value]) => (
                      <div key={key}>
                        <span className="text-gray-500 capitalize">{key}:</span> {value}
                      </div>
                    ))}
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex justify-center mt-6">
        <button
          onClick={() => onComplete(extractedData)}
          className="cyber-button flex items-center space-x-2 text-lg px-8 py-4"
        >
          <span>Generate Legal Report</span>
        </button>
      </div>
    </div>
  )
}

export default EvidenceTimeline
