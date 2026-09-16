import { useState } from 'react'
import { api } from '../api'
import { errorText } from '../hooks'
import type { Source } from '../types'
import { useConfirm, usePrompt } from './Dialogs'
import {
  CloseIcon,
  EditIcon,
  FileIcon,
  LinkIcon,
  RefreshIcon,
  SparkIcon,
  Spinner,
  TrashIcon,
} from './Icons'

interface Props {
  source: Source
  onClose: () => void
  onAsk: (question: string) => void
  onSourceChanged: (source: Source) => void
  onSourceRemoved: (sourceId: string) => void
  className?: string
}

/**
 * Everything about one source, in the main column. The sidebar only lists sources: a summary
 * of a 200-page document pushes the list itself out of view when it lives in an 18rem panel.
 */
export function SourceGuidePanel({
  source,
  onClose,
  onAsk,
  onSourceChanged,
  onSourceRemoved,
  className = '',
}: Props) {
  const [actionError, setActionError] = useState<string | null>(null)
  const [confirm, confirmDialog] = useConfirm()
  const [prompt, promptDialog] = usePrompt()

  const TypeIcon = source.type === 'url' ? LinkIcon : FileIcon
  const meta = [
    source.type.toUpperCase(),
    source.page_count ? `${source.page_count} Seiten` : null,
    source.chunk_count ? `${source.chunk_count} Abschnitte` : null,
  ]
    .filter(Boolean)
    .join(' · ')

  async function rename() {
    const title = await prompt({
      title: 'Quelle umbenennen',
      label: 'Titel der Quelle',
      initial: source.title,
    })
    if (!title || title === source.title) return
    try {
      onSourceChanged(await api.renameSource(source.id, title))
    } catch (err) {
      setActionError(errorText(err))
    }
  }

  async function remove() {
    const ok = await confirm({
      title: 'Quelle entfernen?',
      body: `„${source.title}“ wird mit allen Abschnitten und Belegen gelöscht.`,
      confirmLabel: 'Entfernen',
      danger: true,
    })
    if (!ok) return
    try {
      await api.deleteSource(source.id)
      onSourceRemoved(source.id)
      onClose()
    } catch (err) {
      setActionError(errorText(err))
    }
  }

  async function retryGuide() {
    setActionError(null)
    try {
      onSourceChanged(await api.regenerateGuide(source.id))
    } catch (err) {
      setActionError(errorText(err))
    }
  }

  return (
    <section className={`panel ${className}`} aria-label="Quelle">
      <div className="panel-header">
        <div className="flex min-w-0 items-center gap-2">
          <TypeIcon className="shrink-0 text-muted" />
          <div className="min-w-0">
            <h2 className="truncate font-medium" title={source.origin ?? source.title}>
              {source.title}
            </h2>
            <p className="truncate text-xs text-muted">{meta}</p>
          </div>
        </div>
        <button className="btn-ghost shrink-0" onClick={onClose}>
          <CloseIcon /> <span className="hidden sm:inline">Zum Chat</span>
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
        <div className="max-w-prose space-y-6">
          {actionError && <p className="text-sm text-danger">{actionError}</p>}

          {source.status === 'processing' && (
            <p className="flex items-center gap-2 text-sm text-muted">
              <Spinner size={14} /> Die Quelle wird verarbeitet – Text wird gelesen, zerlegt und
              eingebettet.
            </p>
          )}

          {source.status === 'error' && (
            <div className="space-y-2">
              <p className="text-sm font-medium text-danger">Die Quelle konnte nicht gelesen werden.</p>
              <p className="text-sm text-muted">{source.error}</p>
            </div>
          )}

          {source.status === 'ready' && (
            <>
              <section className="space-y-2">
                <h3 className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-muted uppercase">
                  <SparkIcon size={14} /> Quellen-Guide
                </h3>
                {source.guide_status === 'pending' && (
                  <p className="flex items-center gap-2 text-sm text-muted">
                    <Spinner size={14} /> Zusammenfassung wird erstellt …
                  </p>
                )}
                {source.guide_status === 'error' && (
                  <div className="space-y-2">
                    <p className="text-sm text-danger">
                      {source.guide_error ?? 'Guide konnte nicht erstellt werden.'}
                    </p>
                    <button className="btn-ghost -ml-3" onClick={() => void retryGuide()}>
                      <RefreshIcon /> Erneut versuchen
                    </button>
                  </div>
                )}
                {source.guide_status === 'ready' && (
                  <p className="text-sm leading-relaxed">{source.summary}</p>
                )}
              </section>

              {source.key_topics.length > 0 && (
                <section className="space-y-2">
                  <h3 className="text-xs font-semibold tracking-wide text-muted uppercase">
                    Kernthemen
                  </h3>
                  <ul className="flex flex-wrap gap-1.5">
                    {source.key_topics.map((topic) => (
                      <li
                        key={topic}
                        className="rounded-full border border-line px-2.5 py-1 text-xs"
                      >
                        {topic}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {source.suggested_questions.length > 0 && (
                <section className="space-y-2">
                  <h3 className="text-xs font-semibold tracking-wide text-muted uppercase">
                    Fragen an diese Quelle
                  </h3>
                  <ul className="space-y-2">
                    {source.suggested_questions.map((question) => (
                      <li key={question}>
                        <button
                          className="w-full rounded-xl border border-line px-4 py-2.5 text-left text-sm hover:border-accent hover:bg-accent-soft"
                          onClick={() => onAsk(question)}
                        >
                          {question}
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}
        </div>
      </div>

      <div className="flex flex-wrap justify-between gap-2 border-t border-line px-3 py-2">
        <button className="btn-ghost" onClick={() => void rename()}>
          <EditIcon size={14} /> Umbenennen
        </button>
        <button className="btn-danger" onClick={() => void remove()}>
          <TrashIcon size={14} /> Quelle entfernen
        </button>
      </div>

      {confirmDialog}
      {promptDialog}
    </section>
  )
}
