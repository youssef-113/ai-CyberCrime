import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Download, Eye, Trash2, RefreshCw, Search, Filter } from 'lucide-react'
import { useCases, usePdfDownload } from '../api/hooks'
import { useTheme } from '../context/ThemeContext'
import { getTranslation } from '../utils/translations'
import Button from '../components/ui/Button'

const statusColors = {
  processing: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
  completed: 'text-green-400 bg-green-400/10 border-green-400/20',
  failed: 'text-red-400 bg-red-400/10 border-red-400/20',
}

const gradeColors = {
  STRONG: 'text-green-400',
  MEDIUM: 'text-yellow-400',
  WEAK: 'text-red-400',
}

export default function CaseHistoryPage() {
  const { cases, fetchCases, loading, error } = useCases()
  const { download, loading: downloadLoading } = usePdfDownload()
  const { language, isRtl } = useTheme()
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [selectedCase, setSelectedCase] = useState(null)
  
  const t = (key) => getTranslation(language, key)

  useEffect(() => {
    fetchCases()
  }, [fetchCases])

  const filteredCases = cases.filter(c => {
    const matchesSearch = searchTerm === '' || 
      c.case_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.classification?.crime_type?.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesStatus = statusFilter === 'all' || c.status === statusFilter
    return matchesSearch && matchesStatus
  })

  const handleDownload = async (caseId) => {
    try {
      await download(caseId)
    } catch (err) {
      console.error('Download failed:', err)
    }
  }

  const handleRefresh = () => {
    fetchCases()
  }

  return (
    <div className="container mx-auto px-6 py-8" dir={isRtl ? 'rtl' : 'ltr'}>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-display font-bold mb-2">{t('history.title')}</h1>
          <p className="text-neutral-400">{t('history.subtitle')}</p>
        </div>
        <Button onClick={handleRefresh} variant="outline" className="gap-2">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          {t('history.refresh')}
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 mb-6">
        <div className="flex-1 min-w-[250px]">
          <div className="relative">
            <Search className={`absolute ${isRtl ? 'right-3' : 'left-3'} top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500`} />
            <input
              type="text"
              placeholder={t('history.searchCases')}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className={`w-full ${isRtl ? 'pr-10 pl-4' : 'pl-10 pr-4'} py-2 bg-neutral-900/50 border border-neutral-800 rounded-lg text-sm focus:outline-none focus:border-primary/50`}
            />
          </div>
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-2 bg-neutral-900/50 border border-neutral-800 rounded-lg text-sm focus:outline-none focus:border-primary/50"
        >
          <option value="all">{t('history.allStatus')}</option>
          <option value="processing">{t('history.processing')}</option>
          <option value="completed">{t('history.completed')}</option>
          <option value="failed">{t('history.failed')}</option>
        </select>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {loading && cases.length === 0 ? (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="w-8 h-8 text-primary animate-spin" />
        </div>
      ) : filteredCases.length === 0 ? (
        <div className="text-center py-12">
          <FileText className="w-12 h-12 text-neutral-600 mx-auto mb-4" />
          <p className="text-neutral-400 mb-4">{t('history.noCases')}</p>
          <Link to="/analyze">
            <Button>{t('history.startNewCase')}</Button>
          </Link>
        </div>
      ) : (
        <div className="grid gap-4">
          {filteredCases.map((caseItem) => (
            <div
              key={caseItem.case_id}
              className="perspective-card p-6 hover:border-primary/30 transition-all"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-medium">{caseItem.case_id}</span>
                    <Badge variant={statusColors[caseItem.status] || statusColors.processing}>
                      {t(`history.${caseItem.status}`)}
                    </Badge>
                  </div>
                  {caseItem.created_at && (
                    <p className="text-sm text-neutral-500 mb-3">
                      {t('history.created')}: {new Date(caseItem.created_at).toLocaleString()}
                    </p>
                  )}

                  {caseItem.classification && (
                    <div className="space-y-2 mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-neutral-400">{t('analysis.crimeType')}:</span>
                        <span className="text-sm font-medium capitalize">{language === 'ar' ? t(`crimes.${caseItem.classification.crime_type}`) : caseItem.classification.crime_type}</span>
                      </div>
                      {caseItem.score && (
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-neutral-400">{t('analysis.score')}:</span>
                          <span className={`text-sm font-bold ${gradeColors[caseItem.score.grade] || gradeColors.WEAK}`}>
                            {caseItem.score.total_score}% ({language === 'ar' ? t(`grades.${caseItem.score.grade}`) : caseItem.score.grade})
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {caseItem.files_count && (
                    <p className="text-sm text-neutral-500">
                      {caseItem.files_count} {t('history.filesProcessed')}
                    </p>
                  )}

                  {caseItem.error && (
                    <p className="text-sm text-red-400 mt-2">{caseItem.error}</p>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {caseItem.status === 'completed' && (
                    <>
                      <Link to={`/analyze?caseId=${caseItem.case_id}`}>
                        <Button variant="outline" size="sm" className="gap-2">
                          <Eye className="w-4 h-4" />
                          {t('history.view')}
                        </Button>
                      </Link>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDownload(caseItem.case_id)}
                        disabled={downloadLoading}
                        className="gap-2"
                      >
                        <Download className="w-4 h-4" />
                        {t('history.pdf')}
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Case Detail Modal */}
      {selectedCase && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="perspective-card-elevated max-w-4xl w-full max-h-[90vh] overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold">{selectedCase.case_id}</h2>
              <Button variant="ghost" onClick={() => setSelectedCase(null)}>
                ×
              </Button>
            </div>
            <pre className="text-sm text-neutral-300 whitespace-pre-wrap">
              {JSON.stringify(selectedCase, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
