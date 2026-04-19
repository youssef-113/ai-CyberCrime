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
      link.download = `Cybercrime AI_Report_${caseId}.pdf`
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
