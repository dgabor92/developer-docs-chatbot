import { useCallback, useRef, useState } from 'react'
import type { SourceCitation, SSEEvent } from '../types/session'
import { sendMessageStream } from '../api/sessions'

export interface StreamState {
  streaming: boolean
  tokens: string
  sources: SourceCitation[]
  error: string | null
}

const INITIAL_STATE: StreamState = {
  streaming: false,
  tokens: '',
  sources: [],
  error: null,
}

export function useSSE(sessionId: string) {
  const [state, setState] = useState<StreamState>(INITIAL_STATE)
  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(
    async (content: string, onDone?: (messageId: string) => void) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setState({ streaming: true, tokens: '', sources: [], error: null })

      try {
        const res = await sendMessageStream(sessionId, content)

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`)
        }

        const reader = res.body!.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          let currentEvent = ''
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7)
            } else if (line.startsWith('data: ')) {
              const parsed = JSON.parse(line.slice(6)) as SSEEvent['data']
              handleEvent(currentEvent, parsed, onDone)
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          setState(s => ({ ...s, error: (err as Error).message, streaming: false }))
        }
      }
    },
    [sessionId],
  )

  function handleEvent(event: string, data: SSEEvent['data'], onDone?: (id: string) => void) {
    if (event === 'token') {
      const { content } = data as { content: string }
      setState(s => ({ ...s, tokens: s.tokens + content }))
    } else if (event === 'sources') {
      const { sources } = data as { sources: SourceCitation[] }
      setState(s => ({ ...s, sources }))
    } else if (event === 'done') {
      const { message_id } = data as { message_id: string }
      setState(s => ({ ...s, streaming: false }))
      onDone?.(message_id)
    } else if (event === 'error') {
      const { message } = data as { message: string }
      setState(s => ({ ...s, error: message, streaming: false }))
    }
  }

  const reset = useCallback(() => setState(INITIAL_STATE), [])

  return { ...state, sendMessage, reset }
}
