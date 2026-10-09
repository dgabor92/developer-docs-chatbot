import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ChatInput } from '../../components/ChatInput'

describe('ChatInput', () => {
  it('renders textarea and send button', () => {
    render(<ChatInput onSend={vi.fn()} disabled={false} />)
    expect(screen.getByRole('textbox')).toBeInTheDocument()
    expect(screen.getByRole('button')).toBeInTheDocument()
  })

  it('calls onSend with trimmed text on Enter', async () => {
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} disabled={false} />)
    const textarea = screen.getByRole('textbox')
    await userEvent.type(textarea, 'hello world{Enter}')
    expect(onSend).toHaveBeenCalledWith('hello world')
  })

  it('does not submit on Shift+Enter', async () => {
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} disabled={false} />)
    const textarea = screen.getByRole('textbox')
    await userEvent.type(textarea, 'hello{shift>}{Enter}{/shift}')
    expect(onSend).not.toHaveBeenCalled()
  })

  it('does not submit empty or whitespace-only text', async () => {
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} disabled={false} />)
    const textarea = screen.getByRole('textbox')
    await userEvent.type(textarea, '   {Enter}')
    expect(onSend).not.toHaveBeenCalled()
  })

  it('disables textarea and button when disabled=true', () => {
    render(<ChatInput onSend={vi.fn()} disabled={true} />)
    expect(screen.getByRole('textbox')).toBeDisabled()
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('clears input after successful submit', async () => {
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} disabled={false} />)
    const textarea = screen.getByRole('textbox')
    await userEvent.type(textarea, 'my question{Enter}')
    expect(textarea).toHaveValue('')
  })

  it('does not call onSend when disabled and Enter pressed', async () => {
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} disabled={true} />)
    const textarea = screen.getByRole('textbox')
    await userEvent.type(textarea, 'hello{Enter}')
    expect(onSend).not.toHaveBeenCalled()
  })
})
