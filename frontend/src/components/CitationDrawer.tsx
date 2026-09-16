import { useEffect, useRef } from 'react'
import { api } from '../api'
import { useLoader } from '../hooks'
import type { Citation } from '../types'
import { CloseIcon, FileIcon, Spinner } from './Icons'

export function CitationDrawer({ citation, onClose }: { citation: Citation; onClose: () => void }) {
  const chunk = useLoader(
    () => api.getChunk(citation.source_id, citation.chunk_id),
    `${citation.source_id}/${citation.chunk_id}`,
  )
  const highlightRef = useRef<HTMLElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    highlightRef.current?.scrollIntoView({ block: 'center' })
  }, [chunk.data])

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="citation-title"
        className="flex h-full w-full max-w-xl flex-col border-l border-line bg-surface shadow-2xl"
      >
        <div className="panel-header">
          <div className="flex min-w-0 items-center gap-2">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-fg">
              {citation.n}
            </span>
            <div className="min-w-0">
              <h2 id="citation-title" className="truncate text-sm font-medium">
                {citation.source_title}
              </h2>
              <p className="text-xs text-muted">
                {citation.page ? `Seite ${citation.page}` : 'Textquelle'}
                {chunk.data ? ` · Abschnitt ${chunk.data.ordinal + 1}` : ''}
              </p>
            </div>
          </div>
          <button ref={closeRef} className="btn-ghost p-1.5" onClick={onClose} aria-label="Schließen">
            <CloseIcon />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 text-sm leading-relaxed">
          {chunk.loading && (
            <div className="flex justify-center py-10 text-muted">
              <Spinner />
            </div>
          )}
          {chunk.error && <p className="text-danger">{chunk.error}</p>}
          {chunk.data && (
            <div className="space-y-4">
              {chunk.data.previous_content && (
                <p className="whitespace-pre-line text-muted">{chunk.data.previous_content}</p>
              )}
              <mark
                ref={highlightRef}
                className="block rounded-lg bg-highlight px-3 py-2 whitespace-pre-line text-fg"
              >
                {chunk.data.content}
              </mark>
              {chunk.data.next_content && (
                <p className="whitespace-pre-line text-muted">{chunk.data.next_content}</p>
              )}
            </div>
          )}
        </div>

        <p className="flex items-center gap-1.5 border-t border-line px-5 py-3 text-xs text-muted">
          <FileIcon size={14} /> Hervorgehoben: die Passage, auf die sich die Aussage stützt.
        </p>
      </aside>
    </div>
  )
}
