import { useCallback, useEffect, useState } from 'react'
import type { Session } from './types/session'
import { createSession, deleteSession, listSessions } from './api/sessions'
import { SessionSidebar } from './components/SessionSidebar'
import { ChatWindow } from './components/ChatWindow'
import { SourcesPanel } from './components/SourcesPanel'

type View = 'chat' | 'sources'

export default function App() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [view, setView] = useState<View>('chat')

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
    <div className='flex h-screen overflow-hidden bg-white font-sans'>
      <SessionSidebar
        sessions={sessions}
        selectedId={selectedId}
        onSelect={handleSelectSession}
        onNew={handleNewSession}
        onDelete={handleDeleteSession}
        loading={sessionsLoading}
      />

      <div className='flex flex-1 flex-col overflow-hidden'>
        <header className='flex items-center justify-between border-b border-gray-200 bg-white px-6 py-3'>
          <div>
            <h1 className='text-sm font-semibold text-gray-900'>Developer Docs Chatbot</h1>
            <p className='text-xs text-gray-400'>RAG-powered documentation assistant</p>
          </div>
          <nav className='flex gap-1 rounded-lg bg-gray-100 p-1'>
            <button
              onClick={() => setView('chat')}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                view === 'chat'
                  ? 'bg-white text-gray-800 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Chat
            </button>
            <button
              onClick={() => setView('sources')}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                view === 'sources'
                  ? 'bg-white text-gray-800 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              Sources
            </button>
          </nav>
        </header>

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
              <p className='text-base font-medium text-gray-600'>No session selected</p>
              <p className='mt-1 text-sm text-gray-400'>
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
  )
}
