import { EVIDENCE_GRADES, CRIME_TYPES } from './constants'

export function formatFileSize(bytes) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}

export function formatDate(dateString, locale = 'en') {
  const date = new Date(dateString)
  return date.toLocaleDateString(locale === 'ar' ? 'ar-EG' : 'en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatDateTime(dateString, locale = 'en') {
  const date = new Date(dateString)
  return date.toLocaleDateString(locale === 'ar' ? 'ar-EG' : 'en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatConfidence(score) {
  return `${Math.round(score * 100)}%`
}

export function formatScore(score) {
  return `${score}/100`
}

export function getGradeInfo(score) {
  if (score >= EVIDENCE_GRADES.STRONG.minScore) return EVIDENCE_GRADES.STRONG
  if (score >= EVIDENCE_GRADES.MEDIUM.minScore) return EVIDENCE_GRADES.MEDIUM
  return EVIDENCE_GRADES.WEAK
}

export function getCrimeTypeInfo(crimeType) {
  return CRIME_TYPES[crimeType] || CRIME_TYPES.unknown
}

export function formatCaseId(caseId) {
  if (!caseId) return ''
  return caseId.replace('CASE_', '#')
}

export function truncateText(text, maxLength = 100) {
  if (!text || text.length <= maxLength) return text
  return text.slice(0, maxLength).trim() + '...'
}

export function formatTimelineEvent(event, locale = 'en') {
  return {
    ...event,
    formattedDate: formatDateTime(event.date || event.timestamp, locale),
    typeLabel: event.type?.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
  }
}

export function formatCurrency(amount, locale = 'en') {
  if (locale === 'ar') {
    return `${amount} جنيه`
  }
  return `EGP ${amount}`
}

export function scoreToColor(score) {
  if (score >= 75) return 'text-success-light'
  if (score >= 45) return 'text-warning-light'
  return 'text-danger-light'
}

export function scoreToBgColor(score) {
  if (score >= 75) return 'bg-success/20'
  if (score >= 45) return 'bg-warning/20'
  return 'bg-danger/20'
}
