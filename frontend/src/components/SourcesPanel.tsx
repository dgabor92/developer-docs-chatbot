import { useEffect, useState } from 'react'
import type { Session } from '../types/session'
import { ApiError } from '../api/client'
import { createSession } from '../api/sessions'
import { apiFetch } from '../api/client'

interface SourceRow {
  id: string
  name: string
  base_url: string
  status: string
  chunk_count: number
  error_msg: string | null
}

const STATUS_COLOR: Record<string, string> = {
  ready: 'bg-green-100 text-green-700',
  indexing: 'bg-yellow-100 text-yellow-700',
  error: 'bg-red-100 text-red-700',
  pending: 'bg-gray-100 text-gray-600',
}

interface Props {
  onSessionCreated: (session: Session) => void
}

export function SourcesPanel({ onSessionCreated }: Props) {
  const [sources, setSources] = useState<SourceRow[]>([])
  const [loading, setLoading] = useState(true)
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  function loadSources() {
    apiFetch<SourceRow[]>('/sources').then(setSources).finally(() => setLoading(false))
  }

  useEffect(() => {
    loadSources()
  }, [])

  useEffect(() => {
    const hasIndexing = sources.some(s => s.status === 'indexing')
    if (!hasIndexing) return
    const interval = setInterval(loadSources, 3000)
    return () => clearInterval(interval)
  }, [sources])

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    setSubmitting(true)
    try {
      await apiFetch('/sources', {
        method: 'POST',
        body: JSON.stringify({ name, base_url: url }),
      })
      setName('')
      setUrl('')
      loadSources()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setFormError('This URL is already added.')
      } else if (err instanceof ApiError && err.status === 422) {
        setFormError('Invalid URL. Use http:// or https://')
      } else {
        setFormError('Failed to add source.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDelete(id: string) {
    await apiFetch(`/sources/${id}`, { method: 'DELETE' })
    setSources(prev => prev.filter(s => s.id !== id))
  }

  async function handleReindex(id: string) {
    await apiFetch(`/sources/${id}/reindex`, { method: 'POST' })
    loadSources()
  }

  async function handleStartChat(sourceId: string) {
    const session = await createSession([sourceId])
    onSessionCreated(session)
  }

  return (
    <div className='flex flex-1 flex-col overflow-y-auto bg-white px-6 py-6 dark:bg-gray-900'>
      <h2 className='mb-4 text-base font-semibold text-gray-800 dark:text-gray-100'>Documentation Sources</h2>

      <form onSubmit={handleAdd} className='mb-6 flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800'>
        <h3 className='text-sm font-medium text-gray-700 dark:text-gray-300'>Add new source</h3>
        <div className='flex gap-3'>
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder='Name (e.g. FastAPI Docs)'
            required
            className='flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400 dark:focus:border-indigo-500'
          />
          <input
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder='https://docs.example.com/'
            required
            type='url'
            className='flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400 dark:focus:border-indigo-500'
          />
          <button
            type='submit'
            disabled={submitting}
            className='rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50'
          >
            {submitting ? 'Adding...' : 'Add'}
          </button>
        </div>
        {formError && <p className='text-xs text-red-600'>{formError}</p>}
      </form>

      {loading && <p className='text-sm text-gray-400 dark:text-gray-500'>Loading sources...</p>}

      {!loading && sources.length === 0 && (
        <p className='text-center text-sm text-gray-400 dark:text-gray-500'>No sources yet. Add a documentation URL above.</p>
      )}

      <div className='flex flex-col gap-3'>
        {sources.map(s => (
          <div key={s.id} className='flex items-center justify-between rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800'>
            <div className='min-w-0 flex-1'>
              <div className='flex items-center gap-2'>
                <span className='truncate font-medium text-sm text-gray-800 dark:text-gray-100'>{s.name}</span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLOR[s.status] ?? 'bg-gray-100 text-gray-600'}`}>
                  {s.status}
                </span>
                {s.status === 'ready' && (
                  <span className='text-xs text-gray-400 dark:text-gray-500'>{s.chunk_count.toLocaleString()} chunks</span>
                )}
              </div>
              <a
                href={s.base_url}
                target='_blank'
                rel='noopener noreferrer'
                className='mt-0.5 block truncate text-xs text-indigo-600 hover:underline'
              >
                {s.base_url}
              </a>
              {s.error_msg && (
                <p className='mt-1 text-xs text-red-500 truncate'>{s.error_msg}</p>
              )}
            </div>
            <div className='ml-4 flex items-center gap-2'>
              {s.status === 'ready' && (
                <button
                  onClick={() => handleStartChat(s.id)}
                  className='rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700'
                >
                  Chat
                </button>
              )}
              {s.status !== 'indexing' && (
                <button
                  onClick={() => handleReindex(s.id)}
                  className='rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-400 dark:hover:bg-gray-700'
                >
                  Reindex
                </button>
              )}
              {s.status === 'indexing' && (
                <span className='text-xs text-yellow-600 animate-pulse'>Indexing...</span>
              )}
              <button
                onClick={() => handleDelete(s.id)}
                className='rounded-lg border border-red-100 px-3 py-1.5 text-xs text-red-500 hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950'
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
