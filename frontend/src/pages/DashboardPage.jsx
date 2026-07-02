import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Plus, FileText, Shield, TrendingUp, Clock, AlertTriangle, CheckCircle2, RefreshCw } from 'lucide-react'
import { Card, CardBody } from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { SkeletonCard } from '../components/ui/Skeleton'
import { getGradeInfo, formatDateTime, getCrimeTypeInfo, formatCaseId } from '../utils/formatters'
import { useCases } from '../api/hooks'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { getTranslation } from '../utils/translations'

const DEMO_CASES = [
  {
    case_id: 'CASE_DEMO_001',
    created_at: '2024-01-15T10:30:00',
    classification: { crime_type: 'fraud' },
    score: { total_score: 85, grade: 'STRONG' },
    verification: { status: 'APPROVED' },
    files_processed: 3
  },
  {
    case_id: 'CASE_DEMO_002',
    created_at: '2024-01-14T14:20:00',
    classification: { crime_type: 'identity_theft' },
    score: { total_score: 62, grade: 'MEDIUM' },
    verification: { status: 'PENDING' },
    files_processed: 2
  },
  {
    case_id: 'CASE_DEMO_003',
    created_at: '2024-01-13T09:15:00',
    classification: { crime_type: 'phishing' },
    score: { total_score: 45, grade: 'WEAK' },
    verification: { status: 'PENDING' },
    files_processed: 1
  }
]

export default function DashboardPage() {
  const { cases, fetchCases, loading, error } = useCases()
  const { language, isRtl } = useTheme()
  const { isDemo } = useAuth()
  
  const t = (key) => getTranslation(language, key)

  useEffect(() => {
    fetchCases().catch(() => {})
  }, [fetchCases])

  const displayCases = cases.length > 0
    ? cases
    : (isDemo ? DEMO_CASES : [])

  const stats = {
    total: displayCases.length,
    strong: displayCases.filter((c) => c.score?.grade === 'STRONG').length,
    pending: displayCases.filter((c) => c.verification?.status !== 'APPROVED').length,
    avgScore: displayCases.length ? Math.round(displayCases.reduce((s, c) => s + (c.score?.total_score || 0), 0) / displayCases.length) : 0,
  }

  if (loading) {
    return (
      <div className="space-y-6" dir={isRtl ? 'rtl' : 'ltr'}>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
        <SkeletonCard />
      </div>
    )
  }

  if (error && cases.length === 0 && !isDemo) {
    return (
      <div className="space-y-6" dir={isRtl ? 'rtl' : 'ltr'}>
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6" dir={isRtl ? 'rtl' : 'ltr'}>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="section-title">{t('dashboard.title')}</h1>
          <p className="section-subtitle">{t('dashboard.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={fetchCases} disabled={loading} className="gap-2">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            {t('common.refresh')}
          </Button>
          <Link to="/analyze">
            <Button className="gap-2">
              <Plus className="w-4 h-4" />
              {t('dashboard.newCase')}
            </Button>
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { icon: FileText, labelKey: 'dashboard.totalCases', value: stats.total, color: 'text-primary' },
          { icon: Shield, labelKey: 'dashboard.strongEvidence', value: stats.strong, color: 'text-success-light' },
          { icon: AlertTriangle, labelKey: 'dashboard.needsReview', value: stats.pending, color: 'text-warning-light' },
          { icon: TrendingUp, labelKey: 'dashboard.avgScore', value: stats.avgScore, color: 'text-accent-blue' },
        ].map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
          >
            <Card>
              <CardBody className="flex items-center gap-4">
                <stat.icon className={`w-8 h-8 ${stat.color} shrink-0`} />
                <div>
                  <p className="stat-value">{stat.value}</p>
                  <p className="stat-label">{t(stat.labelKey)}</p>
                </div>
              </CardBody>
            </Card>
          </motion.div>
        ))}
      </div>

      <Card>
        <div className="px-6 py-4 border-b border-neutral-800 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{t('dashboard.recentCases')}</h2>
          <Badge variant="neutral">{displayCases.length} {t('dashboard.cases')}</Badge>
        </div>
        <div className="divide-y divide-neutral-800/50">
          {displayCases.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <FileText className="w-12 h-12 text-neutral-600 mx-auto mb-4" />
              <p className="text-neutral-400 mb-4">{t('dashboard.noCases')}</p>
              <Link to="/analyze">
                <Button>{t('dashboard.newCase')}</Button>
              </Link>
            </div>
          ) : (
            displayCases.map((caseItem, i) => {
              const gradeInfo = getGradeInfo(caseItem.score?.total_score || 0)
              const crimeInfo = getCrimeTypeInfo(caseItem.classification?.crime_type || 'unknown')
              return (
              <motion.div
                key={caseItem.case_id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.05 }}
                className="px-6 py-4 flex items-center justify-between hover:bg-neutral-800/30 transition-colors"
              >
                <div className="flex items-center gap-4 min-w-0">
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                    <FileText className="w-5 h-5 text-primary" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-medium">{formatCaseId(caseItem.case_id)}</span>
                      <Badge variant={crimeInfo.color}>{language === 'ar' ? crimeInfo.ar : crimeInfo.en}</Badge>
                    </div>
                    <p className="text-xs text-neutral-500 mt-0.5">
                      {formatDateTime(caseItem.created_at)} · {caseItem.files_processed || caseItem.files_count || 0} {t('common.files')}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right hidden sm:block">
                    <p className={`text-sm font-semibold ${
                      caseItem.score?.grade === 'STRONG' ? 'text-success-light' :
                      caseItem.score?.grade === 'MEDIUM' ? 'text-warning-light' : 'text-danger-light'
                    }`}>
                      {caseItem.score?.total_score || 0}%
                    </p>
                    <p className="text-xs text-neutral-500">{language === 'ar' ? gradeInfo.labelAr : gradeInfo.label}</p>
                  </div>
                  {caseItem.verification?.status === 'APPROVED' ? (
                    <CheckCircle2 className="w-5 h-5 text-success-light" />
                  ) : (
                    <Clock className="w-5 h-5 text-warning-light" />
                  )}
                </div>
              </motion.div>
            )
          })
        )}
        </div>
      </Card>
    </div>
  )
}
