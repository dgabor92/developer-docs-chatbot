import { useRef, type KeyboardEvent } from 'react'

interface Props {
  onSend: (content: string) => void
  disabled: boolean
}

export function ChatInput({ onSend, disabled }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null)

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function submit() {
    const value = ref.current?.value.trim()
    if (!value || disabled) return
    onSend(value)
    if (ref.current) ref.current.value = ''
  }

  return (
    <div className='flex items-end gap-3 border-t border-gray-200 bg-white px-4 py-3'>
      <textarea
        ref={ref}
        rows={1}
        placeholder='Ask a question... (Enter to send, Shift+Enter for newline)'
        disabled={disabled}
        onKeyDown={handleKeyDown}
        className='flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2.5 text-sm text-gray-900 placeholder-gray-400 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100 disabled:cursor-not-allowed disabled:bg-gray-50'
        style={{ maxHeight: '160px', overflowY: 'auto' }}
        onInput={e => {
          const el = e.currentTarget
          el.style.height = 'auto'
          el.style.height = `${Math.min(el.scrollHeight, 160)}px`
        }}
      />
      <button
        onClick={submit}
        disabled={disabled}
        className='flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50 transition-colors'
      >
        {disabled ? (
          <span className='h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent' />
        ) : (
          <svg className='h-4 w-4' fill='none' viewBox='0 0 24 24' stroke='currentColor' strokeWidth={2}>
            <path strokeLinecap='round' strokeLinejoin='round' d='M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5' />
          </svg>
        )}
      </button>
    </div>
  )
}
