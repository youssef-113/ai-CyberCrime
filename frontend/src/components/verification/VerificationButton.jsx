import { useState } from 'react'
import { Button } from '../ui/Button'
import { triggerCaseVerification } from '../../api/endpoints'

/**
 * VerificationButton - Triggers verification for a case
 * 
 * Usage:
 * <VerificationButton 
 *   caseId={caseId}
 *   caseData={{ evidence_text, entities, classification, articles, evidence_blocks }}
 *   onVerificationComplete={(result) => console.log(result)}
 *   onVerificationError={(error) => console.error(error)}
 * />
 */
export function VerificationButton({
  caseId,
  caseData,
  onVerificationComplete,
  onVerificationError,
  variant = 'primary',
  size = 'md',
  className = '',
  children = 'Verify Evidence',
}) {
  const [isVerifying, setIsVerifying] = useState(false)
  const [progress, setProgress] = useState(null)

  const handleVerify = async () => {
    if (!caseData || !caseId) {
      onVerificationError?.(new Error('Case data or case ID missing'))
      return
    }

    setIsVerifying(true)
    setProgress('Initializing verification...')

    try {
      // Simulate progress updates (since verification takes time)
      const progressInterval = setInterval(() => {
        const messages = [
          'Analyzing evidence...',
          'Running attacker challenges...',
          'Evaluating legal grounding...',
          'Building timeline...',
          'Finalizing assessment...',
        ]
        const randomMsg = messages[Math.floor(Math.random() * messages.length)]
        setProgress(randomMsg)
      }, 3000)

      const result = await triggerCaseVerification(caseId, caseData)

      clearInterval(progressInterval)
      setProgress('Complete!')
      onVerificationComplete?.(result)
    } catch (error) {
      console.error('Verification failed:', error)
      onVerificationError?.(error)
    } finally {
      setIsVerifying(false)
      setProgress(null)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <Button
        onClick={handleVerify}
        disabled={isVerifying}
        variant={variant}
        size={size}
        className={className}
        icon={isVerifying ? <SpinnerIcon /> : <ShieldCheckIcon />}
      >
        {isVerifying ? 'Verifying...' : children}
      </Button>
      
      {isVerifying && progress && (
        <div className="flex items-center gap-2 text-sm text-gray-600">
          <LoadingSpinner size="sm" />
          <span>{progress}</span>
        </div>
      )}
    </div>
  )
}

function SpinnerIcon() {
  return (
    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  )
}

function ShieldCheckIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  )
}

function LoadingSpinner({ size = 'md' }) {
  const sizeClasses = {
    sm: 'h-3 w-3',
    md: 'h-4 w-4',
    lg: 'h-6 w-6',
  }
  
  return (
    <svg className={`animate-spin ${sizeClasses[size]}`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  )
}
