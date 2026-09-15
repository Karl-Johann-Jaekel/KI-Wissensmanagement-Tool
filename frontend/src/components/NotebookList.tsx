import { useState } from 'react'
import { api } from '../api'
import { errorText, useLoader } from '../hooks'
import type { Notebook } from '../types'
import { EditIcon, NoteIcon, PlusIcon, Spinner, TrashIcon } from './Icons'

const dateFormat = new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium' })

export function NotebookList({ onOpen }: { onOpen: (id: string) => void }) {
  const notebooks = useLoader(api.listNotebooks, 'notebooks')
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  async function create() {
    setBusy(true)
    setActionError(null)
    try {
      const notebook = await api.createNotebook()
      onOpen(notebook.id)
    } catch (err) {
      setActionError(errorText(err))
      setBusy(false)
    }
  }

  async function rename(notebook: Notebook) {
    const title = window.prompt('Neuer Titel', notebook.title)?.trim()
    if (!title || title === notebook.title) return
    try {
      const updated = await api.renameNotebook(notebook.id, title)
      notebooks.setData((list = []) => list.map((n) => (n.id === updated.id ? updated : n)))
    } catch (err) {
      setActionError(errorText(err))
    }
  }

  async function remove(notebook: Notebook) {
    if (!window.confirm(`„${notebook.title}“ mit allen Quellen, Chats und Notizen löschen?`)) return
    try {
      await api.deleteNotebook(notebook.id)
      notebooks.setData((list = []) => list.filter((n) => n.id !== notebook.id))
    } catch (err) {
      setActionError(errorText(err))
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:py-12">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Notebooks</h1>
          <p className="mt-1 text-sm text-muted">
            Quellen hochladen, Fragen stellen, Antworten mit Belegen erhalten.
          </p>
        </div>
        <button className="btn-primary px-4 py-2" onClick={create} disabled={busy}>
          {busy ? <Spinner /> : <PlusIcon />} Neues Notebook
        </button>
      </header>

      {actionError && <p className="mb-4 text-sm text-danger">{actionError}</p>}

      {notebooks.loading ? (
        <div className="flex justify-center py-16 text-muted">
          <Spinner size={24} />
        </div>
      ) : notebooks.error ? (
        <div className="panel items-center gap-3 p-8 text-center">
          <p className="text-sm text-danger">{notebooks.error}</p>
          <button className="btn-ghost" onClick={() => void notebooks.reload()}>
            Erneut versuchen
          </button>
        </div>
      ) : notebooks.data?.length === 0 ? (
        <div className="panel items-center gap-2 p-10 text-center">
          <NoteIcon size={28} className="text-muted" />
          <p className="font-medium">Noch keine Notebooks</p>
          <p className="text-sm text-muted">Lege ein Notebook an und füge PDFs, Texte oder Links hinzu.</p>
        </div>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {notebooks.data?.map((notebook) => (
            <li key={notebook.id} className="panel group relative p-4 hover:border-accent">
              <button
                className="absolute inset-0 rounded-2xl"
                onClick={() => onOpen(notebook.id)}
                aria-label={`${notebook.title} öffnen`}
              />
              <h2 className="pr-16 font-medium break-words">{notebook.title}</h2>
              <p className="mt-6 text-xs text-muted">
                {dateFormat.format(new Date(notebook.created_at))} ·{' '}
                {notebook.source_count === 1 ? '1 Quelle' : `${notebook.source_count} Quellen`}
              </p>
              <div className="absolute top-3 right-3 flex gap-1 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100">
                <button className="btn-ghost relative p-1.5" onClick={() => void rename(notebook)} aria-label="Umbenennen">
                  <EditIcon />
                </button>
                <button className="btn-danger relative p-1.5" onClick={() => void remove(notebook)} aria-label="Löschen">
                  <TrashIcon />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}
