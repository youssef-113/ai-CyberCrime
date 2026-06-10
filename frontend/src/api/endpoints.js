import client from './client'

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

export const healthCheck = async () => {
  const response = await client.get('/health')
  return response.data
}

export const getHealthAggregate = async () => {
  const response = await client.get('/health/aggregate')
  return response.data
}

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

export const analyzeEvidenceBackground = async (files) => {
  const formData = new FormData()
  files.forEach((f) => formData.append('files', f.file || f))

  const config = {
    headers: { 'Content-Type': 'multipart/form-data' },
  }

  const response = await client.post('/analyze', formData, config)
  return response.data
}

export const subscribeCaseEvents = (caseId, accessToken, onUpdate, onDone, onError) => {
  const baseUrl = client.defaults.baseURL || window.location.origin
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

export const downloadPdf = async (caseId) => {
  const response = await client.get(`/pdf/${caseId}`, {
    responseType: 'blob',
  })
  return response.data
}

export const getCaseReport = async (caseId) => {
  // Returns JSON report for a case; falls back to /cases/{id}
  try {
    const response = await client.get(`/cases/${caseId}`)
    return response.data
  } catch (e) {
    throw e
  }
}

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

export const uploadChatDocuments = async (files, sessionId) => {
  const formData = new FormData()
  files.forEach(file => formData.append('files', file))
  if (sessionId) {
    formData.append('session_id', sessionId)
  }

  const response = await client.post('/chat/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

export const resetChat = async (sessionId) => {
  const response = await client.post('/chat/reset', { session_id: sessionId })
  return response.data
}

export const getChatHistory = async (sessionId) => {
  const response = await client.get(`/chat/history?session_id=${sessionId}`)
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

export const classifyCrime = async (text, entities, userId = null, sessionId = null) => {
  const response = await client.post('/classify', {
    text,
    entities,
    user_id: userId,
    session_id: sessionId,
  })
  return response.data
}

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

// Verification audit endpoints
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

// Trigger verification from existing case (for "Verify" button in case view)
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

export const generatePdf = async (caseData) => {
  const response = await client.post('/generate', caseData, {
    responseType: 'blob',
  })
  return response.data
}
