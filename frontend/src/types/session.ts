export interface SourceCitation {
  url: string
  title: string | null
  score: number
}

export interface Message {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
  sources: SourceCitation[] | null
  created_at: string
}

export interface Session {
  id: string
  title: string | null
  source_ids: string[]
  created_at: string
  updated_at: string
}

export interface SessionWithMessages extends Session {
  messages: Message[]
}

export type SSEEvent =
  | { event: 'token'; data: { content: string } }
  | { event: 'sources'; data: { sources: SourceCitation[] } }
  | { event: 'done'; data: { message_id: string; session_id: string } }
  | { event: 'error'; data: { message: string } }
