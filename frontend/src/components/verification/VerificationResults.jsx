import { useState } from 'react'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Tabs } from '../ui/Tabs'

/**
 * VerificationResults - Displays verification outcome with score, grade, and timeline
 * 
 * @param {Object} result - Verification result from API
 * @param {string} result.case_id
 * @param {string} result.status - APPROVED, NEEDS_REVISION, NEEDS_USER_REVIEW
 * @param {number} result.rounds
 * @param {Array} result.round_details
 * @param {number} result.final_score
 * @param {string} result.grade - STRONG, MEDIUM, WEAK
 * @param {Object} result.timeline
 */
export function VerificationResults({ result, onViewAudit, className = '' }) {
  const [activeTab, setActiveTab] = useState('overview')

  if (!result) {
    return (
      <Card className={`p-6 ${className}`}>
        <div className="text-center text-gray-500">No verification results available</div>
      </Card>
    )
  }

  const {
    case_id,
    status,
    rounds,
    round_details = [],
    final_score = 0,
    score_breakdown = {},
    grade = 'WEAK',
    timeline = {},
  } = result

  const getStatusColor = (status) => {
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

  const getGradeColor = (grade) => {
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

  const scorePercentage = Math.min(100, Math.max(0, final_score))

  return (
    <Card className={`overflow-hidden ${className}`}>
      {/* Header */}
      <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Verification Results</h3>
            <p className="text-sm text-gray-500">Case ID: {case_id}</p>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant={getStatusColor(status)} size="lg">
              {status}
            </Badge>
            {onViewAudit && (
              <Button variant="outline" size="sm" onClick={() => onViewAudit(case_id)}>
                View Audit
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Score Banner */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="text-center">
              <div className="text-3xl font-bold text-white">{final_score}</div>
              <div className="text-xs text-blue-100">Score / 100</div>
            </div>
            <div className="h-12 w-px bg-blue-400" />
            <div>
              <div className="text-sm text-blue-100">Evidence Strength</div>
              <Badge variant={getGradeColor(grade)} size="lg" className="mt-1">
                {grade}
              </Badge>
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm text-blue-100">Rounds Completed</div>
            <div className="text-2xl font-bold text-white">{rounds}</div>
          </div>
        </div>
      </div>

      {/* Tabs Content */}
      <Tabs value={activeTab} onChange={setActiveTab} className="px-6 py-4">
        <Tabs.Tab value="overview" label="Overview" />
        <Tabs.Tab value="rounds" label={`Rounds (${rounds})`} />
        <Tabs.Tab value="timeline" label="Timeline" />
        <Tabs.Tab value="breakdown" label="Score Breakdown" />

        <Tabs.Panel value="overview">
          <OverviewPanel
            status={status}
            grade={grade}
            rounds={rounds}
            timeline={timeline}
          />
        </Tabs.Panel>

        <Tabs.Panel value="rounds">
          <RoundsPanel rounds={round_details} />
        </Tabs.Panel>

        <Tabs.Panel value="timeline">
          <TimelinePanel timeline={timeline} />
        </Tabs.Panel>

        <Tabs.Panel value="breakdown">
          <ScoreBreakdownPanel breakdown={score_breakdown} />
        </Tabs.Panel>
      </Tabs>
    </Card>
  )
}

function OverviewPanel({ status, grade, rounds, timeline }) {
  const statusMessages = {
    APPROVED: 'Evidence has been verified and approved. The claims are well-supported by the evidence and legal articles.',
    NEEDS_REVISION: 'Some claims need revision. Review the attacker challenges and judge feedback to strengthen the evidence.',
    NEEDS_USER_REVIEW: 'The evidence requires manual review. Multiple rounds of verification did not reach a conclusive result.',
  }

  const recommendations = {
    STRONG: [
      'Evidence is ready for legal proceedings',
      'All key claims are supported by evidence',
      'Timeline is coherent and complete',
    ],
    MEDIUM: [
      'Add more specific evidence for unsupported claims',
      'Strengthen timeline with additional dates',
      'Consider clarifying ambiguous statements',
    ],
    WEAK: [
      'Gather additional evidence before proceeding',
      'Address gaps in the timeline',
      'Consult with legal team on next steps',
    ],
  }

  return (
    <div className="space-y-4 py-4">
      <div className="rounded-lg bg-gray-50 p-4">
        <h4 className="font-medium text-gray-900">Assessment</h4>
        <p className="mt-1 text-sm text-gray-600">{statusMessages[status] || statusMessages.NEEDS_USER_REVIEW}</p>
      </div>

      <div className="rounded-lg bg-blue-50 p-4">
        <h4 className="font-medium text-blue-900">Recommendations</h4>
        <ul className="mt-2 space-y-1">
          {(recommendations[grade] || recommendations.WEAK).map((rec, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-blue-800">
              <span className="mt-1">•</span>
              {rec}
            </li>
          ))}
        </ul>
      </div>

      {timeline?.date_coverage !== undefined && (
        <div className="rounded-lg border border-gray-200 p-4">
          <h4 className="font-medium text-gray-900">Timeline Coverage</h4>
          <div className="mt-2 flex items-center gap-3">
            <div className="flex-1">
              <div className="h-2 rounded-full bg-gray-200">
                <div
                  className="h-2 rounded-full bg-blue-600 transition-all"
                  style={{ width: `${(timeline.date_coverage || 0) * 100}%` }}
                />
              </div>
            </div>
            <span className="text-sm font-medium text-gray-700">
              {Math.round((timeline.date_coverage || 0) * 100)}%
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

function RoundsPanel({ rounds }) {
  if (!rounds || rounds.length === 0) {
    return (
      <div className="py-8 text-center text-gray-500">No round data available</div>
    )
  }

  return (
    <div className="space-y-3 py-4">
      {rounds.map((round, index) => (
        <div key={index} className="rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 text-sm font-medium text-blue-700">
                {round.round}
              </div>
              <div>
                <div className="font-medium text-gray-900">Round {round.round}</div>
                <div className="text-xs text-gray-500">
                  {round.latency_ms ? `${round.latency_ms}ms` : 'Latency unknown'}
                </div>
              </div>
            </div>
            <Badge
              variant={
                round.status === 'APPROVED'
                  ? 'green'
                  : round.status === 'NEEDS_REVISION'
                  ? 'yellow'
                  : 'red'
              }
            >
              {round.status}
            </Badge>
          </div>

          {round.articles_cited?.length > 0 && (
            <div className="mt-3">
              <div className="text-xs font-medium text-gray-500">Articles Cited</div>
              <div className="mt-1 flex flex-wrap gap-1">
                {round.articles_cited.map((article, i) => (
                  <Badge key={i} variant="outline" size="sm">
                    {article}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {round.confidence !== undefined && round.confidence !== null && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-500">Judge Confidence</span>
                <span className="font-medium text-gray-700">
                  {Math.round(round.confidence * 100)}%
                </span>
              </div>
              <div className="mt-1 h-1.5 rounded-full bg-gray-200">
                <div
                  className="h-1.5 rounded-full bg-green-500"
                  style={{ width: `${round.confidence * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function TimelinePanel({ timeline }) {
  const { events = [], gaps = [], date_coverage = 0 } = timeline || {}

  if (events.length === 0) {
    return (
      <div className="py-8 text-center text-gray-500">No timeline data available</div>
    )
  }

  return (
    <div className="space-y-4 py-4">
      <div className="flex items-center justify-between rounded-lg bg-gray-50 p-3">
        <span className="text-sm font-medium text-gray-700">Timeline Coverage</span>
        <span className="text-lg font-bold text-blue-600">{Math.round(date_coverage * 100)}%</span>
      </div>

      <div className="space-y-2">
        <h4 className="font-medium text-gray-900">Events</h4>
        <div className="space-y-2">
          {events.map((event, index) => (
            <div key={index} className="flex items-start gap-3 rounded-lg border border-gray-200 p-3">
              <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 text-xs font-medium text-blue-700">
                {index + 1}
              </div>
              <div className="flex-1">
                <div className="font-medium text-gray-900">{event.description || event.event || 'Event'}</div>
                <div className="text-sm text-gray-500">{event.date || event.timestamp || 'Date unknown'}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {gaps.length > 0 && (
        <div className="space-y-2">
          <h4 className="font-medium text-red-700">Timeline Gaps</h4>
          <div className="space-y-2">
            {gaps.map((gap, index) => (
              <div key={index} className="rounded-lg border border-red-200 bg-red-50 p-3">
                <div className="flex items-center gap-2 text-sm text-red-800">
                  <span>⚠</span>
                  <span>
                    Gap between {gap.from || gap.start || '?'} and {gap.to || gap.end || '?'}
                  </span>
                </div>
                {gap.duration_days && (
                  <div className="mt-1 text-xs text-red-600">{gap.duration_days} days unaccounted for</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ScoreBreakdownPanel({ breakdown }) {
  if (!breakdown || Object.keys(breakdown).length === 0) {
    return (
      <div className="py-8 text-center text-gray-500">No score breakdown available</div>
    )
  }

  const entries = Object.entries(breakdown).filter(([key]) => key !== 'grade')

  return (
    <div className="space-y-3 py-4">
      {entries.map(([key, value]) => (
        <div key={key} className="flex items-center justify-between rounded-lg border border-gray-200 p-3">
          <span className="text-sm font-medium text-gray-700">
            {key.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
          </span>
          <span className="text-lg font-bold text-blue-600">+{value}</span>
        </div>
      ))}
    </div>
  )
}
