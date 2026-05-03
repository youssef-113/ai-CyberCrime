import { useState } from 'react'
import { MainLayout } from '../components/layout/MainLayout'
import { Card } from '../components/ui/Card'
import { Alert } from '../components/ui/Alert'
import {
  VerificationsList,
  VerificationResults,
  VerificationAudit,
} from '../components/verification'
import { getVerificationById } from '../api/endpoints'

/**
 * VerificationsPage - Full page for viewing and managing verification cases
 * 
 * Routes:
 * - /verifications - Shows list of all verifications
 * - /verifications/:id - Shows specific verification details
 */
export default function VerificationsPage() {
  const [selectedVerification, setSelectedVerification] = useState(null)
  const [verificationData, setVerificationData] = useState(null)
  const [auditVerificationId, setAuditVerificationId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleViewVerification = async (verificationId) => {
    setLoading(true)
    setError(null)
    try {
      const data = await getVerificationById(verificationId)
      setVerificationData(data)
      setSelectedVerification(verificationId)
    } catch (err) {
      setError(err.message || 'Failed to load verification details')
    } finally {
      setLoading(false)
    }
  }

  const handleViewAudit = (verificationId) => {
    setAuditVerificationId(verificationId)
  }

  const handleBackToList = () => {
    setSelectedVerification(null)
    setVerificationData(null)
    setError(null)
  }

  return (
    <MainLayout>
      <div className="container mx-auto px-4 py-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Evidence Verification</h1>
          <p className="mt-1 text-gray-600">
            Review AI-verified evidence with full audit trails and legal grounding
          </p>
        </div>

        {error && (
          <Alert variant="error" className="mb-6" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Left sidebar - List of verifications */}
          <div className="lg:col-span-1">
            <VerificationsList
              onViewVerification={handleViewVerification}
              onViewAudit={handleViewAudit}
              className="sticky top-4"
            />
          </div>

          {/* Main content area */}
          <div className="lg:col-span-2">
            {selectedVerification ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Button variant="ghost" onClick={handleBackToList}>
                    ← Back to List
                  </Button>
                  <div className="flex gap-2">
                    <Button variant="outline" onClick={() => handleViewAudit(selectedVerification)}>
                      View Full Audit
                    </Button>
                  </div>
                </div>

                {loading ? (
                  <Card className="p-8">
                    <div className="flex items-center justify-center">
                      <LoadingSpinner />
                      <span className="ml-3 text-gray-600">Loading verification...</span>
                    </div>
                  </Card>
                ) : verificationData ? (
                  <VerificationResults
                    result={verificationData}
                    onViewAudit={handleViewAudit}
                  />
                ) : null}
              </div>
            ) : (
              <Card className="flex h-96 items-center justify-center p-8">
                <div className="text-center">
                  <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-blue-100">
                    <ShieldIcon className="h-8 w-8 text-blue-600" />
                  </div>
                  <h3 className="text-lg font-medium text-gray-900">Select a Verification</h3>
                  <p className="mt-1 max-w-sm text-sm text-gray-500">
                    Choose a verification from the list to view detailed results, audit trails, and
                    legal analysis.
                  </p>
                </div>
              </Card>
            )}
          </div>
        </div>
      </div>

      {/* Audit Modal */}
      <VerificationAudit
        verificationId={auditVerificationId}
        isOpen={!!auditVerificationId}
        onClose={() => setAuditVerificationId(null)}
      />
    </MainLayout>
  )
}

function Button({ children, variant = 'primary', onClick, className = '' }) {
  const variants = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700',
    outline: 'border border-gray-300 text-gray-700 hover:bg-gray-50',
    ghost: 'text-gray-600 hover:bg-gray-100',
  }

  return (
    <button
      onClick={onClick}
      className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${variants[variant]} ${className}`}
    >
      {children}
    </button>
  )
}

function LoadingSpinner() {
  return (
    <svg className="h-6 w-6 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}

function ShieldIcon({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
      />
    </svg>
  )
}
