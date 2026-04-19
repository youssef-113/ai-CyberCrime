import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Plus, FileText, Shield, TrendingUp, Clock, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { Card, CardBody } from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { SkeletonCard } from '../components/ui/Skeleton'
import { getGradeInfo, formatDateTime, getCrimeTypeInfo, formatCaseId } from '../utils/formatters'
import { SCORE_WEIGHTS } from '../utils/constants'

const MOCK_CASES = [
  {
    case_id: 'CASE_A3F2B1',
    created_at: '2024-11-15T14:32:00Z',
    classification: { crime_type: 'blackmail', confidence: 0.92 },
    score: { total_score: 87, grade: 'STRONG' },
    verification: { status: 'APPROVED', rounds: 2 },
    files_processed: 3,
  },
  {
    case_id: 'CASE_B7C4D2',
    created_at: '2024-11-10T09:15:00Z',
    classification: { crime_type: 'scam', confidence: 0.78 },
    score: { total_score: 62, grade: 'MEDIUM' },
    verification: { status: 'APPROVED', rounds: 1 },
    files_processed: 2,
  },
  {
    case_id: 'CASE_C1E5F3',
    created_at: '2024-11-08T16:45:00Z',
    classification: { crime_type: 'threat', confidence: 0.85 },
    score: { total_score: 38, grade: 'WEAK' },
    verification: { status: 'NEEDS_USER_REVIEW', rounds: 3 },
    files_processed: 1,
  },
]

export default function DashboardPage() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const timer = setTimeout(() => {
      setCases(MOCK_CASES)
      setLoading(false)
    }, 800)
    return () => clearTimeout(timer)
  }, [])

  const stats = {
    total: cases.length,
    strong: cases.filter((c) => c.score.grade === 'STRONG').length,
    pending: cases.filter((c) => c.verification.status !== 'APPROVED').length,
    avgScore: cases.length ? Math.round(cases.reduce((s, c) => s + c.score.total_score, 0) / cases.length) : 0,
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
        <SkeletonCard />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="section-title">Dashboard</h1>
          <p className="section-subtitle">Overview of your case activity</p>
        </div>
        <Link to="/analyze">
          <Button className="gap-2">
            <Plus className="w-4 h-4" />
            New Case
          </Button>
        </Link>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { icon: FileText, label: 'Total Cases', value: stats.total, color: 'text-primary' },
          { icon: Shield, label: 'Strong Evidence', value: stats.strong, color: 'text-success-light' },
          { icon: AlertTriangle, label: 'Needs Review', value: stats.pending, color: 'text-warning-light' },
          { icon: TrendingUp, label: 'Avg Score', value: stats.avgScore, color: 'text-accent-blue' },
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
                  <p className="stat-label">{stat.label}</p>
                </div>
              </CardBody>
            </Card>
          </motion.div>
        ))}
      </div>

      <Card>
        <div className="px-6 py-4 border-b border-neutral-800 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Recent Cases</h2>
          <Badge variant="neutral">{cases.length} cases</Badge>
        </div>
        <div className="divide-y divide-neutral-800/50">
          {cases.map((caseItem, i) => {
            const gradeInfo = getGradeInfo(caseItem.score.total_score)
            const crimeInfo = getCrimeTypeInfo(caseItem.classification.crime_type)
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
                      <Badge variant={crimeInfo.color}>{crimeInfo.en}</Badge>
                    </div>
                    <p className="text-xs text-neutral-500 mt-0.5">
                      {formatDateTime(caseItem.created_at)} · {caseItem.files_processed} files
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right hidden sm:block">
                    <p className={`text-sm font-semibold ${
                      caseItem.score.grade === 'STRONG' ? 'text-success-light' :
                      caseItem.score.grade === 'MEDIUM' ? 'text-warning-light' : 'text-danger-light'
                    }`}>
                      {caseItem.score.total_score}%
                    </p>
                    <p className="text-xs text-neutral-500">{gradeInfo.label}</p>
                  </div>
                  {caseItem.verification.status === 'APPROVED' ? (
                    <CheckCircle2 className="w-5 h-5 text-success-light" />
                  ) : (
                    <Clock className="w-5 h-5 text-warning-light" />
                  )}
                </div>
              </motion.div>
            )
          })}
        </div>
      </Card>
    </div>
  )
}
