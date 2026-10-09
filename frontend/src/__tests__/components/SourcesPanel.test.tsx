import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SourcesPanel } from '../../components/SourcesPanel'

vi.mock('../../api/client', () => ({
  apiFetch: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  },
}))

vi.mock('../../api/sessions', () => ({
  createSession: vi.fn(),
}))

import { apiFetch, ApiError } from '../../api/client'
import { createSession } from '../../api/sessions'
const mockFetch = vi.mocked(apiFetch)
const mockCreate = vi.mocked(createSession)

describe('SourcesPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading state initially', () => {
    mockFetch.mockReturnValue(new Promise(() => {}))
    render(<SourcesPanel onSessionCreated={vi.fn()} />)
    expect(screen.getByText('Loading sources...')).toBeInTheDocument()
  })

  it('shows empty state when no sources exist', async () => {
    mockFetch.mockResolvedValue([])
    render(<SourcesPanel onSessionCreated={vi.fn()} />)
    await waitFor(() =>
      expect(
        screen.getByText(/No sources yet/),
      ).toBeInTheDocument(),
    )
  })

  it('renders source rows with name and status', async () => {
    mockFetch.mockResolvedValue([
      {
        id: 'src-1',
        name: 'FastAPI Docs',
        base_url: 'https://fastapi.tiangolo.com/',
        status: 'ready',
        chunk_count: 120,
        error_msg: null,
      },
    ])
    render(<SourcesPanel onSessionCreated={vi.fn()} />)
    await waitFor(() => expect(screen.getByText('FastAPI Docs')).toBeInTheDocument())
    expect(screen.getByText('ready')).toBeInTheDocument()
    expect(screen.getByText('120 chunks')).toBeInTheDocument()
  })

  it('submits add form with name and URL', async () => {
    mockFetch.mockResolvedValueOnce([]).mockResolvedValue([])
    render(<SourcesPanel onSessionCreated={vi.fn()} />)
    await waitFor(() => screen.getByPlaceholderText(/Name/))

    await userEvent.type(screen.getByPlaceholderText(/Name/), 'My Docs')
    await userEvent.type(
      screen.getByPlaceholderText(/https:\/\//),
      'https://docs.example.com/',
    )
    await userEvent.click(screen.getByRole('button', { name: /Add/i }))

    expect(mockFetch).toHaveBeenCalledWith(
      '/sources',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('shows 409 error when duplicate URL submitted', async () => {
    mockFetch
      .mockResolvedValueOnce([])
      .mockRejectedValue(new ApiError(409, 'conflict'))
    render(<SourcesPanel onSessionCreated={vi.fn()} />)
    await waitFor(() => screen.getByPlaceholderText(/Name/))

    await userEvent.type(screen.getByPlaceholderText(/Name/), 'Duplicate')
    await userEvent.type(
      screen.getByPlaceholderText(/https:\/\//),
      'https://docs.example.com/',
    )
    await userEvent.click(screen.getByRole('button', { name: /Add/i }))

    await waitFor(() =>
      expect(screen.getByText('This URL is already added.')).toBeInTheDocument(),
    )
  })

  it('calls onSessionCreated when Chat button clicked', async () => {
    mockFetch.mockResolvedValue([
      {
        id: 'src-1',
        name: 'FastAPI',
        base_url: 'https://fastapi.tiangolo.com/',
        status: 'ready',
        chunk_count: 50,
        error_msg: null,
      },
    ])
    const session = { id: 'sess-1', title: null, source_ids: ['src-1'], created_at: '', updated_at: '' }
    mockCreate.mockResolvedValue(session)
    const onCreated = vi.fn()
    render(<SourcesPanel onSessionCreated={onCreated} />)
    await waitFor(() => screen.getByRole('button', { name: 'Chat' }))

    await userEvent.click(screen.getByRole('button', { name: 'Chat' }))
    expect(mockCreate).toHaveBeenCalledWith(['src-1'])
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(session))
  })
})
