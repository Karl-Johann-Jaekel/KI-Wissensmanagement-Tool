import type {
  ChatResponse,
  ChunkDetail,
  Message,
  Note,
  Notebook,
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

export const api = {
  checkKey: (key: string) => request<{ ok: boolean }>('/auth/check', {}, key),

  listNotebooks: () => request<Notebook[]>('/notebooks'),
  getNotebook: (id: string) => request<Notebook>(`/notebooks/${id}`),
  createNotebook: (title?: string) =>
    request<Notebook>('/notebooks', json('POST', title ? { title } : {})),
  renameNotebook: (id: string, title: string) =>
    request<Notebook>(`/notebooks/${id}`, json('PATCH', { title })),
  deleteNotebook: (id: string) => request<void>(`/notebooks/${id}`, { method: 'DELETE' }),

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

  listNotes: (notebookId: string) => request<Note[]>(`/notebooks/${notebookId}/notes`),
  createNote: (notebookId: string, title: string, content: string) =>
    request<Note>(`/notebooks/${notebookId}/notes`, json('POST', { title, content })),
  noteFromMessage: (notebookId: string, messageId: string) =>
    request<Note>(`/notebooks/${notebookId}/notes/from-message/${messageId}`, { method: 'POST' }),
  updateNote: (noteId: string, patch: { title?: string; content?: string }) =>
    request<Note>(`/notes/${noteId}`, json('PATCH', patch)),
  deleteNote: (noteId: string) => request<void>(`/notes/${noteId}`, { method: 'DELETE' }),
}
