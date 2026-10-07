import { useEffect, useState } from 'react'

interface HealthStatus {
  status: string
  database: string
  ollama: string
}

function StatusBadge({ status }: { status: string }) {
  const isOk = status === 'ok'
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
        isOk ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
      }`}
    >
      {status}
    </span>
  )
}

function StatusRow({ label, status }: { label: string; status: string }) {
  return (
    <div className='flex items-center justify-between py-2'>
      <span className='text-sm text-gray-600'>{label}</span>
      <StatusBadge status={status} />
    </div>
  )
}

export default function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    fetch('/api/health')
      .then(res => {
        if (!res.ok) throw new Error('API returned non-OK status')
        return res.json() as Promise<HealthStatus>
      })
      .then(data => setHealth(data))
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className='min-h-screen bg-gray-50'>
      <div className='mx-auto max-w-2xl px-4 py-16'>
        <div className='mb-8'>
          <h1 className='text-3xl font-bold tracking-tight text-gray-900'>
            Developer Docs Chatbot
          </h1>
          <p className='mt-2 text-gray-500'>RAG-powered documentation assistant</p>
        </div>

        <div className='rounded-lg border border-gray-200 bg-white p-6 shadow-sm'>
          <h2 className='text-sm font-semibold uppercase tracking-wide text-gray-500'>
            System Status
          </h2>

          {loading && (
            <p className='mt-4 text-sm text-gray-400'>Checking services...</p>
          )}

          {error && (
            <p className='mt-4 text-sm text-red-600'>
              Could not reach the API. Is the backend running?
            </p>
          )}

          {health && (
            <div className='mt-3 divide-y divide-gray-100'>
              <StatusRow label='API' status={health.status} />
              <StatusRow label='Database' status={health.database} />
              <StatusRow label='Ollama' status={health.ollama} />
            </div>
          )}
        </div>

        <p className='mt-6 text-center text-xs text-gray-400'>Phase 1 — Infrastructure</p>
      </div>
    </div>
  )
}
