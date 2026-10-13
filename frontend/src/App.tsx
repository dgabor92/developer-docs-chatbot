import { useCallback, useEffect, useState } from 'react'
import type { Session } from './types/session'
import { createSession, deleteSession, listSessions } from './api/sessions'
import { apiFetch } from './api/client'
import { SessionSidebar } from './components/SessionSidebar'
import { ChatWindow } from './components/ChatWindow'
import { SourcesPanel } from './components/SourcesPanel'

type View = 'chat' | 'sources'

function useDarkMode() {
  const [dark, setDark] = useState(() => {
    const stored = localStorage.getItem('theme')
    if (stored) return stored === 'dark'
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])

  return [dark, () => setDark(d => !d)] as const
}

export default function App() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [isCreatingSession, setIsCreatingSession] = useState(false)
  const [view, setView] = useState<View>('chat')
  const [dark, toggleDark] = useDarkMode()

  const loadSessions = useCallback(() => {
    listSessions()
      .then(data => {
        setSessions(data)
        setSessionsLoading(false)
      })
      .catch(err => {
        console.error('Failed to load sessions:', err)
        setSessionsLoading(false)
      })
  }, [])

  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  async function handleNewSession() {
    if (isCreatingSession) return
    setIsCreatingSession(true)
    try {
      const allSources = await apiFetch<{ id: string; status: string }[]>('/sources')
      const readyIds = allSources.filter(s => s.status === 'ready').map(s => s.id)
      const session = await createSession(readyIds)
      setSessions(prev => [session, ...prev])
      setSelectedId(session.id)
      setView('chat')
    } catch (err) {
      console.error('Failed to create session:', err)
    } finally {
      setIsCreatingSession(false)
    }
  }

  async function handleDeleteSession(id: string) {
    await deleteSession(id)
    setSessions(prev => prev.filter(s => s.id !== id))
    if (selectedId === id) setSelectedId(null)
  }

  function handleSelectSession(id: string) {
    setSelectedId(id)
    setView('chat')
  }

  function handleSessionCreatedFromSources(session: Session) {
    setSessions(prev => [session, ...prev])
    setSelectedId(session.id)
    setView('chat')
  }

  return (
    <div className='flex h-screen flex-col overflow-hidden bg-white font-sans dark:bg-gray-900'>
      {/* Unified top bar — single border-b keeps sidebar and main header on the same line */}
      <div className='flex flex-shrink-0 items-stretch border-b border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900'>
        <div className='flex w-64 flex-shrink-0 items-center justify-between border-r border-gray-200 px-4 py-3 dark:border-gray-700'>
          <span className='text-sm font-semibold text-gray-700 dark:text-gray-200'>Sessions</span>
          <button
            onClick={handleNewSession}
            className='rounded-md bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-700'
          >
            + New
          </button>
        </div>
        <div className='flex flex-1 items-center justify-between px-6 py-3'>
          <div>
            <h1 className='text-sm font-semibold text-gray-900 dark:text-gray-100'>Developer Docs Chatbot</h1>
            <p className='text-xs text-gray-400 dark:text-gray-500'>RAG-powered documentation assistant</p>
          </div>
          <div className='flex items-center gap-2'>
            <nav className='flex gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-800'>
              <button
                onClick={() => setView('chat')}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  view === 'chat'
                    ? 'bg-white text-gray-800 shadow-sm dark:bg-gray-700 dark:text-gray-100'
                    : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                }`}
              >
                Chat
              </button>
              <button
                onClick={() => setView('sources')}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  view === 'sources'
                    ? 'bg-white text-gray-800 shadow-sm dark:bg-gray-700 dark:text-gray-100'
                    : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
                }`}
              >
                Sources
              </button>
            </nav>
            <button
              onClick={toggleDark}
              title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
              className='flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-400 dark:hover:bg-gray-800'
            >
              {dark ? (
                <svg className='h-4 w-4' fill='none' viewBox='0 0 24 24' stroke='currentColor' strokeWidth={2}>
                  <path strokeLinecap='round' strokeLinejoin='round' d='M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M12 7a5 5 0 110 10A5 5 0 0112 7z' />
                </svg>
              ) : (
                <svg className='h-4 w-4' fill='none' viewBox='0 0 24 24' stroke='currentColor' strokeWidth={2}>
                  <path strokeLinecap='round' strokeLinejoin='round' d='M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z' />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Content area */}
      <div className='flex flex-1 overflow-hidden'>
        <SessionSidebar
          sessions={sessions}
          selectedId={selectedId}
          onSelect={handleSelectSession}
          onDelete={handleDeleteSession}
          loading={sessionsLoading}
        />

        <div className='flex flex-1 flex-col overflow-hidden'>
          {view === 'sources' && (
            <SourcesPanel onSessionCreated={handleSessionCreatedFromSources} />
          )}

          {view === 'chat' && selectedId && (
            <ChatWindow
              key={selectedId}
              sessionId={selectedId}
            />
          )}

          {view === 'chat' && !selectedId && (
            <div className='flex flex-1 flex-col items-center justify-center gap-8 px-8 text-center'>
              <div className='flex flex-col items-center gap-3'>
                <div className='flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-600 text-white shadow-lg'>
                  <svg className='h-7 w-7' fill='none' viewBox='0 0 24 24' stroke='currentColor' strokeWidth={1.5}>
                    <path strokeLinecap='round' strokeLinejoin='round' d='M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z' />
                  </svg>
                </div>
                <div>
                  <h2 className='text-lg font-semibold text-gray-800 dark:text-gray-100'>Developer Docs Chatbot</h2>
                  <p className='mt-1 text-sm text-gray-500 dark:text-gray-400'>RAG-powered documentation assistant</p>
                </div>
              </div>

              <div className='grid w-full max-w-md grid-cols-2 gap-3'>
                <div className='rounded-xl border border-gray-100 bg-gray-50 p-3 text-left dark:border-gray-700 dark:bg-gray-800'>
                  <div className='mb-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400'>Semantic RAG</div>
                  <p className='text-xs text-gray-500 dark:text-gray-400'>Answers grounded in your docs with no hallucinations</p>
                </div>
                <div className='rounded-xl border border-gray-100 bg-gray-50 p-3 text-left dark:border-gray-700 dark:bg-gray-800'>
                  <div className='mb-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400'>SSE Streaming</div>
                  <p className='text-xs text-gray-500 dark:text-gray-400'>Token-by-token responses via Server-Sent Events</p>
                </div>
                <div className='rounded-xl border border-gray-100 bg-gray-50 p-3 text-left dark:border-gray-700 dark:bg-gray-800'>
                  <div className='mb-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400'>Multi-turn history</div>
                  <p className='text-xs text-gray-500 dark:text-gray-400'>Persistent sessions with full conversation context</p>
                </div>
                <div className='rounded-xl border border-gray-100 bg-gray-50 p-3 text-left dark:border-gray-700 dark:bg-gray-800'>
                  <div className='mb-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400'>Source citations</div>
                  <p className='text-xs text-gray-500 dark:text-gray-400'>Every answer links back to the exact doc chunk</p>
                </div>
              </div>

              <button
                onClick={handleNewSession}
                className='rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-indigo-700'
              >
                Start new session
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
