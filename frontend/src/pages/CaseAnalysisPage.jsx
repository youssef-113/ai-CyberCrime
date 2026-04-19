import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, FileImage, FileText, X, AlertCircle, CheckCircle2, Clock, Phone, User, DollarSign, Scale, Download, RotateCcw, ChevronRight } from 'lucide-react'
import { Card, CardBody } from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import { ProgressBar, PipelineProgress, Spinner } from '../components/ui/ProgressIndicator'
import { useAnalyze, usePdfDownload } from '../api/hooks'
import { validateFile, validateFileList } from '../utils/validators'
import { formatFileSize, getGradeInfo, getCrimeTypeInfo, scoreToColor, scoreToBgColor } from '../utils/formatters'
import { FILE_CONSTRAINTS, SCORE_WEIGHTS, VERIFICATION_STATUS } from '../utils/constants'
import toast from 'react-hot-toast'

const PIPELINE_STEPS = ['Upload', 'OCR', 'Classify', 'RAG', 'Verify', 'Score', 'PDF']

export default function CaseAnalysisPage() {
  const [files, setFiles] = useState([])
  const [dragActive, setDragActive] = useState(false)
  const [pipelineStep, setPipelineStep] = useState(-1)
  const [result, setResult] = useState(null)
  const { analyze, loading, progress, error } = useAnalyze()
  const { download, loading: downloading } = usePdfDownload()

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
      toast.error(`${invalidNew.length} file(s) rejected: ${invalidNew[0].errors[0]}`)
    }

    setFiles((prev) => {
      const combined = [...prev, ...validNew]
      if (combined.length > FILE_CONSTRAINTS.MAX_FILES) {
        toast.error(`Maximum ${FILE_CONSTRAINTS.MAX_FILES} files`)
        return combined.slice(0, FILE_CONSTRAINTS.MAX_FILES)
      }
      return combined
    })
  }

  const removeFile = (id) => setFiles((prev) => prev.filter((f) => f.id !== id))

  const handleAnalyze = async () => {
    const validation = validateFileList(files.map((f) => f.file))
    if (!validation.valid) {
      toast.error(validation.errors[0])
      return
    }

    setPipelineStep(0)
    setResult(null)

    try {
      const stepTimer = setInterval(() => {
        setPipelineStep((prev) => (prev < PIPELINE_STEPS.length - 1 ? prev + 1 : prev))
      }, 4000)

      const data = await analyze(files, true)
      clearInterval(stepTimer)
      setPipelineStep(PIPELINE_STEPS.length - 1)
      setResult(data)
      toast.success('Analysis complete!')
    } catch (err) {
      setPipelineStep(-1)
      toast.error(error || 'Analysis failed')
    }
  }

  const handleDownload = async () => {
    if (result?.case_id) {
      try {
        await download(result.case_id)
        toast.success('PDF downloaded!')
      } catch {
        toast.error('Download failed')
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
    <div className="space-y-6">
      <div>
        <h1 className="section-title">New Case Analysis</h1>
        <p className="section-subtitle">Upload evidence and run the AI pipeline</p>
      </div>

      {pipelineStep >= 0 && loading ? (
        <Card variant="elevated">
          <CardBody className="py-12">
            <div className="flex flex-col items-center gap-6">
              <Spinner size="lg" />
              <PipelineProgress steps={PIPELINE_STEPS} currentStep={pipelineStep} className="w-full max-w-2xl" />
              <p className="text-neutral-400 text-sm">
                Processing through {PIPELINE_STEPS[pipelineStep]} stage...
              </p>
              <ProgressBar value={progress} label="Upload progress" className="w-full max-w-md" />
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
                <p className="text-lg mb-1">Drag & drop your evidence files</p>
                <p className="text-sm text-neutral-500 mb-4">
                  PNG, JPG, PDF — max {FILE_CONSTRAINTS.MAX_SIZE_MB}MB each, up to {FILE_CONSTRAINTS.MAX_FILES} files
                </p>
                <label htmlFor="case-file-upload" className="btn-primary inline-block cursor-pointer">
                  Select Files
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
                <h3 className="font-semibold">Uploaded Files ({files.length})</h3>
                <Button variant="danger" size="sm" onClick={() => setFiles([])}>Clear All</Button>
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
                  Analyze Evidence
                  <ChevronRight className="w-4 h-4" />
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
  const gradeInfo = getGradeInfo(result.score?.total_score || 0)
  const crimeInfo = getCrimeTypeInfo(result.classification?.crime_type || 'unknown')
  const verificationStatus = VERIFICATION_STATUS[result.verification?.status] || VERIFICATION_STATUS.NEEDS_USER_REVIEW

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="section-title">Analysis Results</h1>
          <p className="section-subtitle">Case {result.case_id}</p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={onReset} className="gap-2">
            <RotateCcw className="w-4 h-4" />
            New Case
          </Button>
          <Button onClick={onDownload} loading={downloading} className="gap-2">
            <Download className="w-4 h-4" />
            Download PDF
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardBody className="text-center">
            <p className={`stat-value ${scoreToColor(result.score?.total_score || 0)}`}>
              {result.score?.total_score || 0}%
            </p>
            <p className="stat-label">Evidence Strength</p>
            <Badge variant={gradeInfo.color} className="mt-2">{gradeInfo.label}</Badge>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="text-center">
            <p className="stat-value text-primary">{Math.round((result.classification?.confidence || 0) * 100)}%</p>
            <p className="stat-label">Classification Confidence</p>
            <Badge variant={crimeInfo.color} className="mt-2">{crimeInfo.en}</Badge>
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
            <p className="stat-label">Verification Rounds</p>
            <Badge variant={verificationStatus.color} className="mt-2">{verificationStatus.label}</Badge>
          </CardBody>
        </Card>
      </div>

      {result.entities && (
        <Card>
          <div className="px-6 py-4 border-b border-neutral-800">
            <h2 className="text-lg font-semibold">Extracted Entities</h2>
          </div>
          <CardBody>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { icon: Phone, label: 'Phone Numbers', items: result.entities.phones || [] },
                { icon: DollarSign, label: 'Financial Amounts', items: result.entities.amounts || [] },
                { icon: Clock, label: 'Dates', items: result.entities.dates || [] },
                { icon: User, label: 'Accounts', items: result.entities.accounts || [] },
              ].map(({ icon: Icon, label, items }) => (
                <div key={label} className="bg-neutral-800/50 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Icon className="w-4 h-4 text-primary" />
                    <span className="text-sm font-medium text-neutral-300">{label}</span>
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
                    <p className="text-xs text-neutral-600">None detected</p>
                  )}
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      )}

      {result.articles?.length > 0 && (
        <Card>
          <div className="px-6 py-4 border-b border-neutral-800 flex items-center gap-2">
            <Scale className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold">Retrieved Law Articles</h2>
          </div>
          <CardBody className="space-y-3">
            {result.articles.map((article, i) => (
              <div key={i} className="legal-article-box">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-semibold text-primary">
                    Article {article.article_number} — Law {article.law}
                  </span>
                  <Badge variant="primary">{Math.round((1 - article.relevance_score) * 100)}% match</Badge>
                </div>
                <p className="text-sm text-neutral-300 mb-1">{article.text}</p>
                {article.penalty_ar && (
                  <p className="text-xs text-neutral-500">Penalty: {article.penalty_ar}</p>
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
              <h3 className="font-semibold text-warning-light">Suggestions for Stronger Evidence</h3>
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
            <h2 className="text-lg font-semibold">Score Breakdown</h2>
          </div>
          <CardBody className="space-y-3">
            {Object.entries(SCORE_WEIGHTS).map(([key, { label, weight }]) => {
              const earned = result.score.breakdown[key] || 0
              return (
                <div key={key} className="flex items-center justify-between">
                  <span className="text-sm text-neutral-300">{label}</span>
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
    </div>
  )
}
