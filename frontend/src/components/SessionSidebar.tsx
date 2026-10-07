import type { Session } from '../types/session'

interface Props {
  sessions: Session[]
  selectedId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  loading: boolean
}

export function SessionSidebar({
  sessions,
  selectedId,
  onSelect,
  onNew,
  onDelete,
  loading,
}: Props) {
  return (
    <aside className='flex w-64 flex-shrink-0 flex-col border-r border-gray-200 bg-gray-50'>
      <div className='flex items-center justify-between border-b border-gray-200 px-4 py-3'>
        <span className='text-sm font-semibold text-gray-700'>Sessions</span>
        <button
          onClick={onNew}
          className='rounded-md bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-700'
        >
          + New
        </button>
      </div>

      <div className='flex-1 overflow-y-auto'>
        {loading && (
          <p className='px-4 py-3 text-xs text-gray-400'>Loading...</p>
        )}
        {!loading && sessions.length === 0 && (
          <p className='px-4 py-6 text-center text-xs text-gray-400'>
            No sessions yet
          </p>
        )}
        {sessions.map(s => (
          <div
            key={s.id}
            className={`group flex cursor-pointer items-center justify-between px-4 py-3 hover:bg-gray-100 ${
              s.id === selectedId ? 'bg-indigo-50 border-r-2 border-indigo-500' : ''
            }`}
            onClick={() => onSelect(s.id)}
          >
            <span
              className={`truncate text-sm ${
                s.id === selectedId ? 'font-medium text-indigo-700' : 'text-gray-700'
              }`}
            >
              {s.title ?? 'Untitled session'}
            </span>
            <button
              onClick={e => {
                e.stopPropagation()
                onDelete(s.id)
              }}
              className='ml-2 hidden rounded text-gray-400 hover:text-red-500 group-hover:block'
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
