import { useState, useCallback, useRef, useEffect } from 'react'
import * as endpoints from './endpoints'
import { useAuth } from '../context/AuthContext'

export function useAnalyze() {
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [stage, setStage] = useState(null)
  const [error, setError] = useState(null)
  const eventSourceRef = useRef(null)
  const { token } = useAuth()

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  const analyze = useCallback(async (files, jsonMode = true) => {
    setLoading(true)
    setProgress(0)
    setStage(null)
    setError(null)

    const cleanup = () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }

    try {
      if (jsonMode) {
        const data = await endpoints.analyzeEvidenceJson(files, (p) => setProgress(p))
        return data
      }

      const response = await endpoints.analyzeEvidenceBackground(files)
      const caseId = response?.case_id
      if (!caseId) {
        throw new Error('Failed to start background analysis')
      }

      return await new Promise((resolve, reject) => {
        eventSourceRef.current = endpoints.subscribeCaseEvents(
          caseId,
          token,
          (payload) => {
            if (payload.stage) {
              setStage(payload.stage)
            }
            if (typeof payload.progress === 'number') {
              setProgress(payload.progress)
            }
          },
          (payload) => {
            cleanup()
            if (payload.result) {
              resolve(payload.result)
            } else {
              resolve(payload)
            }
          },
          (error) => {
            cleanup()
            const message = error?.message || 'Event stream failed'
            setError(message)
            reject(new Error(message))
          }
        )
      })
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Analysis failed'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [token])

  return { analyze, loading, progress, stage, error }
}

export function useChat(caseContext, initialSessionId = null) {
  const { sessionId: authSessionId, tenantId, createChatSession, getCurrentSessionId } = useAuth()
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [sessionLoading, setSessionLoading] = useState(false)
  const sessionIdRef = useRef(initialSessionId || authSessionId || `session_${Date.now()}`)

  // Sync with auth session when it becomes available
  useEffect(() => {
    const currentSession = getCurrentSessionId()
    if (currentSession && !initialSessionId) {
      sessionIdRef.current = currentSession
      loadHistory(currentSession)
    }
  }, [authSessionId])

  // Load chat history when initialSessionId changes
  useEffect(() => {
    if (initialSessionId) {
      sessionIdRef.current = initialSessionId
      loadHistory(initialSessionId)
    }
  }, [initialSessionId])

  const loadHistory = useCallback(async (sessionId) => {
    setSessionLoading(true)
    try {
      const data = await endpoints.getChatHistory(sessionId)
      if (data.messages && data.messages.length > 0) {
        // Convert to frontend format
        const loadedMessages = data.messages.map(msg => ({
          role: msg.role,
          content: msg.content,
          timestamp: msg.created_at || new Date().toISOString(),
          citations: msg.citations ? JSON.parse(msg.citations) : undefined,
        }))
        setMessages(loadedMessages)
      }
    } catch (err) {
      console.error('Failed to load chat history:', err)
    } finally {
      setSessionLoading(false)
    }
  }, [])

  const sendMessage = useCallback(async (content) => {
    setLoading(true)
    setError(null)
    const userMessage = { role: 'user', content, timestamp: new Date().toISOString() }
    setMessages((prev) => [...prev, userMessage])

    // Ensure we have a valid session ID
    let sid = sessionIdRef.current
    if (!sid || sid.startsWith('session_')) {
      try {
        sid = await createChatSession()
        sessionIdRef.current = sid
      } catch (err) {
        console.warn('Could not create session, using current:', err)
      }
    }

    try {
      const response = await endpoints.sendChatMessage(
        sid,
        content,
        caseContext,
        'ar', // default language
        messages.slice(-10).map(m => ({ role: m.role, content: m.content })) // recent history
      )
      const aiMessage = {
        role: 'assistant',
        content: response.reply || response.content || response,
        timestamp: new Date().toISOString(),
        citations: response.citations,
        confidence_score: response.confidence_score,
        model_used: response.model_used,
        tokens_used: response.tokens_used,
        latency_ms: response.latency_ms,
      }
      setMessages((prev) => [...prev, aiMessage])
      return aiMessage
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Chat failed'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [caseContext, createChatSession, messages])

  const clearChat = useCallback(async () => {
    setMessages([])
    try {
      const newSid = await createChatSession()
      sessionIdRef.current = newSid
    } catch {
      sessionIdRef.current = `session_${Date.now()}`
    }
  }, [createChatSession])

  return { messages, sendMessage, loading, error, clearChat, sessionId: sessionIdRef.current, sessionLoading, loadHistory }
}

export function usePdfDownload() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const download = useCallback(async (caseId) => {
    setLoading(true)
    setError(null)
    try {
      const blob = await endpoints.downloadPdf(caseId)
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `Cybercrime_AI_Report_${caseId}.pdf`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Download failed'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return { download, loading, error }
}

export function useCases() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchCases = useCallback(async (params = {}) => {
    setLoading(true)
    setError(null)
    try {
      const data = await endpoints.getCaseHistory(params)
      setCases(Array.isArray(data) ? data : [])
      return data
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Failed to fetch cases'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchCase = useCallback(async (caseId) => {
    setLoading(true)
    setError(null)
    try {
      const data = await endpoints.getCaseById(caseId)
      return data
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Failed to fetch case'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return { cases, fetchCases, fetchCase, loading, error }
}

export function useHealthCheck() {
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const checkHealth = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await endpoints.healthCheck()
      setHealth(data)
      return data
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Health check failed'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return { health, checkHealth, loading, error }
}

export function useChatHistory() {
  const [history, setHistory] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchHistory = useCallback(async (sessionId) => {
    setLoading(true)
    setError(null)
    try {
      const data = await endpoints.getChatHistory(sessionId)
      setHistory(data)
      return data
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Failed to fetch chat history'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return { history, fetchHistory, loading, error }
}

export function useSessions() {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchSessions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await endpoints.listSessions()
      setSessions(data.sessions || [])
      return data
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Failed to fetch sessions'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return { sessions, fetchSessions, loading, error }
}

export function useOcr() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  const extract = useCallback(async (file) => {
    setLoading(true)
    setError(null)
    try {
      const data = await endpoints.extractText(file)
      setResult(data)
      return data
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'OCR extraction failed'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return { extract, result, loading, error }
}

export function useOcrBatch() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  const extractBatch = useCallback(async (files) => {
    setLoading(true)
    setError(null)
    try {
      const data = await endpoints.extractTextBatch(files)
      setResult(data)
      return data
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Batch OCR failed'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return { extractBatch, result, loading, error }
}

export function useOcrEngines() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const checkStatus = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await endpoints.getOcrEnginesStatus()
      setStatus(data)
      return data
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Failed to check OCR engines'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return { status, checkStatus, loading, error }
}

export function useClassification() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const classify = useCallback(async (text, entities, userId = null, sessionId = null) => {
    setLoading(true)
    setError(null)
    try {
      const data = await endpoints.classifyCrime(text, entities, userId, sessionId)
      return data
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Classification failed'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return { classify, loading, error }
}

export function useRag() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const retrieve = useCallback(async (query, crimeType, topK = 5, options = {}) => {
    setLoading(true)
    setError(null)
    try {
      const data = await endpoints.retrieveArticles(query, crimeType, topK, options)
      return data
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Article retrieval failed'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return { retrieve, loading, error }
}

export function useVerification() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const verify = useCallback(async (evidenceText, entities, classification, articles, userId = null, sourceCaseId = null) => {
    setLoading(true)
    setError(null)
    try {
      const data = await endpoints.verifyEvidence(evidenceText, entities, classification, articles, [], null, null, userId, sourceCaseId)
      return data
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Verification failed'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return { verify, loading, error }
}

export function usePdfGeneration() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const generate = useCallback(async (caseData) => {
    setLoading(true)
    setError(null)
    try {
      const blob = await endpoints.generatePdf(caseData)
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `complaint_${caseData.case_id}.pdf`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
      return blob
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'PDF generation failed'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return { generate, loading, error }
}
