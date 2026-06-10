import { useState, useCallback, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, FileImage, FileText, X, AlertCircle, CheckCircle2, Clock, Phone, User, DollarSign, Scale, Download, RotateCcw, ChevronRight, Eye, Cpu, ArrowRight } from 'lucide-react'
import { Card, CardBody } from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { ProgressBar, PipelineProgress, Spinner } from '../components/ui/ProgressIndicator'
import { useAnalyze, usePdfDownload } from '../api/hooks'
import { VerificationSection } from '../components/verification'
import { validateFile, validateFileList } from '../utils/validators'
import { formatFileSize, getGradeInfo, getCrimeTypeInfo, scoreToColor, scoreToBgColor } from '../utils/formatters'
import { FILE_CONSTRAINTS, SCORE_WEIGHTS, VERIFICATION_STATUS } from '../utils/constants'
import { useTheme } from '../context/ThemeContext'
import { getTranslation } from '../utils/translations'
import useAlerts from '../hooks/useAlerts'

const PIPELINE_STEPS_EN = ['Upload', 'OCR', 'Classify', 'RAG', 'Verify', 'Score', 'PDF']
const PIPELINE_STEPS_AR = ['رفع', 'استخراج النص', 'تصنيف', 'استرجاع', 'تحقق', 'تقييم', 'تقرير']

export default function CaseAnalysisPage() {
  const [files, setFiles] = useState([])
  const [dragActive, setDragActive] = useState(false)
  const [pipelineStep, setPipelineStep] = useState(-1)
  const [result, setResult] = useState(null)
  const { analyze, loading, progress, stage, error } = useAnalyze()
  const { download, loading: downloading } = usePdfDownload()
  const { language, isRtl } = useTheme()
  const alerts = useAlerts()
  
  const t = (key) => getTranslation(language, key)
  const pipelineSteps = language === 'ar' ? PIPELINE_STEPS_AR : PIPELINE_STEPS_EN

  const handleDrag = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(e.type === 'dragenter' || e.type === 'dragover')
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files?.[0]) addFiles(e.dataTransfer.files)
  }, [])

  const addFiles = (fileList) => {
    const newFiles = Array.from(fileList).map((file) => {
      const validation = validateFile(file)
      return {
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        file,
        name: file.name,
        type: file.type,
        size: file.size,
        formattedSize: formatFileSize(file.size),
        valid: validation.valid,
        errors: validation.errors,
      }
    })

    const validNew = newFiles.filter((f) => f.valid)
    const invalidNew = newFiles.filter((f) => !f.valid)

    if (invalidNew.length > 0) {
      alerts.uploadFailed(invalidNew[0].errors[0])
    }

    setFiles((prev) => {
      const combined = [...prev, ...validNew]
      if (combined.length > FILE_CONSTRAINTS.MAX_FILES) {
        alerts.error('❌ Too Many Files', `Maximum ${FILE_CONSTRAINTS.MAX_FILES} files allowed`)
        return combined.slice(0, FILE_CONSTRAINTS.MAX_FILES)
      }
      return combined
    })
  }

  const removeFile = (id) => setFiles((prev) => prev.filter((f) => f.id !== id))

  const handleAnalyze = async () => {
    const validation = validateFileList(files.map((f) => f.file))
    if (!validation.valid) {
      alerts.uploadFailed(validation.errors[0])
      return
    }

    setPipelineStep(0)
    setResult(null)
    alerts.analysisStart()

    try {
      const data = await analyze(files, false)
      setPipelineStep(pipelineSteps.length - 1)
      setResult(data)
      alerts.close()
      alerts.analysisComplete(Math.round(((data.verification?.final_score || 0) / 100) * 100))
    } catch (err) {
      setPipelineStep(-1)
      alerts.analysisFailed(error || 'Analysis failed')
    }
  }

  useEffect(() => {
    if (stage) {
      const stageIndex = {
        ocr: 1,
        classification: 2,
        rag: 3,
        verification: 4,
        score: 5,
        completed: pipelineSteps.length - 1,
        failed: pipelineSteps.length - 1,
      }[stage.toLowerCase()]

      if (typeof stageIndex === 'number') {
        setPipelineStep(Math.min(stageIndex, pipelineSteps.length - 1))
        return
      }
    }

    if (!loading) return
    const thresholds = [0, 10, 25, 40, 60, 80, 100]
    const nextStep = thresholds.reduce((current, threshold, index) => {
      if (progress >= threshold) return index
      return current
    }, 0)
    setPipelineStep(Math.min(nextStep, pipelineSteps.length - 1))
  }, [progress, loading, pipelineSteps.length, pipelineSteps, stage])

  const handleDownload = async () => {
    if (result?.case_id) {
      try {
        await download(result.case_id)
        toastSuccess('PDF downloaded!')
      } catch {
        toastError('Download failed')
      }
    }
  }

  const handleReset = () => {
    setFiles([])
    setResult(null)
    setPipelineStep(-1)
  }

  if (result) {
    return <ResultView result={result} onDownload={handleDownload} onReset={handleReset} downloading={downloading} />
  }

  return (
    <div className="space-y-6" dir={isRtl ? 'rtl' : 'ltr'}>
      <div>
        <h1 className="section-title">{t('analysis.title')}</h1>
        <p className="section-subtitle">{t('analysis.subtitle')}</p>
      </div>

      {pipelineStep >= 0 && loading ? (
        <Card variant="elevated">
          <CardBody className="py-12">
            <div className="flex flex-col items-center gap-6">
              <Spinner size="lg" />
              <PipelineProgress steps={pipelineSteps} currentStep={pipelineStep} className="w-full max-w-2xl" />
              <p className="text-neutral-400 text-sm">
                {t('analysis.processing')} {stage || pipelineSteps[pipelineStep]}...
              </p>
              <ProgressBar value={progress} label={t('analysis.uploadProgress')} className="w-full max-w-md" />
            </div>
          </CardBody>
        </Card>
      ) : (
        <>
          <Card>
            <CardBody>
              <div
                className={`border-2 border-dashed rounded-xl p-10 text-center transition-all duration-300 ${
                  dragActive
                    ? 'border-primary bg-primary/5'
                    : 'border-neutral-700 hover:border-neutral-600'
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
              >
                <Upload className="w-12 h-12 mx-auto mb-3 text-primary" />
                <p className="text-lg mb-1">{t('analysis.uploadFiles')}</p>
                <p className="text-sm text-neutral-500 mb-4">
                  {t('analysis.supportedFormats')} — max {FILE_CONSTRAINTS.MAX_SIZE_MB}MB each, up to {FILE_CONSTRAINTS.MAX_FILES} files
                </p>
                <label htmlFor="case-file-upload" className="btn-primary inline-block cursor-pointer">
                  {t('analysis.uploadFiles')}
                </label>
                <input
                  id="case-file-upload"
                  type="file"
                  multiple
                  accept={FILE_CONSTRAINTS.ACCEPTED_EXTENSIONS.join(',')}
                  onChange={(e) => e.target.files?.[0] && addFiles(e.target.files)}
                  className="hidden"
                />
              </div>
            </CardBody>
          </Card>

          {files.length > 0 && (
            <Card>
              <div className="px-6 py-4 border-b border-neutral-800 flex items-center justify-between">
                <h3 className="font-semibold">{t('analysis.uploadFiles')} ({files.length})</h3>
                <Button variant="danger" size="sm" onClick={() => setFiles([])}>{t('common.cancel')}</Button>
              </div>
              <div className="divide-y divide-neutral-800/50">
                {files.map((file) => (
                  <div key={file.id} className="px-6 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-3 min-w-0">
                      {file.type.startsWith('image/') ? (
                        <FileImage className="w-5 h-5 text-primary shrink-0" />
                      ) : (
                        <FileText className="w-5 h-5 text-accent-purple shrink-0" />
                      )}
                      <span className="text-sm truncate">{file.name}</span>
                      <span className="text-xs text-neutral-500 shrink-0">{file.formattedSize}</span>
                    </div>
                    <button onClick={() => removeFile(file.id)} className="btn-ghost btn-icon shrink-0" aria-label="Remove file">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
              <div className="px-6 py-4 flex justify-end">
                <Button onClick={handleAnalyze} className="gap-2">
                  {t('analysis.analyze')}
                  <ChevronRight className={`w-4 h-4 ${isRtl ? 'rotate-180' : ''}`} />
                </Button>
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  )
}

function ResultView({ result, onDownload, onReset, downloading }) {
  const { language, isRtl } = useTheme()
  const t = (key) => getTranslation(language, key)

  const gradeInfo = getGradeInfo(result.score?.total_score || 0)
  const crimeInfo = getCrimeTypeInfo(result.classification?.crime_type || 'unknown')
  const verificationStatus = VERIFICATION_STATUS[result.verification?.status] || VERIFICATION_STATUS.NEEDS_USER_REVIEW

  // Safe helpers for nested OCR data
  const ocrConf = result.ocr?.avg_confidence ?? result.ocr_confidence ?? 0
  const ocrPerFile = result.ocr?.per_file || []
  const ocrEngine = ocrPerFile[0]?.engine || 'easyocr'
  const ocrLang = ocrPerFile[0]?.language || result.language || 'en'
  const ocrFallback = ocrPerFile.some(f => f.fallback_triggered)
  const pipelineErrors = result.pipeline_status?.errors || []
  const isPartial = result.pipeline_status?.partial || false
  const stagesCompleted = result.pipeline_status?.stages_completed || []

  const langLabel = { ar: 'عربي', en: 'English', mixed: 'مختلط' }[ocrLang] || 'English'

  return (
    <div className="space-y-6" dir={isRtl ? 'rtl' : 'ltr'}>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="section-title">{t('analysis.results')}</h1>
          <p className="section-subtitle">{t('analysis.caseId')} {result.case_id}</p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={onReset} className="gap-2">
            <RotateCcw className="w-4 h-4" />
            {t('analysis.startNewCase')}
          </Button>
          <Button onClick={onDownload} loading={downloading} className="gap-2">
            <Download className="w-4 h-4" />
            {t('analysis.downloadPdf')}
          </Button>
        </div>
      </div>

      {/* Pipeline partial results warning */}
      {isPartial && pipelineErrors.length > 0 && (
        <Card className="border-l-4 border-l-warning">
          <CardBody>
            <div className="flex items-center gap-2 mb-3">
              <AlertCircle className="w-5 h-5 text-warning" />
              <h3 className="font-semibold text-warning-light">
                {language === 'ar' ? 'بعض المراحل لم تكتمل' : 'Some pipeline stages did not complete'}
              </h3>
            </div>
            <div className="flex flex-wrap gap-2 mb-3">
              {['ocr', 'classify', 'rag', 'verify'].map(stage => (
                <Badge key={stage} variant={stagesCompleted.includes(stage) ? 'success' : 'danger'} size="sm">
                  {{ ocr: 'OCR', classify: language === 'ar' ? 'تصنيف' : 'Classify', rag: 'RAG', verify: language === 'ar' ? 'تحقق' : 'Verify' }[stage]}
                </Badge>
              ))}
            </div>
            <ul className="space-y-1">
              {pipelineErrors.map((err, i) => (
                <li key={i} className="text-sm text-neutral-400">
                  <span className="text-warning">{{ ocr: 'OCR', classify: 'Classify', rag: 'RAG', verify: 'Verify' }[err.stage] || err.stage}:</span>{' '}
                  {err.error}
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardBody className="text-center">
            <p className={`stat-value ${scoreToColor(result.score?.total_score || 0)}`}>
              {result.score?.total_score || 0}%
            </p>
            <p className="stat-label">{t('analysis.score')}</p>
            <Badge variant={gradeInfo.color} className="mt-2">{language === 'ar' ? gradeInfo.labelAr : gradeInfo.label}</Badge>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="text-center">
            <p className="stat-value text-primary">{Math.round((result.classification?.confidence || 0) * 100)}%</p>
            <p className="stat-label">{t('analysis.confidence')}</p>
            <Badge variant={crimeInfo.color} className="mt-2">{language === 'ar' ? crimeInfo.ar : crimeInfo.en}</Badge>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="text-center">
            <div className="flex items-center justify-center gap-2">
              {result.verification?.status === 'APPROVED' ? (
                <CheckCircle2 className="w-6 h-6 text-success-light" />
              ) : (
                <AlertCircle className="w-6 h-6 text-warning-light" />
              )}
              <p className="stat-value">{result.verification?.rounds || 0}</p>
            </div>
            <p className="stat-label">{t('analysis.verificationRounds')}</p>
            <Badge variant={verificationStatus.color} className="mt-2">{t(`verification.${result.verification?.status}`)}</Badge>
          </CardBody>
        </Card>
      </div>

      {result.ocr && (
        <Card>
          <div className="px-6 py-4 border-b border-neutral-800 flex items-center gap-2">
            <Eye className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold">{language === 'ar' ? 'تفاصيل التعرف على النص' : 'OCR Details'}</h2>
          </div>
          <CardBody>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-neutral-800/50 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Cpu className="w-4 h-4 text-primary" />
                  <span className="text-sm font-medium text-neutral-300">{language === 'ar' ? 'محرك التعرف' : 'Engine'}</span>
                </div>
                <p className="text-sm font-mono">{ocrEngine}</p>
              </div>
              <div className="bg-neutral-800/50 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle2 className="w-4 h-4 text-primary" />
                  <span className="text-sm font-medium text-neutral-300">{language === 'ar' ? 'ثقة التعرف' : 'OCR Confidence'}</span>
                </div>
                <p className={`text-sm font-mono ${
                  ocrConf >= 0.7 ? 'text-success-light' : ocrConf >= 0.5 ? 'text-warning-light' : 'text-danger-light'
                }`}>
                  {Math.round(ocrConf * 100)}%
                  {ocrPerFile[0]?.confidence_score?.status && ` (${ocrPerFile[0].confidence_score.status})`}
                </p>
              </div>
              <div className="bg-neutral-800/50 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <ArrowRight className="w-4 h-4 text-primary" />
                  <span className="text-sm font-medium text-neutral-300">{language === 'ar' ? 'محرك بديل' : 'Fallback'}</span>
                </div>
                <p className="text-sm font-mono">
                  {ocrFallback ?
                    (language === 'ar' ? 'نعم - تم استخدام PaddleOCR' : 'Yes — PaddleOCR used') :
                    (language === 'ar' ? 'لا - EasyOCR كافي' : 'No — EasyOCR sufficient')
                  }
                </p>
              </div>
              <div className="bg-neutral-800/50 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <FileText className="w-4 h-4 text-primary" />
                  <span className="text-sm font-medium text-neutral-300">{language === 'ar' ? 'اللغة' : 'Language'}</span>
                </div>
                <p className="text-sm font-mono">{langLabel}</p>
              </div>
            </div>
            {ocrPerFile.length > 1 && (
              <div className="mt-4">
                <h4 className="text-sm font-medium text-neutral-400 mb-2">{language === 'ar' ? 'ملخص لكل ملف' : 'Per-file summary'}</h4>
                <div className="space-y-2">
                  {ocrPerFile.map((f, i) => (
                    <div key={i} className="flex items-center justify-between bg-neutral-800/30 rounded px-3 py-2 text-sm">
                      <span className="text-neutral-300 truncate">{f.file || `File ${i + 1}`}</span>
                      <div className="flex items-center gap-4 shrink-0">
                        <span className="font-mono text-neutral-400">{f.engine || '—'}</span>
                        <span className={`font-mono ${(f.confidence || 0) >= 0.7 ? 'text-success-light' : (f.confidence || 0) >= 0.5 ? 'text-warning-light' : 'text-danger-light'}`}>
                          {Math.round((f.confidence || 0) * 100)}%
                        </span>
                        {f.fallback_triggered && (
                          <Badge variant="warning" size="sm">fallback</Badge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {result.entities && (
        <Card>
          <div className="px-6 py-4 border-b border-neutral-800">
            <h2 className="text-lg font-semibold">{t('analysis.entities')}</h2>
          </div>
          <CardBody>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { icon: Phone, labelKey: 'analysis.phones', items: result.entities.phones || [] },
                { icon: DollarSign, labelKey: 'analysis.amounts', items: result.entities.amounts || [] },
                { icon: Clock, labelKey: 'analysis.dates', items: result.entities.dates || [] },
                { icon: User, labelKey: 'analysis.accounts', items: result.entities.accounts || [] },
              ].map(({ icon: Icon, labelKey, items }) => (
                <div key={labelKey} className="bg-neutral-800/50 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Icon className="w-4 h-4 text-primary" />
                    <span className="text-sm font-medium text-neutral-300">{t(labelKey)}</span>
                  </div>
                  {items.length > 0 ? (
                    <div className="space-y-1.5">
                      {items.map((item, i) => (
                        <div key={i} className="text-sm font-mono bg-neutral-800 px-2.5 py-1.5 rounded">
                          {item.value || item}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-neutral-600">{t('analysis.noEntities')}</p>
                  )}
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      {/* RAG Metadata */}
      {result.rag_meta && (
        <Card>
          <div className="px-6 py-4 border-b border-neutral-800 flex items-center gap-2">
            <Scale className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold">{language === 'ar' ? 'تفاصيل الاسترجاع' : 'RAG Details'}</h2>
          </div>
          <CardBody>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-neutral-800/50 rounded-lg p-4">
                <span className="text-sm font-medium text-neutral-300 block mb-1">{language === 'ar' ? 'استراتيجية البحث' : 'Query Strategy'}</span>
                <p className="text-sm font-mono">{result.rag_meta.query_strategy || 'none'}</p>
              </div>
              <div className="bg-neutral-800/50 rounded-lg p-4">
                <span className="text-sm font-medium text-neutral-300 block mb-1">{language === 'ar' ? 'ذاكرة التخزين المؤقت' : 'Cache'}</span>
                <p className="text-sm font-mono">{result.rag_meta.cache_hit ? (language === 'ar' ? 'مطابق' : 'Hit') : (language === 'ar' ? 'غير مطابق' : 'Miss')}</p>
              </div>
              <div className="bg-neutral-800/50 rounded-lg p-4">
                <span className="text-sm font-medium text-neutral-300 block mb-1">{language === 'ar' ? 'زمن الاستجابة' : 'Latency'}</span>
                <p className="text-sm font-mono">{Math.round(result.rag_meta.latency_ms || 0)}ms</p>
              </div>
            </div>
          </CardBody>
        </Card>
      )}

      {result.articles?.length > 0 && (
        <Card>
          <div className="px-6 py-4 border-b border-neutral-800 flex items-center gap-2">
            <Scale className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold">{t('analysis.articles')}</h2>
          </div>
          <CardBody className="space-y-3">
            {result.articles.map((article, i) => (
              <div key={i} className="legal-article-box">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-semibold text-primary">
                    {language === 'ar' ? 'المادة' : 'Article'} {article.article_number} — {language === 'ar' ? 'القانون' : 'Law'} {article.law}
                  </span>
                  <Badge variant="primary">{Math.round((1 - article.relevance_score) * 100)}% match</Badge>
                </div>
                <p className="text-sm text-neutral-300 mb-1">{article.text}</p>
                {article.penalty_ar && (
                  <p className="text-xs text-neutral-500">{language === 'ar' ? 'العقوبة:' : 'Penalty:'} {article.penalty_ar}</p>
                )}
              </div>
            ))}
          </CardBody>
        </Card>
      )}

      {result.classification?.missing_evidence?.length > 0 && (
        <Card className="border-l-4 border-l-warning">
          <CardBody>
            <div className="flex items-center gap-2 mb-3">
              <AlertCircle className="w-5 h-5 text-warning" />
              <h3 className="font-semibold text-warning-light">{t('analysis.suggestions')}</h3>
            </div>
            <ul className="space-y-1.5">
              {result.classification.missing_evidence.map((item, i) => (
                <li key={i} className="text-sm text-neutral-400 flex items-start gap-2">
                  <span className="text-warning mt-0.5">—</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}

      {result.score?.breakdown && (
        <Card>
          <div className="px-6 py-4 border-b border-neutral-800">
            <h2 className="text-lg font-semibold">{t('analysis.scoreBreakdown')}</h2>
          </div>
          <CardBody className="space-y-3">
            {Object.entries(SCORE_WEIGHTS).map(([key, { label, weight }]) => {
              const labelKey = `analysis.${key.replace(/_/g, '')}`
              const earned = result.score.breakdown[key] || 0
              return (
                <div key={key} className="flex items-center justify-between">
                  <span className="text-sm text-neutral-300">{t(labelKey)}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-32 h-1.5 bg-neutral-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full transition-all"
                        style={{ width: `${(earned / weight) * 100}%` }}
                      />
                    </div>
                    <span className="text-sm font-mono text-neutral-400 w-14 text-right">
                      {earned}/{weight}
                    </span>
                  </div>
                </div>
              )
            })}
          </CardBody>
        </Card>
      )}

      {/* Verification Section - Full detailed verification results */}
      <VerificationSection
        caseId={result.case_id}
        result={result}
        caseData={{
          evidence_text: result.ocr ? result.ocr.per_file?.map(f => f.full_text).join(' ') : '',
          entities: result.entities,
          classification: result.classification,
          articles: result.articles,
          evidence_blocks: result.ocr?.evidence_blocks || result.ocr?.per_file || [],
          session_id: null, // Could be passed from chat context if available
        }}
      />
    </div>
  )
}
