import client from './client'

// NOTE: client.baseURL already includes the gateway prefix (/api). Every path
// here is therefore relative to the gateway (services/api/main.py), which is
// the only layer that enforces auth and persists to the database.

// ── Evidence analysis (full pipeline) ───────────────────────────────────────
export const analyzeEvidence = async (files, onProgress) => {
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f.file || f))

  const config = {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded * 100) / event.total))
      }
    },
  }

  const response = await client.post('/analyze', formData, config)
  return response.data
}

export const analyzeEvidenceJson = async (files, onProgress) => {
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f.file || f))

  const config = {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded * 100) / event.total))
      }
    },
  }

  const response = await client.post('/analyze/json', formData, config)
  return response.data
}

export const analyzeEvidenceBackground = async (files) => {
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f.file || f))

  const config = {
    headers: { 'Content-Type': 'multipart/form-data' },
  }

  const response = await client.post('/analyze', formData, config)
  return response.data
}

// ── Health & metrics ────────────────────────────────────────────────────────
export const healthCheck = async () => {
  const response = await client.get('/health')
  return response.data
}

export const getHealthAggregate = async () => {
  const response = await client.get('/health/aggregate')
  return response.data
}

// ── Cases ───────────────────────────────────────────────────────────────────
export const getCaseHistory = async (params = {}) => {
  const response = await client.get('/cases', { params })
  return response.data
}

export const getCaseById = async (caseId) => {
  const response = await client.get(`/cases/${caseId}`)
  return response.data
}

export const getCaseStatus = async (caseId) => {
  // Alias to getCaseById for status polling
  const response = await client.get(`/cases/${caseId}`)
  return response.data
}

export const getCaseReport = async (caseId) => {
  const response = await client.get(`/cases/${caseId}`)
  return response.data
}

export const subscribeCaseEvents = (caseId, accessToken, onUpdate, onDone, onError) => {
  // client.defaults.baseURL already ends with /api
  const baseUrl = client.defaults.baseURL || `${window.location.origin}/api`
  const tokenQuery = accessToken ? `?access_token=${encodeURIComponent(accessToken)}` : ''
  const source = new EventSource(`${baseUrl}/cases/${caseId}/events${tokenQuery}`)

  const parseEvent = (event) => {
    if (!event.data) return null
    try {
      return JSON.parse(event.data)
    } catch (error) {
      console.error('Failed to parse event data', error)
      return null
    }
  }

  source.addEventListener('update', (event) => {
    const payload = parseEvent(event)
    if (payload && onUpdate) onUpdate(payload)
  })

  source.addEventListener('done', (event) => {
    const payload = parseEvent(event)
    if (payload && onDone) onDone(payload)
    source.close()
  })

  source.onerror = (error) => {
    if (onError) onError(error)
    source.close()
  }

  return source
}

// ── PDF ─────────────────────────────────────────────────────────────────────
export const downloadPdf = async (caseId) => {
  const response = await client.get(`/pdf/${caseId}`, {
    responseType: 'blob',
  })
  return response.data
}

// ── Chat ────────────────────────────────────────────────────────────────────
export const sendChatMessage = async (sessionId, message, caseContext, language = 'ar', history = null) => {
  const response = await client.post('/chat', {
    session_id: sessionId,
    user_message: message,
    case_context: caseContext,
    language,
    history,
  })
  return response.data
}

export const resetChat = async (sessionId) => {
  const response = await client.post('/chat/reset', { session_id: sessionId })
  return response.data
}

export const getChatHistory = async (sessionId, limit = 50) => {
  const response = await client.get('/chat/history', {
    params: { session_id: sessionId, limit },
  })
  return response.data
}

export const listSessions = async () => {
  const response = await client.get('/sessions/list')
  return response.data
}

export const triggerPdfFromChat = async (sessionId) => {
  const response = await client.post('/chat/pdf_trigger', { session_id: sessionId })
  return response.data
}

// Upload documents into a chat session (OCR + index into the session RAG store).
// Maps to gateway POST /chat/upload (session_id is a query param there).
export const uploadChatDocuments = async (files, sessionId) => {
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f.file || f))
  const response = await client.post('/chat/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params: { session_id: sessionId || '' },
  })
  return response.data // { indexed, files_processed, session_id, message }
}

// ── OCR (synchronous) ───────────────────────────────────────────────────────
export const extractText = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  const response = await client.post('/ocr/extract', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export const extractTextBatch = async (files) => {
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f.file || f))
  const response = await client.post('/ocr/extract/batch', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export const getOcrEnginesStatus = async () => {
  const response = await client.get('/ocr/engines/status')
  return response.data
}

// ── OCR (async Celery jobs) ─────────────────────────────────────────────────
export const uploadOcrJob = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  const response = await client.post('/ocr/jobs/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data // { job_id, status, message }
}

export const getOcrJobStatus = async (jobId) => {
  const response = await client.get(`/ocr/jobs/${jobId}/status`)
  return response.data // { job_id, status, message }
}

export const getOcrJobResult = async (jobId) => {
  const response = await client.get(`/ocr/jobs/${jobId}/result`)
  return response.data // { job_id, status, result, error }
}

export const retryOcrJob = async (jobId) => {
  const response = await client.post(`/ocr/jobs/${jobId}/retry`)
  return response.data // { job_id, status, message }
}

// ── Classification ──────────────────────────────────────────────────────────
export const classifyCrime = async (text, entities, userId = null, sessionId = null) => {
  const response = await client.post('/classify', {
    text,
    entities,
    user_id: userId,
    session_id: sessionId,
  })
  return response.data
}

// ── RAG ─────────────────────────────────────────────────────────────────────
export const retrieveArticles = async (query, crimeType, topK = 5, options = {}) => {
  const response = await client.post('/retrieve', {
    query,
    crime_type: crimeType,
    top_k: topK,
    tenant_id: options.tenantId || 'default',
    transform_strategy: options.transformStrategy || 'auto',
    user_id: options.userId || null,
    session_id: options.sessionId || null,
  })
  return response.data
}

export const checkFaithfulness = async (query, answer, citations = []) => {
  const response = await client.post('/faithfulness', {
    query,
    answer,
    citations,
  })
  return response.data
}

export const getRagStats = async () => {
  const response = await client.get('/stats')
  return response.data
}

export const indexArticles = async (articles, tenantId = 'default', asyncIngest = false, userId = null, caseId = null) => {
  const response = await client.post('/index', {
    articles,
    tenant_id: tenantId,
    async_ingest: asyncIngest,
    user_id: userId,
    case_id: caseId,
  })
  return response.data
}

// ── Verification (multi-agent) ──────────────────────────────────────────────
export const verifyEvidence = async (evidenceText, entities, classification, articles, evidenceBlocks = [], caseId = null, sessionId = null, userId = null, sourceCaseId = null) => {
  const response = await client.post('/verify', {
    evidence_text: evidenceText,
    extracted_entities: entities,
    classification,
    retrieved_articles: articles,
    evidence_blocks: evidenceBlocks,
    case_id: caseId,
    session_id: sessionId,
    user_id: userId,
    source_case_id: sourceCaseId,
  })
  return response.data
}

export const getVerifications = async (params = {}) => {
  const response = await client.get('/verifications', { params })
  return response.data
}

export const getVerificationById = async (verificationId) => {
  const response = await client.get(`/verifications/${verificationId}`)
  return response.data
}

export const getVerificationRounds = async (verificationId) => {
  const response = await client.get(`/verifications/${verificationId}/rounds`)
  return response.data
}

export const getVerificationAudit = async (verificationId) => {
  const response = await client.get(`/verifications/${verificationId}/audit`)
  return response.data
}

// Trigger verification from an existing case (the "Verify" button in case view)
export const triggerCaseVerification = async (caseId, caseData, userId = null) => {
  const response = await client.post('/verify', {
    evidence_text: caseData.evidence_text || caseData.text,
    extracted_entities: caseData.entities || {},
    classification: caseData.classification || { crime_type: 'unknown', confidence: 0 },
    retrieved_articles: caseData.articles || [],
    evidence_blocks: caseData.evidence_blocks || [],
    case_id: caseId,
    session_id: caseData.session_id || null,
    user_id: userId,
    source_case_id: caseId,
  })
  return response.data
}
