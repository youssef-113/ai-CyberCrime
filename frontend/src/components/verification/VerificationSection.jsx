import { useState } from 'react'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { VerificationButton } from './VerificationButton'
import { VerificationResults } from './VerificationResults'
import { VerificationAudit } from './VerificationAudit'
import { useTheme } from '../../context/ThemeContext'

/**
 * VerificationSection - Integrated verification display for CaseAnalysisPage
 * 
 * Shows verification results from pipeline OR allows re-verification with button
 * 
 * @param {Object} props
 * @param {string} props.caseId - The case ID
 * @param {Object} props.result - Full pipeline result including verification data
 * @param {Object} props.caseData - Case data for re-verification
 * @param {function} props.onVerificationComplete - Callback when re-verification done
 */
export function VerificationSection({
  caseId,
  result,
  caseData,
  onVerificationComplete,
  className = '',
}) {
  const { language, isRtl } = useTheme()
  const [showAudit, setShowAudit] = useState(false)
  const [verificationResult, setVerificationResult] = useState(null)

  // Use either fresh verification result or result from pipeline
  const displayResult = verificationResult || result?.verification

  const t = (key) => {
    const translations = {
      en: {
        'verify.title': 'Evidence Verification',
        'verify.description': 'AI-powered multi-round verification with legal grounding',
        'verify.status': 'Status',
        'verify.rounds': 'Rounds',
        'verify.score': 'Score',
        'verify.grade': 'Grade',
        'verify.reverify': 'Re-verify Evidence',
        'verify.viewAudit': 'View Audit Trail',
        'verify.noVerification': 'Verification not completed',
        'verify.pending': 'Verification pending - run analysis to verify',
      },
      ar: {
        'verify.title': 'التحقق من الأدلة',
        'verify.description': 'تحقق متعدد الجولات مدعوم بالذكاء الاصطناعي مع أساس قانوني',
        'verify.status': 'الحالة',
        'verify.rounds': 'الجولات',
        'verify.score': 'النتيجة',
        'verify.grade': 'التقدير',
        'verify.reverify': 'إعادة التحقق',
        'verify.viewAudit': 'عرض سجل التدقيق',
        'verify.noVerification': 'لم يتم إكمال التحقق',
        'verify.pending': 'التحقق معلق - قم بتشغيل التحليل للتحقق',
      },
    }
    return translations[language]?.[key] || key
  }

  const handleVerificationComplete = (result) => {
    setVerificationResult(result)
    onVerificationComplete?.(result)
  }

  if (!displayResult) {
    return (
      <Card className={`p-6 ${className}`} dir={isRtl ? 'rtl' : 'ltr'}>
        <div className="text-center">
          <h3 className="text-lg font-semibold text-gray-900">{t('verify.noVerification')}</h3>
          <p className="mt-2 text-gray-500">{t('verify.pending')}</p>
        </div>
      </Card>
    )
  }

  return (
    <div className={`space-y-4 ${className}`} dir={isRtl ? 'rtl' : 'ltr'}>
      {/* Header with re-verify button */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{t('verify.title')}</h3>
          <p className="text-sm text-gray-500">{t('verify.description')}</p>
        </div>
        <div className="flex gap-2">
          {caseData && (
            <VerificationButton
              caseId={caseId}
              caseData={caseData}
              onVerificationComplete={handleVerificationComplete}
              variant="outline"
              size="sm"
            >
              {t('verify.reverify')}
            </VerificationButton>
          )}
          {displayResult.case_id && (
            <Button variant="ghost" size="sm" onClick={() => setShowAudit(true)}>
              {t('verify.viewAudit')}
            </Button>
          )}
        </div>
      </div>

      {/* Quick Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          label={t('verify.status')}
          value={displayResult.status || 'UNKNOWN'}
          badge
          badgeColor={getStatusColor(displayResult.status)}
        />
        <StatCard
          label={t('verify.rounds')}
          value={displayResult.rounds || 0}
        />
        <StatCard
          label={t('verify.score')}
          value={`${displayResult.final_score || 0}/100`}
        />
        <StatCard
          label={t('verify.grade')}
          value={displayResult.grade || '-'}
          badge
          badgeColor={getGradeColor(displayResult.grade)}
        />
      </div>

      {/* Full Results Card (expandable) */}
      {displayResult.case_id && (
        <VerificationResults
          result={displayResult}
          onViewAudit={setShowAudit}
          className="mt-4"
        />
      )}

      {/* Audit Modal */}
      <VerificationAudit
        verificationId={displayResult.case_id}
        isOpen={showAudit}
        onClose={() => setShowAudit(false)}
      />
    </div>
  )
}

function StatCard({ label, value, badge, badgeColor }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-3">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="mt-1 flex items-center justify-between">
        {badge ? (
          <Badge variant={badgeColor} size="sm">
            {value}
          </Badge>
        ) : (
          <span className="text-lg font-semibold text-gray-900">{value}</span>
        )}
      </div>
    </div>
  )
}

function getStatusColor(status) {
  switch (status) {
    case 'APPROVED':
      return 'success'
    case 'NEEDS_REVISION':
      return 'warning'
    case 'NEEDS_USER_REVIEW':
      return 'danger'
    default:
      return 'neutral'
  }
}

function getGradeColor(grade) {
  switch (grade) {
    case 'STRONG':
      return 'success'
    case 'MEDIUM':
      return 'warning'
    case 'WEAK':
      return 'danger'
    default:
      return 'neutral'
  }
}
