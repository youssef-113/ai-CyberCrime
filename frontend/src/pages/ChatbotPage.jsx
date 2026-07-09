import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Trash2, Bot, User, Scale, Upload, FileText, X, Paperclip } from 'lucide-react'
import { Card, CardBody } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { Spinner } from '../components/ui/ProgressIndicator'
import { useChat } from '../api/hooks'
import { useCase } from '../context/CaseContext'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { getTranslation } from '../utils/translations'
import { uploadChatDocuments } from '../api/endpoints'
import useAlerts from '../hooks/useAlerts'
import clsx from 'clsx'

export default function ChatbotPage() {
  const { analysisResult } = useCase()
  const caseContext = analysisResult || {}
  const { sessionId: authSessionId, isAuthenticated } = useAuth()
  const { messages, sendMessage, loading, error, clearChat, sessionId } = useChat(caseContext, authSessionId)
  const [input, setInput] = useState('')
  const [uploadedFiles, setUploadedFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [showUpload, setShowUpload] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const fileInputRef = useRef(null)
  const { language, isRtl } = useTheme()
  const alerts = useAlerts()

  const t = (key) => getTranslation(language, key)

  const WELCOME_MESSAGE = {
    role: 'assistant',
    content: t('chatbot.welcome'),
    timestamp: new Date().toISOString(),
  }

  const allMessages = [WELCOME_MESSAGE, ...messages]

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (e) => {
    e.preventDefault()
    const trimmed = input.trim()
    if (!trimmed || loading) return
    setInput('')
    await sendMessage(trimmed)
    inputRef.current?.focus()
  }

  const handleFileSelect = useCallback((e) => {
    const files = Array.from(e.target.files)
    if (files.length > 0) {
      setUploadedFiles(prev => [...prev, ...files])
    }
  }, [])

  const removeFile = useCallback((index) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== index))
  }, [])

  const handleUpload = useCallback(async () => {
    if (uploadedFiles.length === 0) return

    setUploading(true)
    alerts.uploadStart()
    try {
      const result = await uploadChatDocuments(uploadedFiles, sessionId)
      setUploadedFiles([])
      setShowUpload(false)
      alerts.uploadSuccess(uploadedFiles.length)
    } catch (err) {
      alerts.uploadFailed(err)
      console.error(err)
    } finally {
      setUploading(false)
    }
  }, [uploadedFiles, sessionId, alerts])

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]" dir={isRtl ? 'rtl' : 'ltr'}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
            <Scale className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h1 className="section-title text-lg">{t('chatbot.title')}</h1>
            <p className="text-xs text-neutral-500">{t('chatbot.subtitle')}</p>
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={clearChat} className="gap-1.5">
          <Trash2 className="w-3.5 h-3.5" />
          {t('chatbot.clear')}
        </Button>
      </div>

      <Card variant="elevated" className="flex-1 flex flex-col min-h-0">
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {allMessages.map((msg, i) => (
            <div
              key={i}
              className={clsx(
                'flex gap-3 max-w-[85%]',
                msg.role === 'user' ? 'ml-auto flex-row-reverse' : 'mr-auto'
              )}
            >
              <div
                className={clsx(
                  'w-8 h-8 rounded-full flex items-center justify-center shrink-0',
                  msg.role === 'user' ? 'bg-primary/20' : 'bg-neutral-800'
                )}
              >
                {msg.role === 'user' ? (
                  <User className="w-4 h-4 text-primary" />
                ) : (
                  <Bot className="w-4 h-4 text-accent-blue" />
                )}
              </div>
              <div
                className={clsx(
                  msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-ai',
                  'text-sm leading-relaxed'
                )}
              >
                {msg.content}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex gap-3 mr-auto max-w-[85%]">
              <div className="w-8 h-8 rounded-full bg-neutral-800 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-accent-blue" />
              </div>
              <div className="chat-bubble-ai flex items-center gap-2">
                <Spinner size="sm" />
                <span className="text-sm text-neutral-400">{t('chatbot.thinking')}</span>
              </div>
            </div>
          )}

          {error && (
            <div className="text-center">
              <p className="text-sm text-danger-light">{error}</p>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* File Upload Panel */}
        {showUpload && (
          <div className="p-4 border-t border-neutral-800 bg-neutral-900/50">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-neutral-300">{t('chatbot.uploadDocs')}</h3>
              <button onClick={() => setShowUpload(false)} className="text-neutral-400 hover:text-neutral-200">
                <X className="w-4 h-4" />
              </button>
            </div>

            {uploadedFiles.length === 0 ? (
              <div
                className="border-2 border-dashed border-neutral-700 rounded-lg p-6 text-center cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="w-8 h-8 mx-auto mb-2 text-neutral-400" />
                <p className="text-sm text-neutral-400">{t('chatbot.uploadDesc')}</p>
                <p className="text-xs text-neutral-500 mt-1">{t('chatbot.uploadFormats')}</p>
              </div>
            ) : (
              <div className="space-y-2">
                {uploadedFiles.map((file, idx) => (
                  <div key={idx} className="flex items-center justify-between bg-neutral-800/50 rounded-lg px-3 py-2">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-primary" />
                      <span className="text-sm text-neutral-300 truncate max-w-[200px]">{file.name}</span>
                      <span className="text-xs text-neutral-500">({(file.size / 1024).toFixed(1)} KB)</span>
                    </div>
                    <button onClick={() => removeFile(idx)} className="text-neutral-400 hover:text-danger-light">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
                <div className="flex gap-2 mt-3">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => fileInputRef.current?.click()}
                    className="flex-1"
                  >
                    {t('chatbot.addMore')}
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleUpload}
                    loading={uploading}
                    className="flex-1"
                  >
                    {t('chatbot.uploadFiles')}
                  </Button>
                </div>
              </div>
            )}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.png,.jpg,.jpeg"
              onChange={handleFileSelect}
              className="hidden"
            />
          </div>
        )}

        <form onSubmit={handleSend} className="p-4 border-t border-neutral-800">
          <div className="flex gap-3">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="shrink-0 w-11 h-11"
              onClick={() => setShowUpload(!showUpload)}
              title="Upload documents for chat"
            >
              <Paperclip className={clsx("w-5 h-5", showUpload && "text-primary")} />
            </Button>
            <Input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t('chatbot.placeholder')}
              className="flex-1"
              disabled={loading}
            />
            <Button type="submit" disabled={!input.trim() || loading} size="icon" className="shrink-0 w-11 h-11">
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}
