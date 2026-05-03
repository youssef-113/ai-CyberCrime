import { useState, useEffect } from 'react'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { getVerifications } from '../../api/endpoints'

/**
 * VerificationsList - Displays all verification cases for the current user
 * 
 * @param {function} onViewVerification - Callback when viewing a specific verification
 * @param {function} onViewAudit - Callback when viewing audit trail
 */
export function VerificationsList({ onViewVerification, onViewAudit, className = '' }) {
  const [verifications, setVerifications] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [pagination, setPagination] = useState({ limit: 20, offset: 0, hasMore: false })

  useEffect(() => {
    loadVerifications()
  }, [pagination.offset])

  const loadVerifications = async () => {
    setLoading(true)
    try {
      const data = await getVerifications({
        limit: pagination.limit,
        offset: pagination.offset,
      })
      setVerifications(data.verifications || [])
      setPagination((prev) => ({
        ...prev,
        hasMore: (data.verifications || []).length === pagination.limit,
      }))
    } catch (err) {
      setError(err.message || 'Failed to load verifications')
    } finally {
      setLoading(false)
    }
  }

  const handleLoadMore = () => {
    setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }))
  }

  if (loading && verifications.length === 0) {
    return (
      <Card className={`p-8 ${className}`}>
        <div className="flex items-center justify-center">
          <LoadingSpinner />
          <span className="ml-3 text-gray-600">Loading verifications...</span>
        </div>
      </Card>
    )
  }

  if (error && verifications.length === 0) {
    return (
      <Card className={`p-6 ${className}`}>
        <div className="rounded-lg bg-red-50 p-4 text-red-700">
          <p className="font-medium">Error loading verifications</p>
          <p className="text-sm">{error}</p>
          <Button variant="outline" size="sm" className="mt-3" onClick={loadVerifications}>
            Retry
          </Button>
        </div>
      </Card>
    )
  }

  if (verifications.length === 0) {
    return (
      <Card className={`p-8 ${className}`}>
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-gray-100">
            <ShieldIcon className="h-8 w-8 text-gray-400" />
          </div>
          <h3 className="text-lg font-medium text-gray-900">No verifications yet</h3>
          <p className="mt-1 text-sm text-gray-500">
            Upload evidence and run the full analysis pipeline to create verifications.
          </p>
        </div>
      </Card>
    )
  }

  return (
    <Card className={`overflow-hidden ${className}`}>
      <div className="border-b border-gray-200 bg-gray-50 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Verification History</h3>
            <p className="text-sm text-gray-500">{verifications.length} cases verified</p>
          </div>
          <Button variant="outline" size="sm" onClick={loadVerifications} disabled={loading}>
            {loading ? <LoadingSpinner size="sm" /> : 'Refresh'}
          </Button>
        </div>
      </div>

      <div className="divide-y divide-gray-200">
        {verifications.map((v) => (
          <VerificationItem
            key={v.case_id}
            verification={v}
            onView={() => onViewVerification?.(v.case_id)}
            onViewAudit={() => onViewAudit?.(v.case_id)}
          />
        ))}
      </div>

      {pagination.hasMore && (
        <div className="border-t border-gray-200 p-4">
          <Button variant="outline" onClick={handleLoadMore} disabled={loading} className="w-full">
            {loading ? 'Loading...' : 'Load More'}
          </Button>
        </div>
      )}
    </Card>
  )
}

function VerificationItem({ verification, onView, onViewAudit }) {
  const {
    case_id,
    crime_type,
    final_status,
    final_score,
    grade,
    created_at,
    total_rounds,
  } = verification

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

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Unknown'
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return dateStr
    }
  }

  return (
    <div className="flex items-center justify-between px-6 py-4 hover:bg-gray-50">
      <div className="flex items-center gap-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100">
          <span className="text-sm font-bold text-blue-700">
            {final_score !== undefined && final_score !== null ? final_score : '-'}
          </span>
        </div>

        <div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-gray-900">{case_id}</span>
            <Badge variant={getStatusColor(final_status)} size="sm">
              {final_status || 'PENDING'}
            </Badge>
          </div>
          <div className="mt-1 flex items-center gap-3 text-sm text-gray-500">
            <span className="capitalize">{crime_type}</span>
            <span>•</span>
            <span>{formatDate(created_at)}</span>
            {total_rounds !== undefined && (
              <>
                <span>•</span>
                <span>{total_rounds} rounds</span>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {grade && (
          <Badge variant={getGradeColor(grade)} size="sm">
            {grade}
          </Badge>
        )}
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={onView}>
            View
          </Button>
          <Button variant="outline" size="sm" onClick={onViewAudit}>
            Audit
          </Button>
        </div>
      </div>
    </div>
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

function LoadingSpinner({ size = 'md' }) {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6',
    lg: 'h-8 w-8',
  }

  return (
    <svg className={`animate-spin ${sizeClasses[size]}`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}
