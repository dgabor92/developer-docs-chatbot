import type { Message, SourceCitation } from '../types/session'

interface StreamingBubbleProps {
  content: string
  sources: SourceCitation[]
}

export function StreamingBubble({ content, sources }: StreamingBubbleProps) {
  return (
    <div className='flex flex-col gap-2'>
      <div className='flex justify-start'>
        <div className='max-w-[80%] rounded-2xl rounded-tl-sm bg-white px-4 py-3 shadow-sm ring-1 ring-gray-200'>
          <p className='whitespace-pre-wrap text-sm text-gray-800'>
            {content}
            <span className='ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-indigo-500' />
          </p>
        </div>
      </div>
      {sources.length > 0 && <SourcesList sources={sources} />}
    </div>
  )
}

interface BubbleProps {
  message: Message
}

export function MessageBubble({ message }: BubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className='flex flex-col gap-2'>
      <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
        <div
          className={`max-w-[80%] rounded-2xl px-4 py-3 ${
            isUser
              ? 'rounded-tr-sm bg-indigo-600 text-white'
              : 'rounded-tl-sm bg-white shadow-sm ring-1 ring-gray-200 text-gray-800'
          }`}
        >
          <p className='whitespace-pre-wrap text-sm'>{message.content}</p>
        </div>
      </div>
      {!isUser && message.sources && message.sources.length > 0 && (
        <SourcesList sources={message.sources} />
      )}
    </div>
  )
}

function SourcesList({ sources }: { sources: SourceCitation[] }) {
  return (
    <div className='ml-2 flex flex-wrap gap-2'>
      {sources.map((s, i) => (
        <a
          key={i}
          href={s.url}
          target='_blank'
          rel='noopener noreferrer'
          className='inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs text-gray-600 hover:bg-indigo-50 hover:text-indigo-700 hover:border-indigo-200 transition-colors'
        >
          <span className='max-w-[200px] truncate'>{s.title ?? s.url}</span>
          <span className='text-gray-400'>{(s.score * 100).toFixed(0)}%</span>
        </a>
      ))}
    </div>
  )
}
