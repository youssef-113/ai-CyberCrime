import { useState, useCallback, useRef } from 'react'
import * as endpoints from './endpoints'

export function useAnalyze() {
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)

  const analyze = useCallback(async (files, jsonMode = true) => {
    setLoading(true)
    setProgress(0)
    setError(null)
    try {
      const fn = jsonMode ? endpoints.analyzeEvidenceJson : endpoints.analyzeEvidence
      const data = await fn(files, (p) => setProgress(p))
      return data
    } catch (err) {
      const message = err.response?.data?.detail || err.message || 'Analysis failed'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return { analyze, loading, progress, error }
}

export function useChat(caseContext) {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const sessionIdRef = useRef(`session_${Date.now()}`)

  const sendMessage = useCallback(async (content) => {
    setLoading(true)
    setError(null)
    const userMessage = { role: 'user', content, timestamp: new Date().toISOString() }
    setMessages((prev) => [...prev, userMessage])

    try {
      const response = await endpoints.sendChatMessage(
        sessionIdRef.current,
        content,
        caseContext
      )
      const aiMessage = {
        role: 'assistant',
        content: response.reply || response.content || response,
        timestamp: new Date().toISOString(),
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
  }, [caseContext])

  const clearChat = useCallback(() => {
    setMessages([])
    sessionIdRef.current = `session_${Date.now()}`
  }, [])

  return { messages, sendMessage, loading, error, clearChat }
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

  const classify = useCallback(async (text, entities) => {
    setLoading(true)
    setError(null)
    try {
      const data = await endpoints.classifyCrime(text, entities)
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

  const retrieve = useCallback(async (query, crimeType, topK = 5) => {
    setLoading(true)
    setError(null)
    try {
      const data = await endpoints.retrieveArticles(query, crimeType, topK)
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

  const verify = useCallback(async (evidenceText, entities, classification, articles) => {
    setLoading(true)
    setError(null)
    try {
      const data = await endpoints.verifyEvidence(evidenceText, entities, classification, articles)
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
