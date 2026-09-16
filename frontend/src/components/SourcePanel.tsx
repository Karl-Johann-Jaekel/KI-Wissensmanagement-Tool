import { useState } from 'react'
import { api } from '../api'
import { errorText } from '../hooks'
import type { Source } from '../types'
import { AddSourceDialog } from './AddSourceDialog'
import {
  ChevronIcon,
  EditIcon,
  FileIcon,
  LinkIcon,
  PlusIcon,
  RefreshIcon,
  SparkIcon,
  Spinner,
  TrashIcon,
} from './Icons'

interface Props {
  notebookId: string
  sources: Source[] | undefined
  loadError: string | null
  deselected: Set<string>
  onToggle: (sourceId: string) => void
  onToggleAll: (select: boolean) => void
  onSourceChanged: (source: Source) => void
  onSourceRemoved: (sourceId: string) => void
  onAsk: (question: string) => void
  className?: string
}

export function SourcePanel({
  notebookId,
  sources,
  loadError,
  deselected,
  onToggle,
  onToggleAll,
  onSourceChanged,
  onSourceRemoved,
  onAsk,
  className = '',
}: Props) {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const ready = sources?.filter((s) => s.status === 'ready') ?? []
  const allSelected = ready.length > 0 && ready.every((s) => !deselected.has(s.id))

  async function remove(source: Source) {
    if (!window.confirm(`Quelle „${source.title}“ entfernen?`)) return
    try {
      await api.deleteSource(source.id)
      onSourceRemoved(source.id)
    } catch (err) {
      setActionError(errorText(err))
    }
  }

  async function rename(source: Source) {
    const title = window.prompt('Neuer Titel der Quelle', source.title)?.trim()
    if (!title || title === source.title) return
    try {
      onSourceChanged(await api.renameSource(source.id, title))
    } catch (err) {
      setActionError(errorText(err))
    }
  }

  async function retryGuide(source: Source) {
    try {
      onSourceChanged(await api.regenerateGuide(source.id))
    } catch (err) {
      setActionError(errorText(err))
    }
  }

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
        {actionError && <p className="px-2 pb-2 text-sm text-danger">{actionError}</p>}
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
                expanded={expanded === source.id}
                onExpand={() => setExpanded(expanded === source.id ? null : source.id)}
                onToggle={() => onToggle(source.id)}
                onRemove={() => void remove(source)}
                onRename={() => void rename(source)}
                onRetryGuide={() => void retryGuide(source)}
                onAsk={onAsk}
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
  expanded: boolean
  onExpand: () => void
  onToggle: () => void
  onRemove: () => void
  onRename: () => void
  onRetryGuide: () => void
  onAsk: (question: string) => void
}

function SourceItem({
  source,
  selected,
  expanded,
  onExpand,
  onToggle,
  onRemove,
  onRename,
  onRetryGuide,
  onAsk,
}: ItemProps) {
  const TypeIcon = source.type === 'url' ? LinkIcon : FileIcon
  const meta = [
    source.type.toUpperCase(),
    source.page_count ? `${source.page_count} S.` : null,
    source.chunk_count ? `${source.chunk_count} Abschnitte` : null,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <li className={`rounded-xl ${expanded ? 'bg-surface-muted' : 'hover:bg-surface-muted'}`}>
      <div className="flex items-center gap-2 px-2 py-2">
        <button
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
          onClick={onExpand}
          aria-expanded={expanded}
          disabled={source.status !== 'ready'}
        >
          <ChevronIcon
            size={14}
            className={`shrink-0 text-muted transition-transform ${expanded ? 'rotate-90' : ''} ${source.status !== 'ready' ? 'invisible' : ''}`}
          />
          <TypeIcon className="shrink-0 text-muted" />
          <span className="min-w-0">
            <span className="block truncate text-sm" title={source.origin ?? source.title}>
              {source.title}
            </span>
            <span className="block truncate text-xs text-muted">
              {source.status === 'processing' ? 'Wird verarbeitet …' : source.status === 'error' ? 'Fehler' : meta}
            </span>
          </span>
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
        {source.status === 'error' && (
          <button className="btn-danger p-1" onClick={onRemove} aria-label="Quelle entfernen">
            <TrashIcon size={14} />
          </button>
        )}
      </div>

      {source.status === 'error' && source.error && (
        <p className="px-4 pb-3 text-xs text-danger">{source.error}</p>
      )}

      {expanded && source.status === 'ready' && (
        <div className="space-y-3 px-4 pb-4 text-sm">
          <div className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-muted uppercase">
            <SparkIcon size={14} /> Quellen-Guide
          </div>
          {source.guide_status === 'pending' && (
            <p className="flex items-center gap-2 text-muted">
              <Spinner size={14} /> Zusammenfassung wird erstellt …
            </p>
          )}
          {source.guide_status === 'error' && (
            <div className="space-y-2">
              <p className="text-xs text-danger">{source.guide_error ?? 'Guide konnte nicht erstellt werden.'}</p>
              <button className="btn-ghost -ml-3" onClick={onRetryGuide}>
                <RefreshIcon /> Erneut versuchen
              </button>
            </div>
          )}
          {source.guide_status === 'ready' && (
            <>
              <p className="leading-relaxed">{source.summary}</p>
              {source.key_topics.length > 0 && (
                <ul className="flex flex-wrap gap-1.5">
                  {source.key_topics.map((topic) => (
                    <li key={topic} className="rounded-full border border-line bg-surface px-2 py-0.5 text-xs">
                      {topic}
                    </li>
                  ))}
                </ul>
              )}
              {source.suggested_questions.length > 0 && (
                <ul className="space-y-1">
                  {source.suggested_questions.map((question) => (
                    <li key={question}>
                      <button
                        className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-left text-xs hover:border-accent"
                        onClick={() => onAsk(question)}
                      >
                        {question}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
          <div className="-ml-3 flex flex-wrap gap-1">
            <button className="btn-ghost" onClick={onRename}>
              <EditIcon size={14} /> Umbenennen
            </button>
            <button className="btn-danger" onClick={onRemove}>
              <TrashIcon size={14} /> Quelle entfernen
            </button>
          </div>
        </div>
      )}
    </li>
  )
}
