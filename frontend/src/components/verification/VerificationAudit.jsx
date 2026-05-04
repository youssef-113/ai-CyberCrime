import { useState, useEffect } from 'react'
import { Card, CardBody } from '../ui/Card'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import Modal from '../ui/Modal'
import { getVerificationAudit } from '../../api/endpoints'

/**
 * VerificationAudit - Full round-by-round audit view with attacker/judge details
 * 
 * @param {string} verificationId - The verification case ID to display
 * @param {boolean} isOpen - Modal open state
 * @param {function} onClose - Close handler
 */
export function VerificationAudit({ verificationId, isOpen, onClose }) {
  const [audit, setAudit] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [selectedRound, setSelectedRound] = useState(null)

  useEffect(() => {
    if (isOpen && verificationId) {
      loadAudit()
    }
  }, [isOpen, verificationId])

  const loadAudit = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getVerificationAudit(verificationId)
      setAudit(data)
      if (data.rounds?.length > 0) {
        setSelectedRound(data.rounds[0])
      }
    } catch (err) {
      setError(err.message || 'Failed to load audit')
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl" title="Verification Audit Trail">
      {loading ? (
        <div className="flex h-64 items-center justify-center">
          <LoadingSpinner size="lg" />
          <span className="ml-3 text-gray-600">Loading audit trail...</span>
        </div>
      ) : error ? (
        <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
      ) : audit ? (
        <div className="flex h-[600px] gap-4">
          {/* Left sidebar - Round list */}
          <div className="w-64 flex-shrink-0 overflow-y-auto border-r border-gray-200 pr-4">
            <div className="mb-4">
              <h3 className="font-semibold text-gray-900">Case Summary</h3>
              <div className="mt-2 space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Status:</span>
                  <Badge variant={getStatusColor(audit.audit_summary?.final_status)} size="sm">
                    {audit.audit_summary?.final_status}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Grade:</span>
                  <Badge variant={getGradeColor(audit.audit_summary?.grade)} size="sm">
                    {audit.audit_summary?.grade}
                  </Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Score:</span>
                  <span className="font-medium">{audit.audit_summary?.final_score}/100</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Rounds:</span>
                  <span className="font-medium">{audit.audit_summary?.total_rounds}</span>
                </div>
              </div>
            </div>

            <h4 className="mb-2 font-medium text-gray-900">Rounds</h4>
            <div className="space-y-2">
              {audit.rounds?.map((round, index) => (
                <button
                  key={index}
                  onClick={() => setSelectedRound(round)}
                  className={`w-full rounded-lg border p-3 text-left transition-colors ${
                    selectedRound?.round_num === round.round_num
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-gray-900">Round {round.round_num}</span>
                    <Badge
                      variant={
                        round.judge_status === 'APPROVED'
                          ? 'green'
                          : round.judge_status === 'NEEDS_REVISION'
                          ? 'yellow'
                          : 'red'
                      }
                      size="sm"
                    >
                      {round.judge_status}
                    </Badge>
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    {round.latency_ms ? `${round.latency_ms}ms` : 'No latency data'}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Right panel - Round details */}
          <div className="flex-1 overflow-y-auto">
            {selectedRound ? (
              <RoundDetail round={selectedRound} />
            ) : (
              <div className="flex h-full items-center justify-center text-gray-500">
                Select a round to view details
              </div>
            )}
          </div>
        </div>
      ) : null}
    </Modal>
  )
}

function RoundDetail({ round }) {
  const [activeTab, setActiveTab] = useState('attacker')

  // Parse JSON fields
  const challenges = safeJsonParse(round.attacker_challenges, [])
  const articlesCited = safeJsonParse(round.judge_articles_cited, [])
  const claimsToDrop = safeJsonParse(round.judge_claims_to_drop, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between border-b border-gray-200 pb-3">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Round {round.round_num} Details</h3>
          <p className="text-sm text-gray-500">
            {new Date(round.timestamp).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {round.judge_confidence !== undefined && round.judge_confidence !== null && (
            <div className="text-right">
              <div className="text-xs text-gray-500">Judge Confidence</div>
              <div className="text-lg font-bold text-blue-600">
                {Math.round(round.judge_confidence * 100)}%
              </div>
            </div>
          )}
          <Badge
            variant={
              round.judge_status === 'APPROVED'
                ? 'green'
                : round.judge_status === 'NEEDS_REVISION'
                ? 'yellow'
                : 'red'
            }
            size="lg"
          >
            {round.judge_status}
          </Badge>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        <TabButton active={activeTab === 'attacker'} onClick={() => setActiveTab('attacker')}>
          Attacker
        </TabButton>
        <TabButton active={activeTab === 'judge'} onClick={() => setActiveTab('judge')}>
          Judge
        </TabButton>
        <TabButton active={activeTab === 'technical'} onClick={() => setActiveTab('technical')}>
          Technical
        </TabButton>
      </div>

      {/* Tab Content */}
      <div className="py-2">
        {activeTab === 'attacker' && (
          <div className="space-y-4">
            <div>
              <h4 className="font-medium text-gray-900">Structured Challenges</h4>
              {challenges.length > 0 ? (
                <ul className="mt-2 space-y-2">
                  {challenges.map((challenge, i) => (
                    <li key={i} className="flex items-start gap-2 rounded-lg bg-yellow-50 p-3">
                      <span className="text-yellow-600">⚠</span>
                      <span className="text-sm text-yellow-800">{challenge}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-sm text-gray-500">No structured challenges recorded</p>
              )}
            </div>

            {round.attacker_response && (
              <div>
                <h4 className="font-medium text-gray-900">Attacker LLM Response</h4>
                <div className="mt-2 max-h-48 overflow-y-auto rounded-lg bg-gray-50 p-3">
                  <pre className="whitespace-pre-wrap text-xs text-gray-700">{round.attacker_response}</pre>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'judge' && (
          <div className="space-y-4">
            {articlesCited.length > 0 && (
              <div>
                <h4 className="font-medium text-gray-900">Articles Cited</h4>
                <div className="mt-2 flex flex-wrap gap-2">
                  {articlesCited.map((article, i) => (
                    <Badge key={i} variant="blue">
                      {article}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {claimsToDrop.length > 0 && (
              <div>
                <h4 className="font-medium text-red-700">Claims to Drop</h4>
                <ul className="mt-2 space-y-1">
                  {claimsToDrop.map((claim, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm text-red-600">
                      <span>✗</span>
                      {claim}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {round.judge_response && (
              <div>
                <h4 className="font-medium text-gray-900">Judge LLM Response</h4>
                <div className="mt-2 max-h-64 overflow-y-auto rounded-lg bg-gray-50 p-3">
                  <pre className="whitespace-pre-wrap text-xs text-gray-700">{round.judge_response}</pre>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'technical' && (
          <div className="space-y-3">
            <TechnicalRow label="Round Number" value={round.round_num} />
            <TechnicalRow label="Timestamp" value={round.timestamp} />
            <TechnicalRow label="Latency" value={`${round.latency_ms}ms`} />
            <TechnicalRow label="Case ID" value={round.case_id} />
            <TechnicalRow label="Chat Message ID" value={round.chat_message_id || 'N/A'} />
            <TechnicalRow label="Judge Status" value={round.judge_status} />
            <TechnicalRow
              label="Judge Confidence"
              value={
                round.judge_confidence !== undefined && round.judge_confidence !== null
                  ? `${(round.judge_confidence * 100).toFixed(1)}%`
                  : 'N/A'
              }
            />

            {(round.attacker_prompt || round.judge_prompt) && (
              <div className="mt-4">
                <h4 className="font-medium text-gray-900">LLM Prompts</h4>
                {round.attacker_prompt && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-sm text-blue-600 hover:text-blue-700">
                      View Attacker Prompt ({round.attacker_prompt.length} chars)
                    </summary>
                    <pre className="mt-2 max-h-64 overflow-y-auto rounded-lg bg-gray-100 p-3 text-xs">
                      {round.attacker_prompt}
                    </pre>
                  </details>
                )}
                {round.judge_prompt && (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-sm text-blue-600 hover:text-blue-700">
                      View Judge Prompt ({round.judge_prompt.length} chars)
                    </summary>
                    <pre className="mt-2 max-h-64 overflow-y-auto rounded-lg bg-gray-100 p-3 text-xs">
                      {round.judge_prompt}
                    </pre>
                  </details>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function TabButton({ children, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium transition-colors ${
        active
          ? 'border-b-2 border-blue-600 text-blue-600'
          : 'text-gray-500 hover:text-gray-700'
      }`}
    >
      {children}
    </button>
  )
}

function TechnicalRow({ label, value }) {
  return (
    <div className="flex justify-between border-b border-gray-100 py-2 text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="font-mono text-gray-900">{value}</span>
    </div>
  )
}

function safeJsonParse(str, defaultValue = []) {
  if (!str) return defaultValue
  try {
    return JSON.parse(str)
  } catch {
    return defaultValue
  }
}

function getStatusColor(status) {
  switch (status) {
    case 'APPROVED':
      return 'green'
    case 'NEEDS_REVISION':
      return 'yellow'
    case 'NEEDS_USER_REVIEW':
      return 'red'
    default:
      return 'gray'
  }
}

function getGradeColor(grade) {
  switch (grade) {
    case 'STRONG':
      return 'green'
    case 'MEDIUM':
      return 'yellow'
    case 'WEAK':
      return 'red'
    default:
      return 'gray'
  }
}

function LoadingSpinner({ size = 'md' }) {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6',
    lg: 'h-8 w-8',
  }
  
  return (
    <svg className={`animate-spin ${sizeClasses[size]}`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  )
}
