import { useEffect, useRef, useState } from 'react'
import type { Message } from '../types/session'
import { getSession } from '../api/sessions'
import { useSSE } from '../hooks/useSSE'
import { ChatInput } from './ChatInput'
import { MessageBubble, StreamingBubble } from './MessageBubble'

interface Props {
  sessionId: string
}

export function ChatWindow({ sessionId }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [loadingMessages, setLoadingMessages] = useState(true)
  const bottomRef = useRef<HTMLDivElement>(null)
  const mountedRef = useRef(true)
  const { streaming, tokens, sources, error, sendMessage, reset } = useSSE(sessionId)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  useEffect(() => {
    setLoadingMessages(true)
    setMessages([])
    reset()
    getSession(sessionId)
      .then(s => setMessages(s.messages))
      .catch(() => setMessages([]))
      .finally(() => setLoadingMessages(false))
  }, [sessionId, reset])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, tokens])

  function handleSend(content: string) {
    const optimisticUser: Message = {
      id: crypto.randomUUID(),
      session_id: sessionId,
      role: 'user',
      content,
      sources: null,
      created_at: new Date().toISOString(),
    }
    setMessages(prev => [...prev, optimisticUser])

    sendMessage(content, () => {
      getSession(sessionId).then(s => {
        if (mountedRef.current) setMessages(s.messages)
      })
    })
  }

  return (
    <div className='flex flex-1 flex-col overflow-hidden'>
      <div className='flex-1 overflow-y-auto bg-white px-6 py-4 dark:bg-gray-900'>
        {loadingMessages && (
          <p className='text-center text-sm text-gray-400 dark:text-gray-500'>Loading messages...</p>
        )}

        {!loadingMessages && messages.length === 0 && !streaming && (
          <div className='flex h-full flex-col items-center justify-center gap-5 text-center'>
            <div>
              <p className='text-base font-medium text-gray-600 dark:text-gray-300'>Ask anything about the docs</p>
              <p className='mt-1 text-sm text-gray-400 dark:text-gray-500'>
                Try one of these to get started
              </p>
            </div>
            <div className='flex flex-wrap justify-center gap-2 max-w-lg'>
              {[
                'How do I get started?',
                'Show me a configuration example',
                'What are the main concepts?',
                'How does authentication work?',
              ].map(q => (
                <button
                  key={q}
                  onClick={() => handleSend(q)}
                  className='rounded-full border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-600 hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 transition-colors dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:border-indigo-700 dark:hover:bg-indigo-950 dark:hover:text-indigo-400'
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className='flex flex-col gap-4'>
          {messages.map(m => (
            <MessageBubble key={m.id} message={m} />
          ))}

          {streaming && (
            <StreamingBubble content={tokens} sources={sources} />
          )}

          {error && !streaming && (
            <div className='rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600 dark:bg-red-950 dark:text-red-400'>
              Error: {error}
            </div>
          )}
        </div>

        <div ref={bottomRef} />
      </div>

      <ChatInput onSend={handleSend} disabled={streaming} />
    </div>
  )
}
