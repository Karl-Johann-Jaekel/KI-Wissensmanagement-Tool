import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { errorText, useLoader } from '../hooks'
import type { Citation, Note, Source } from '../types'
import { ChatPanel, type ChatHandle } from './ChatPanel'
import { CitationDrawer } from './CitationDrawer'
import { usePrompt } from './Dialogs'
import { BackIcon, EditIcon, Spinner } from './Icons'
import { NotesPanel } from './NotesPanel'
import { SourceGuidePanel } from './SourceGuidePanel'
import { SourcePanel } from './SourcePanel'

type Tab = 'sources' | 'chat' | 'notes'
const POLL_MS = 2000

export function NotebookView({ notebookId, onBack }: { notebookId: string; onBack: () => void }) {
  const notebook = useLoader(() => api.getNotebook(notebookId), `notebook-${notebookId}`)
  const sources = useLoader(() => api.listSources(notebookId), `sources-${notebookId}`)
  const notes = useLoader(() => api.listNotes(notebookId), `notes-${notebookId}`)

  const { reload: reloadSources, setData: setSources } = sources
  const { setData: setNotes } = notes

  const [tab, setTab] = useState<Tab>('chat')
  const [openSourceId, setOpenSourceId] = useState<string | null>(null)
  const [deselected, setDeselected] = useState<Set<string>>(new Set())
  const [citation, setCitation] = useState<Citation | null>(null)
  const [titleError, setTitleError] = useState<string | null>(null)
  const [prompt, promptDialog] = usePrompt()
  const chatRef = useRef<ChatHandle>(null)

  // Poll while ingestion or guide generation is running.
  const busy = sources.data?.some(
    (s) => s.status === 'processing' || (s.status === 'ready' && s.guide_status === 'pending'),
  )
  useEffect(() => {
    if (!busy) return
    const timer = window.setInterval(() => void reloadSources(), POLL_MS)
    return () => window.clearInterval(timer)
  }, [busy, reloadSources])

  const selectedSourceIds = useMemo(
    () => (sources.data ?? []).filter((s) => s.status === 'ready' && !deselected.has(s.id)).map((s) => s.id),
    [sources.data, deselected],
  )

  const upsertSource = useCallback(
    (source: Source) =>
      setSources((list = []) =>
        list.some((s) => s.id === source.id) ? list.map((s) => (s.id === source.id ? source : s)) : [...list, source],
      ),
    [setSources],
  )

  const removeSource = useCallback(
    (id: string) => setSources((list = []) => list.filter((s) => s.id !== id)),
    [setSources],
  )

  // The open source keeps following the polled list, and closes when it is gone.
  const openSource = (sources.data ?? []).find((s) => s.id === openSourceId) ?? null
  const showSource = useCallback((id: string) => {
    setOpenSourceId(id)
    setTab('chat') // on narrow screens the main column is behind the chat tab
  }, [])
  const closeSource = useCallback(() => setOpenSourceId(null), [])

  function toggleSource(id: string) {
    setDeselected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleAll(select: boolean) {
    setDeselected(select ? new Set() : new Set((sources.data ?? []).map((s) => s.id)))
  }

  async function rename() {
    const current = notebook.data
    if (!current) return
    const title = await prompt({
      title: 'Notebook umbenennen',
      label: 'Titel',
      initial: current.title,
    })
    if (!title || title === current.title) return
    try {
      const updated = await api.renameNotebook(current.id, title)
      notebook.setData(() => updated)
      setTitleError(null)
    } catch (err) {
      setTitleError(errorText(err))
    }
  }

  const askFromGuide = useCallback((question: string) => {
    setOpenSourceId(null)
    setTab('chat')
    chatRef.current?.ask(question)
  }, [])
  const closeCitation = useCallback(() => setCitation(null), [])
  const addNote = useCallback((note: Note) => setNotes((list = []) => [note, ...list]), [setNotes])

  if (notebook.error && !notebook.data) {
    return (
      <main className="flex h-full flex-col items-center justify-center gap-3 p-4 text-center">
        <p className="text-danger">{notebook.error}</p>
        <button className="btn-ghost" onClick={onBack}>
          <BackIcon /> Zur Übersicht
        </button>
      </main>
    )
  }

  const panelClass = (name: Tab) => `${tab === name ? 'flex' : 'hidden'} lg:flex`

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-2 px-3 py-2 sm:px-4">
        <button className="btn-ghost p-2" onClick={onBack} aria-label="Zur Übersicht">
          <BackIcon />
        </button>
        {notebook.data ? (
          <button className="group flex min-w-0 items-center gap-2 text-left" onClick={() => void rename()}>
            <h1 className="truncate text-lg font-semibold">{notebook.data.title}</h1>
            <EditIcon size={14} className="shrink-0 text-muted opacity-0 group-hover:opacity-100" />
          </button>
        ) : (
          <Spinner />
        )}
        {titleError && <span className="text-sm text-danger">{titleError}</span>}
      </header>

      <nav className="grid grid-cols-3 gap-1 px-3 pb-2 lg:hidden" aria-label="Bereiche">
        {(
          [
            ['sources', 'Quellen'],
            ['chat', 'Chat'],
            ['notes', 'Notizen'],
          ] as const
        ).map(([name, label]) => (
          <button
            key={name}
            className={`btn ${tab === name ? 'bg-surface text-fg shadow-sm' : 'text-muted'}`}
            onClick={() => setTab(name)}
            aria-current={tab === name}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="grid min-h-0 flex-1 gap-3 px-3 pb-3 lg:grid-cols-[18rem_minmax(0,1fr)_18rem] xl:grid-cols-[20rem_minmax(0,1fr)_22rem]">
        <SourcePanel
          className={panelClass('sources')}
          notebookId={notebookId}
          sources={sources.data}
          loadError={sources.error}
          deselected={deselected}
          openSourceId={openSourceId}
          onToggle={toggleSource}
          onToggleAll={toggleAll}
          onOpen={showSource}
          onSourceChanged={upsertSource}
        />
        {/* One grid cell for the main column: the chat stays mounted behind an open guide,
            so a running answer is not interrupted by looking something up. */}
        <div className={`${panelClass('chat')} min-h-0 flex-col`}>
          {openSource && (
            <SourceGuidePanel
              className="flex-1"
              source={openSource}
              onClose={closeSource}
              onAsk={askFromGuide}
              onSourceChanged={upsertSource}
              onSourceRemoved={removeSource}
            />
          )}
          <ChatPanel
            ref={chatRef}
            className={openSource ? 'hidden' : 'flex-1'}
            notebookId={notebookId}
            sources={sources.data}
            selectedSourceIds={selectedSourceIds}
            onCitation={setCitation}
            onNoteCreated={addNote}
          />
        </div>
        <NotesPanel
          className={panelClass('notes')}
          notebookId={notebookId}
          notes={notes.data}
          loadError={notes.error}
          onChange={(update) => setNotes((list = []) => update(list))}
          onCitation={setCitation}
        />
      </div>

      {citation && <CitationDrawer citation={citation} onClose={closeCitation} />}
      {promptDialog}
    </div>
  )
}
