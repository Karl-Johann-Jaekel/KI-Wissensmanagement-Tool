export interface Notebook {
  id: string
  title: string
  created_at: string
  source_count: number
}

export type SourceStatus = 'processing' | 'ready' | 'error'
export type GuideStatus = 'pending' | 'ready' | 'error'

export interface Source {
  id: string
  notebook_id: string
  title: string
  type: 'pdf' | 'text' | 'url'
  origin: string | null
  status: SourceStatus
  error: string | null
  guide_status: GuideStatus
  guide_error: string | null
  summary: string | null
  key_topics: string[]
  suggested_questions: string[]
  page_count: number | null
  chunk_count: number
  created_at: string
}

export interface Citation {
  n: number
  chunk_id: string
  source_id: string
  source_title: string
  page: number | null
  snippet: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
  created_at: string
}

export interface ChatResponse {
  question: Message
  answer: Message
}

export interface ChunkDetail {
  id: string
  source_id: string
  source_title: string
  ordinal: number
  page: number | null
  content: string
  previous_content: string | null
  next_content: string | null
}

export interface Note {
  id: string
  notebook_id: string
  title: string
  content: string
  /** Copied from the answer a note was saved from; empty for hand-written notes. */
  citations: Citation[]
  created_at: string
  updated_at: string
}
