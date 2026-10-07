import { apiFetch } from './client'
import type { Session, SessionWithMessages } from '../types/session'

export function createSession(sourceIds: string[] = []): Promise<Session> {
  return apiFetch('/sessions', {
    method: 'POST',
    body: JSON.stringify({ source_ids: sourceIds }),
  })
}

export function listSessions(): Promise<Session[]> {
  return apiFetch('/sessions')
}

export function getSession(id: string): Promise<SessionWithMessages> {
  return apiFetch(`/sessions/${id}`)
}

export function deleteSession(id: string): Promise<void> {
  return apiFetch(`/sessions/${id}`, { method: 'DELETE' })
}

export function sendMessageStream(sessionId: string, content: string): Promise<Response> {
  return fetch(`/api/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
}
