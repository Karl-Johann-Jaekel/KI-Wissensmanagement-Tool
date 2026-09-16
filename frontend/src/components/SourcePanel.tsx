import { useState } from 'react'
import type { Source } from '../types'
import { AddSourceDialog } from './AddSourceDialog'
import { ChevronIcon, FileIcon, LinkIcon, PlusIcon, Spinner } from './Icons'

interface Props {
  notebookId: string
  sources: Source[] | undefined
  loadError: string | null
  deselected: Set<string>
  openSourceId: string | null
  onToggle: (sourceId: string) => void
  onToggleAll: (select: boolean) => void
  onOpen: (sourceId: string) => void
  onSourceChanged: (source: Source) => void
  className?: string
}

/**
 * The list of sources: what exists, what state it is in, what feeds the answers. Opening a
 * source shows its guide in the main column — a summary does not fit into this width.
 */
export function SourcePanel({
  notebookId,
  sources,
  loadError,
  deselected,
  openSourceId,
  onToggle,
  onToggleAll,
  onOpen,
  onSourceChanged,
  className = '',
}: Props) {
  const [dialogOpen, setDialogOpen] = useState(false)

  const ready = sources?.filter((s) => s.status === 'ready') ?? []
  const allSelected = ready.length > 0 && ready.every((s) => !deselected.has(s.id))

  return (
    <section className={`panel ${className}`} aria-label="Quellen">
      <div className="panel-header">
        <h2 className="font-medium">Quellen</h2>
        <button className="btn-ghost" onClick={() => setDialogOpen(true)}>
          <PlusIcon /> Hinzufügen
        </button>
      </div>

      {ready.length > 1 && (
        <label className="flex cursor-pointer items-center justify-between gap-2 border-b border-line px-4 py-2 text-xs text-muted">
          Alle Quellen auswählen
          <input
            type="checkbox"
            className="size-4 accent-(--accent)"
            checked={allSelected}
            onChange={(e) => onToggleAll(e.target.checked)}
          />
        </label>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {loadError && <p className="px-2 pb-2 text-sm text-danger">{loadError}</p>}
        {sources === undefined && !loadError ? (
          <div className="flex justify-center py-8 text-muted">
            <Spinner />
          </div>
        ) : sources?.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
            <FileIcon size={28} className="text-muted" />
            <p className="text-sm font-medium">Noch keine Quellen</p>
            <p className="text-xs text-muted">PDFs, Texte oder Webseiten hinzufügen – danach kannst du Fragen stellen.</p>
            <button className="btn-primary mt-2" onClick={() => setDialogOpen(true)}>
              <PlusIcon /> Quelle hinzufügen
            </button>
          </div>
        ) : (
          <ul className="space-y-1">
            {sources?.map((source) => (
              <SourceItem
                key={source.id}
                source={source}
                selected={!deselected.has(source.id)}
                open={openSourceId === source.id}
                onOpen={() => onOpen(source.id)}
                onToggle={() => onToggle(source.id)}
              />
            ))}
          </ul>
        )}
      </div>

      {dialogOpen && (
        <AddSourceDialog
          notebookId={notebookId}
          onAdded={onSourceChanged}
          onClose={() => setDialogOpen(false)}
        />
      )}
    </section>
  )
}

interface ItemProps {
  source: Source
  selected: boolean
  open: boolean
  onOpen: () => void
  onToggle: () => void
}

function SourceItem({ source, selected, open, onOpen, onToggle }: ItemProps) {
  const TypeIcon = source.type === 'url' ? LinkIcon : FileIcon
  const meta = [
    source.type.toUpperCase(),
    source.page_count ? `${source.page_count} S.` : null,
    source.chunk_count ? `${source.chunk_count} Abschnitte` : null,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <li className={`rounded-xl ${open ? 'bg-accent-soft' : 'hover:bg-surface-muted'}`}>
      <div className="flex items-center gap-2 px-2 py-2">
        <button
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
          onClick={onOpen}
          aria-label={`${source.title} öffnen`}
        >
          <TypeIcon className="shrink-0 text-muted" />
          <span className="min-w-0">
            <span className="block truncate text-sm" title={source.origin ?? source.title}>
              {source.title}
            </span>
            <span className={`block truncate text-xs ${source.status === 'error' ? 'text-danger' : 'text-muted'}`}>
              {source.status === 'processing'
                ? 'Wird verarbeitet …'
                : source.status === 'error'
                  ? 'Fehler'
                  : meta}
            </span>
          </span>
          <ChevronIcon size={14} className="ml-auto shrink-0 text-muted" />
        </button>
        {source.status === 'processing' && (
          <span className="text-accent">
            <Spinner />
          </span>
        )}
        {source.status === 'ready' && (
          <input
            type="checkbox"
            className="size-4 shrink-0 accent-(--accent)"
            checked={selected}
            onChange={onToggle}
            aria-label={`${source.title} für Antworten verwenden`}
          />
        )}
      </div>

      {/* Guides are long and live in the main column; an import error is two lines and
          belongs where the failed source is. */}
      {source.status === 'error' && source.error && (
        <p className="px-4 pb-3 text-xs text-danger">{source.error}</p>
      )}
    </li>
  )
}
