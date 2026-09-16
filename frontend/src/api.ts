import type {
  ChatResponse,
  ChunkDetail,
  Message,
  Note,
  Notebook,
  ReportKind,
  Source,
} from './types'

const KEY_STORAGE = 'notebook.accessKey'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export function getAccessKey(): string | null {
  try {
    return localStorage.getItem(KEY_STORAGE)
  } catch {
    return null
  }
}

export function setAccessKey(key: string | null): void {
  try {
    if (key) localStorage.setItem(KEY_STORAGE, key)
    else localStorage.removeItem(KEY_STORAGE)
  } catch {
    // storage unavailable (private mode): key lives only for this page load
  }
}

let unauthorizedHandler: () => void = () => {}

export function onUnauthorized(handler: () => void): void {
  unauthorizedHandler = handler
}

async function request<T>(path: string, init: RequestInit = {}, key = getAccessKey()): Promise<T> {
  const headers = new Headers(init.headers)
  if (key) headers.set('X-Access-Key', key)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')

  let response: Response
  try {
    response = await fetch(`/api${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, 'Server nicht erreichbar. Bitte Verbindung prüfen.')
  }

  if (response.status === 401) {
    unauthorizedHandler()
    throw new ApiError(401, 'Zugangsschlüssel ungültig.')
  }
  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response))
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail
      if (typeof detail === 'string') return detail
      if (Array.isArray(detail)) return 'Ungültige Eingabe.'
    }
  } catch {
    // non-JSON error body
  }
  return `Anfrage fehlgeschlagen (HTTP ${response.status}).`
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  body: body === undefined ? undefined : JSON.stringify(body),
})

export interface ChatStreamHandlers {
  /** The server accepted the request; from here on a failure is not a transport problem. */
  onOpen?: () => void
  /** Retrieval is done; generation starts now. */
  onPassages?: (info: { count: number; sources: number }) => void
  /** Raw model output as it arrives. Citation markers are validated only at the end. */
  onDelta: (text: string) => void
}

type StreamEvent =
  | { type: 'passages'; count: number; sources: number }
  | { type: 'delta'; text: string }
  | { type: 'error'; detail: string }
  | ({ type: 'done' } & ChatResponse)

/**
 * Server-sent events for one answer. Resolves with the same payload the non-streaming
 * endpoint returns, so the caller can replace the streamed text with the validated one.
 */
async function chatStream(
  notebookId: string,
  question: string,
  sourceIds: string[],
  handlers: ChatStreamHandlers,
): Promise<ChatResponse> {
  const headers = new Headers({ 'Content-Type': 'application/json' })
  const key = getAccessKey()
  if (key) headers.set('X-Access-Key', key)

  let response: Response
  try {
    response = await fetch(`/api/notebooks/${notebookId}/chat/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ question, source_ids: sourceIds }),
    })
  } catch {
    throw new ApiError(0, 'Server nicht erreichbar. Bitte Verbindung prüfen.')
  }
  if (response.status === 401) {
    unauthorizedHandler()
    throw new ApiError(401, 'Zugangsschlüssel ungültig.')
  }
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response))
  if (!response.body) throw new ApiError(0, 'Der Browser unterstützt keine Antwort-Streams.')
  handlers.onOpen?.()

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result: ChatResponse | null = null

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      // Events are separated by a blank line; a chunk can hold several or half of one.
      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const event = parseEvent(frame)
        if (event?.type === 'passages') handlers.onPassages?.(event)
        else if (event?.type === 'delta') handlers.onDelta(event.text)
        else if (event?.type === 'error') throw new ApiError(503, event.detail)
        else if (event?.type === 'done') result = { question: event.question, answer: event.answer }
        boundary = buffer.indexOf('\n\n')
      }
    }
  } finally {
    await reader.cancel().catch(() => {})
  }

  if (!result) throw new ApiError(0, 'Die Antwort wurde unterwegs abgeschnitten.')
  return result
}

function parseEvent(frame: string): StreamEvent | null {
  const line = frame.split('\n').find((l) => l.startsWith('data: '))
  if (!line) return null
  try {
    return JSON.parse(line.slice('data: '.length)) as StreamEvent
  } catch {
    return null
  }
}

export const api = {
  checkKey: (key: string) => request<{ ok: boolean }>('/auth/check', {}, key),

  listNotebooks: () => request<Notebook[]>('/notebooks'),
  getNotebook: (id: string) => request<Notebook>(`/notebooks/${id}`),
  createNotebook: (title?: string) =>
    request<Notebook>('/notebooks', json('POST', title ? { title } : {})),
  renameNotebook: (id: string, title: string) =>
    request<Notebook>(`/notebooks/${id}`, json('PATCH', { title })),
  deleteNotebook: (id: string) => request<void>(`/notebooks/${id}`, { method: 'DELETE' }),
  regenerateOverview: (id: string) =>
    request<Notebook>(`/notebooks/${id}/overview`, { method: 'POST' }),

  listSources: (notebookId: string) => request<Source[]>(`/notebooks/${notebookId}/sources`),
  uploadSource: (notebookId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Source>(`/notebooks/${notebookId}/sources`, { method: 'POST', body: form })
  },
  importUrl: (notebookId: string, url: string) =>
    request<Source>(`/notebooks/${notebookId}/sources/url`, json('POST', { url })),
  regenerateGuide: (sourceId: string) =>
    request<Source>(`/sources/${sourceId}/guide`, { method: 'POST' }),
  renameSource: (sourceId: string, title: string) =>
    request<Source>(`/sources/${sourceId}`, json('PATCH', { title })),
  deleteSource: (sourceId: string) => request<void>(`/sources/${sourceId}`, { method: 'DELETE' }),
  getChunk: (sourceId: string, chunkId: string) =>
    request<ChunkDetail>(`/sources/${sourceId}/chunks/${chunkId}`),

  listMessages: (notebookId: string) => request<Message[]>(`/notebooks/${notebookId}/messages`),
  clearMessages: (notebookId: string) =>
    request<void>(`/notebooks/${notebookId}/messages`, { method: 'DELETE' }),
  chat: (notebookId: string, question: string, sourceIds: string[]) =>
    request<ChatResponse>(
      `/notebooks/${notebookId}/chat`,
      json('POST', { question, source_ids: sourceIds }),
    ),
  chatStream,

  listNotes: (notebookId: string) => request<Note[]>(`/notebooks/${notebookId}/notes`),
  createNote: (notebookId: string, title: string, content: string) =>
    request<Note>(`/notebooks/${notebookId}/notes`, json('POST', { title, content })),
  noteFromMessage: (notebookId: string, messageId: string) =>
    request<Note>(`/notebooks/${notebookId}/notes/from-message/${messageId}`, { method: 'POST' }),
  createReport: (notebookId: string, kind: ReportKind, sourceIds: string[]) =>
    request<Note>(
      `/notebooks/${notebookId}/reports`,
      json('POST', { kind, source_ids: sourceIds }),
    ),
  updateNote: (noteId: string, patch: { title?: string; content?: string }) =>
    request<Note>(`/notes/${noteId}`, json('PATCH', patch)),
  deleteNote: (noteId: string) => request<void>(`/notes/${noteId}`, { method: 'DELETE' }),
}
