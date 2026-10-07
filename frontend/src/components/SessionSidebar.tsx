import type { Session } from '../types/session'

interface Props {
  sessions: Session[]
  selectedId: string | null
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  loading: boolean
}

export function SessionSidebar({
  sessions,
  selectedId,
  onSelect,
  onDelete,
  loading,
}: Props) {
  return (
    <aside className='flex w-64 flex-shrink-0 flex-col border-r border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900'>
      <div className='flex-1 overflow-y-auto'>
        {loading && (
          <p className='px-4 py-3 text-xs text-gray-400 dark:text-gray-500'>Loading...</p>
        )}
        {!loading && sessions.length === 0 && (
          <p className='px-4 py-6 text-center text-xs text-gray-400 dark:text-gray-500'>
            No sessions yet
          </p>
        )}
        {sessions.map(s => (
          <div
            key={s.id}
            className={`group flex cursor-pointer items-center justify-between px-4 py-3 hover:bg-gray-100 dark:hover:bg-gray-800 ${
              s.id === selectedId ? 'border-r-2 border-indigo-500 bg-indigo-50 dark:bg-indigo-950' : ''
            }`}
            onClick={() => onSelect(s.id)}
          >
            <span
              className={`truncate text-sm ${
                s.id === selectedId ? 'font-medium text-indigo-700 dark:text-indigo-400' : 'text-gray-700 dark:text-gray-300'
              }`}
            >
              {s.title ?? 'Untitled session'}
            </span>
            <button
              onClick={e => {
                e.stopPropagation()
                onDelete(s.id)
              }}
              className='ml-2 hidden rounded text-gray-400 hover:text-red-500 group-hover:block dark:text-gray-500 dark:hover:text-red-400'
              title='Delete session'
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </aside>
  )
}
