import { useState, type ReactNode } from 'react'
import { api } from '../api'
import { errorText } from '../hooks'
import type { Citation, Note, ReportKind } from '../types'
import { useConfirm } from './Dialogs'
import {
  CloseIcon,
  EditIcon,
  FaqIcon,
  MapIcon,
  NoteIcon,
  PlusIcon,
  SparkIcon,
  Spinner,
  TrashIcon,
} from './Icons'
import { RichText } from './RichText'

interface Props {
  notebookId: string
  notes: Note[] | undefined
  loadError: string | null
  selectedSourceIds: string[]
  onChange: (update: (notes: Note[]) => Note[]) => void
  onCitation: (citation: Citation) => void
  onOpenTopics: () => void
  className?: string
}

/** Collapsed preview: markers and bold markup would only add noise to two lines of text. */
const plainPreview = (content: string) =>
  content.replaceAll('**', '').replace(/\s*\[\d+\]/g, '')

const timeFormat = new Intl.DateTimeFormat('de-DE', { dateStyle: 'short', timeStyle: 'short' })

export function StudioPanel({
  notebookId,
  notes,
  loadError,
  selectedSourceIds,
  onChange,
  onCitation,
  onOpenTopics,
  className = '',
}: Props) {
  const [editing, setEditing] = useState<string | 'new' | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [running, setRunning] = useState<ReportKind | null>(null)
  const [confirm, confirmDialog] = useConfirm()

  async function createReport(kind: ReportKind) {
    setActionError(null)
    setRunning(kind)
    try {
      const note = await api.createReport(notebookId, kind, selectedSourceIds)
      onChange((list) => [note, ...list])
      setOpenId(note.id)
    } catch (err) {
      setActionError(errorText(err))
    } finally {
      setRunning(null)
    }
  }

  async function save(note: Note | null, title: string, content: string) {
    setActionError(null)
    try {
      if (note) {
        const updated = await api.updateNote(note.id, { title, content })
        onChange((list) => [updated, ...list.filter((n) => n.id !== updated.id)])
      } else {
        const created = await api.createNote(notebookId, title, content)
        onChange((list) => [created, ...list])
        setOpenId(created.id)
      }
      setEditing(null)
    } catch (err) {
      setActionError(errorText(err))
    }
  }

  async function remove(note: Note) {
    const ok = await confirm({
      title: 'Notiz löschen?',
      body: `„${note.title}“ lässt sich danach nicht wiederherstellen.`,
      confirmLabel: 'Löschen',
      danger: true,
    })
    if (!ok) return
    try {
      await api.deleteNote(note.id)
      onChange((list) => list.filter((n) => n.id !== note.id))
    } catch (err) {
      setActionError(errorText(err))
    }
  }

  return (
    <section className={`panel ${className}`} aria-label="Studio">
      <div className="panel-header">
        <h2 className="font-medium">Studio</h2>
        <button className="btn-ghost" onClick={() => setEditing('new')} disabled={editing === 'new'}>
          <PlusIcon /> Notiz
        </button>
      </div>

      {/* Everything the notebook can produce from its sources, in one place. */}
      <div className="grid grid-cols-2 gap-2 border-b border-line p-3">
        <Tile
          icon={running === 'briefing' ? Spinner : SparkIcon}
          label="Briefing"
          hint="Kernfragen, belegt"
          onClick={() => void createReport('briefing')}
          disabled={running !== null || selectedSourceIds.length === 0}
        />
        <Tile
          icon={running === 'faq' ? Spinner : FaqIcon}
          label="FAQ"
          hint="Fragen der Quellen"
          onClick={() => void createReport('faq')}
          disabled={running !== null || selectedSourceIds.length === 0}
        />
        <Tile
          icon={MapIcon}
          label="Themenkarte"
          hint="Kernthemen im Überblick"
          onClick={onOpenTopics}
          className="col-span-2"
        />
      </div>

      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
        {actionError && <p className="text-sm text-danger">{actionError}</p>}
        {running && (
          <p className="flex items-center gap-2 rounded-xl bg-surface-muted px-3 py-2 text-xs text-muted">
            <Spinner size={14} /> Jede Frage wird einzeln aus den Quellen beantwortet und belegt.
            Das dauert etwa eine Minute.
          </p>
        )}
        {loadError && <p className="text-sm text-danger">{loadError}</p>}
        {editing === 'new' && (
          <NoteEditor onSave={(t, c) => save(null, t, c)} onCancel={() => setEditing(null)} />
        )}

        {notes === undefined && !loadError ? (
          <div className="flex justify-center py-8 text-muted">
            <Spinner />
          </div>
        ) : notes?.length === 0 && editing !== 'new' ? (
          <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
            <NoteIcon size={28} className="text-muted" />
            <p className="text-sm font-medium">Noch keine Notizen</p>
            <p className="text-xs text-muted">Speichere Antworten aus dem Chat oder schreibe eigene Notizen.</p>
          </div>
        ) : (
          notes?.map((note) =>
            editing === note.id ? (
              <NoteEditor
                key={note.id}
                initial={note}
                onSave={(t, c) => save(note, t, c)}
                onCancel={() => setEditing(null)}
              />
            ) : (
              <article key={note.id} className="rounded-xl border border-line">
                <button
                  className="w-full px-3 py-2.5 text-left"
                  onClick={() => setOpenId(openId === note.id ? null : note.id)}
                  aria-expanded={openId === note.id}
                >
                  <h3 className="text-sm font-medium break-words">{note.title}</h3>
                  {openId !== note.id && (
                    <p className="mt-1 line-clamp-2 text-xs text-muted">{plainPreview(note.content)}</p>
                  )}
                  <p className="mt-1 text-[11px] text-muted">{timeFormat.format(new Date(note.updated_at))}</p>
                </button>
                {openId === note.id && (
                  <div className="space-y-2 border-t border-line px-3 py-3">
                    <RichText text={note.content} citations={note.citations} onCitation={onCitation} />
                    <div className="flex gap-1">
                      <button className="btn-ghost -ml-3" onClick={() => setEditing(note.id)}>
                        <EditIcon size={14} /> Bearbeiten
                      </button>
                      <button className="btn-danger" onClick={() => void remove(note)}>
                        <TrashIcon size={14} /> Löschen
                      </button>
                    </div>
                  </div>
                )}
              </article>
            ),
          )
        )}
      </div>
      {confirmDialog}
    </section>
  )
}

function Tile({
  icon: Icon,
  label,
  hint,
  onClick,
  disabled = false,
  className = '',
}: {
  icon: (props: { size?: number }) => ReactNode
  label: string
  hint: string
  onClick: () => void
  disabled?: boolean
  className?: string
}) {
  return (
    <button
      className={`flex items-center gap-2 rounded-xl border border-line px-3 py-2.5 text-left transition-colors hover:border-accent hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-line disabled:hover:bg-transparent ${className}`}
      onClick={onClick}
      disabled={disabled}
    >
      <span className="shrink-0 text-accent">
        <Icon size={16} />
      </span>
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium">{label}</span>
        <span className="block truncate text-xs text-muted">{hint}</span>
      </span>
    </button>
  )
}

function NoteEditor({
  initial,
  onSave,
  onCancel,
}: {
  initial?: Note
  onSave: (title: string, content: string) => Promise<void>
  onCancel: () => void
}) {
  const [title, setTitle] = useState(initial?.title ?? '')
  const [content, setContent] = useState(initial?.content ?? '')
  const [saving, setSaving] = useState(false)

  async function submit() {
    setSaving(true)
    await onSave(title.trim(), content)
    setSaving(false)
  }

  return (
    <div className="space-y-2 rounded-xl border border-accent p-3">
      <div className="flex items-center gap-2">
        <input
          className="input"
          placeholder="Titel"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          autoFocus
          aria-label="Titel der Notiz"
        />
        <button className="btn-ghost p-1.5" onClick={onCancel} aria-label="Abbrechen">
          <CloseIcon />
        </button>
      </div>
      <textarea
        className="input min-h-40 resize-y"
        placeholder="Notiz …"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        aria-label="Inhalt der Notiz"
      />
      <div className="flex justify-end gap-2">
        <button className="btn-ghost" onClick={onCancel}>
          Abbrechen
        </button>
        <button className="btn-primary" onClick={() => void submit()} disabled={!title.trim() || saving}>
          {saving && <Spinner size={14} />} Speichern
        </button>
      </div>
    </div>
  )
}
