import { useState } from 'react'
import { api } from '../api'
import { errorText, useLoader } from '../hooks'
import type { Notebook } from '../types'
import { useConfirm, usePrompt } from './Dialogs'
import {
  CloseIcon,
  EditIcon,
  GridIcon,
  ListIcon,
  NoteIcon,
  PlusIcon,
  SearchIcon,
  Spinner,
  TrashIcon,
} from './Icons'

const dateFormat = new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium' })
const VIEW_STORAGE = 'notebook.listView'

type View = 'grid' | 'list'

function storedView(): View {
  try {
    return localStorage.getItem(VIEW_STORAGE) === 'list' ? 'list' : 'grid'
  } catch {
    return 'grid'
  }
}

export function NotebookList({ onOpen }: { onOpen: (id: string) => void }) {
  const notebooks = useLoader(api.listNotebooks, 'notebooks')
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [view, setView] = useState<View>(storedView)
  const [query, setQuery] = useState<string | null>(null)
  const [confirm, confirmDialog] = useConfirm()
  const [prompt, promptDialog] = usePrompt()

  const all = notebooks.data ?? []
  const needle = (query ?? '').trim().toLowerCase()
  const shown = needle ? all.filter((n) => n.title.toLowerCase().includes(needle)) : all

  function chooseView(next: View) {
    setView(next)
    try {
      localStorage.setItem(VIEW_STORAGE, next)
    } catch {
      // storage unavailable: the choice lasts for this page load
    }
  }

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
    const title = await prompt({
      title: 'Notebook umbenennen',
      label: 'Titel',
      initial: notebook.title,
    })
    if (!title || title === notebook.title) return
    try {
      const updated = await api.renameNotebook(notebook.id, title)
      notebooks.setData((list = []) => list.map((n) => (n.id === updated.id ? updated : n)))
    } catch (err) {
      setActionError(errorText(err))
    }
  }

  async function remove(notebook: Notebook) {
    const ok = await confirm({
      title: 'Notebook löschen?',
      body: `„${notebook.title}“ verschwindet mit allen Quellen, Chats und Notizen.`,
      confirmLabel: 'Löschen',
      danger: true,
    })
    if (!ok) return
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

        <div className="flex items-center gap-2">
          {all.length > 0 && (
            <>
              {query === null ? (
                <button
                  className="btn-ghost size-9 p-0"
                  onClick={() => setQuery('')}
                  aria-label="Notebooks durchsuchen"
                >
                  <SearchIcon />
                </button>
              ) : (
                <div className="flex items-center gap-1">
                  <input
                    className="input h-9 w-44 rounded-full"
                    placeholder="Titel suchen …"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Escape' && setQuery(null)}
                    autoFocus
                    aria-label="Notebooks durchsuchen"
                  />
                  <button
                    className="btn-ghost size-9 p-0"
                    onClick={() => setQuery(null)}
                    aria-label="Suche schließen"
                  >
                    <CloseIcon />
                  </button>
                </div>
              )}

              <div className="flex rounded-full border border-line p-0.5" role="group" aria-label="Ansicht">
                {(
                  [
                    ['grid', 'Kacheln', GridIcon],
                    ['list', 'Liste', ListIcon],
                  ] as const
                ).map(([name, label, Icon]) => (
                  <button
                    key={name}
                    className={`btn size-8 p-0 ${
                      view === name ? 'bg-surface text-fg shadow-sm' : 'text-muted hover:text-fg'
                    }`}
                    onClick={() => chooseView(name)}
                    aria-label={label}
                    aria-pressed={view === name}
                  >
                    <Icon size={15} />
                  </button>
                ))}
              </div>
            </>
          )}

          <button className="btn-elevated px-4 py-2" onClick={create} disabled={busy}>
            {busy ? <Spinner /> : <PlusIcon />} Neues Notebook
          </button>
        </div>
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
      ) : all.length === 0 ? (
        <div className="panel items-center gap-2 p-10 text-center">
          <NoteIcon size={28} className="text-muted" />
          <p className="font-medium">Noch keine Notebooks</p>
          <p className="text-sm text-muted">Lege ein Notebook an und füge PDFs, Texte oder Links hinzu.</p>
        </div>
      ) : shown.length === 0 ? (
        <div className="panel items-center gap-2 p-10 text-center">
          <SearchIcon size={28} className="text-muted" />
          <p className="font-medium">Kein Notebook mit „{query}“</p>
        </div>
      ) : (
        <ul
          className={
            view === 'grid' ? 'grid gap-4 sm:grid-cols-2 lg:grid-cols-3' : 'flex flex-col gap-2'
          }
        >
          {shown.map((notebook) => (
            <li
              key={notebook.id}
              className={`panel group relative hover:border-accent ${
                view === 'grid' ? 'p-4' : 'flex-row items-center gap-3 px-4 py-3'
              }`}
            >
              <button
                className="absolute inset-0 rounded-2xl"
                onClick={() => onOpen(notebook.id)}
                aria-label={`${notebook.title} öffnen`}
              />
              <h2 className={`font-medium break-words ${view === 'grid' ? 'pr-16' : 'min-w-0 flex-1'}`}>
                {notebook.title}
              </h2>
              <p className={`text-xs text-muted ${view === 'grid' ? 'mt-6' : 'shrink-0 pr-20'}`}>
                {dateFormat.format(new Date(notebook.created_at))} ·{' '}
                {notebook.source_count === 1 ? '1 Quelle' : `${notebook.source_count} Quellen`}
              </p>
              <div
                className={`absolute right-3 flex gap-1 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100 ${
                  view === 'grid' ? 'top-3' : 'top-1/2 -translate-y-1/2'
                }`}
              >
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
      {confirmDialog}
      {promptDialog}
    </main>
  )
}
