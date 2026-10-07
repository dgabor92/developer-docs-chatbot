import { useCallback, useEffect, useState } from 'react'
import type { Session } from './types/session'
import { createSession, deleteSession, listSessions } from './api/sessions'
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
  const [view, setView] = useState<View>('chat')
  const [dark, toggleDark] = useDarkMode()

  const loadSessions = useCallback(() => {
    listSessions().then(data => {
      setSessions(data)
      setSessionsLoading(false)
    })
  }, [])

  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  async function handleNewSession() {
    const session = await createSession([])
    setSessions(prev => [session, ...prev])
    setSelectedId(session.id)
    setView('chat')
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
            <div className='flex flex-1 flex-col items-center justify-center gap-4 text-center'>
              <div>
                <p className='text-base font-medium text-gray-600 dark:text-gray-300'>No session selected</p>
                <p className='mt-1 text-sm text-gray-400 dark:text-gray-500'>
                  Create a new session or pick one from the sidebar
                </p>
              </div>
              <button
                onClick={handleNewSession}
                className='rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700'
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
