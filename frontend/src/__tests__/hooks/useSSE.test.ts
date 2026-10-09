import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useSSE } from '../../hooks/useSSE'

vi.mock('../../api/sessions', () => ({
  sendMessageStream: vi.fn(),
}))

import { sendMessageStream } from '../../api/sessions'
const mockSend = vi.mocked(sendMessageStream)

function makeSSEStream(events: Array<{ event: string; data: unknown }>) {
  const lines = events
    .flatMap(e => [`event: ${e.event}`, `data: ${JSON.stringify(e.data)}`, ''])
    .join('\n')
  const bytes = new TextEncoder().encode(lines)
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(bytes)
      controller.close()
    },
  })
  return new Response(stream, { status: 200 })
}

describe('useSSE', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('has correct initial state', () => {
    const { result } = renderHook(() => useSSE('session-1'))
    expect(result.current.streaming).toBe(false)
    expect(result.current.tokens).toBe('')
    expect(result.current.sources).toEqual([])
    expect(result.current.error).toBeNull()
  })

  it('reset() restores initial state', async () => {
    mockSend.mockResolvedValue(
      makeSSEStream([{ event: 'token', data: { content: 'Hi' } }]),
    )
    const { result } = renderHook(() => useSSE('session-1'))
    await act(async () => {
      await result.current.sendMessage('q')
    })
    act(() => result.current.reset())
    expect(result.current.tokens).toBe('')
    expect(result.current.streaming).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('accumulates tokens from SSE stream', async () => {
    mockSend.mockResolvedValue(
      makeSSEStream([
        { event: 'token', data: { content: 'Hello ' } },
        { event: 'token', data: { content: 'world' } },
        { event: 'done', data: { message_id: 'msg-1', session_id: 'session-1' } },
      ]),
    )
    const { result } = renderHook(() => useSSE('session-1'))
    await act(async () => {
      await result.current.sendMessage('q')
    })
    await waitFor(() => expect(result.current.streaming).toBe(false))
    expect(result.current.tokens).toBe('Hello world')
  })

  it('populates sources from SSE sources event', async () => {
    const sources = [{ url: 'https://docs.example.com', title: 'Docs', score: 0.9 }]
    mockSend.mockResolvedValue(
      makeSSEStream([
        { event: 'sources', data: { sources } },
        { event: 'done', data: { message_id: 'msg-1', session_id: 'session-1' } },
      ]),
    )
    const { result } = renderHook(() => useSSE('session-1'))
    await act(async () => {
      await result.current.sendMessage('q')
    })
    await waitFor(() => expect(result.current.streaming).toBe(false))
    expect(result.current.sources).toEqual(sources)
  })

  it('calls onDone callback with message_id', async () => {
    mockSend.mockResolvedValue(
      makeSSEStream([{ event: 'done', data: { message_id: 'msg-42', session_id: 's' } }]),
    )
    const onDone = vi.fn()
    const { result } = renderHook(() => useSSE('session-1'))
    await act(async () => {
      await result.current.sendMessage('q', onDone)
    })
    await waitFor(() => expect(result.current.streaming).toBe(false))
    expect(onDone).toHaveBeenCalledWith('msg-42')
  })

  it('sets error state when server returns error event', async () => {
    mockSend.mockResolvedValue(
      makeSSEStream([{ event: 'error', data: { message: 'Something went wrong' } }]),
    )
    const { result } = renderHook(() => useSSE('session-1'))
    await act(async () => {
      await result.current.sendMessage('q')
    })
    await waitFor(() => expect(result.current.streaming).toBe(false))
    expect(result.current.error).toBe('Something went wrong')
  })

  it('sets error when fetch returns non-ok response', async () => {
    mockSend.mockResolvedValue(new Response(null, { status: 500 }))
    const { result } = renderHook(() => useSSE('session-1'))
    await act(async () => {
      await result.current.sendMessage('q')
    })
    await waitFor(() => expect(result.current.error).not.toBeNull())
    expect(result.current.streaming).toBe(false)
  })
})
