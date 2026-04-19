import { useState, useRef, useEffect } from 'react'
import { Send, Trash2, Bot, User, Scale } from 'lucide-react'
import { Card, CardBody } from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { Spinner } from '../components/ui/ProgressIndicator'
import { useChat } from '../api/hooks'
import { useCase } from '../context/CaseContext'
import clsx from 'clsx'

const WELCOME_MESSAGE = {
  role: 'assistant',
  content: 'Welcome to the Cybercrime AI Legal Chatbot. I can answer questions about Egyptian cybercrime law (Law 175/2018) and help you understand your case. What would you like to know?',
  timestamp: new Date().toISOString(),
}

export default function ChatbotPage() {
  const { analysisResult } = useCase()
  const caseContext = analysisResult || {}
  const { messages, sendMessage, loading, error, clearChat } = useChat(caseContext)
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

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

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
            <Scale className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h1 className="section-title text-lg">Legal Chatbot</h1>
            <p className="text-xs text-neutral-500">Egyptian Cybercrime Law Advisor</p>
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={clearChat} className="gap-1.5">
          <Trash2 className="w-3.5 h-3.5" />
          Clear
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
                <span className="text-sm text-neutral-400">Thinking...</span>
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

        <form onSubmit={handleSend} className="p-4 border-t border-neutral-800">
          <div className="flex gap-3">
            <Input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about Egyptian cybercrime law..."
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
