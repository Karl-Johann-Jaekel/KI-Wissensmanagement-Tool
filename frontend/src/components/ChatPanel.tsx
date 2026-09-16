import {
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type Ref,
} from 'react'
import { ApiError, api } from '../api'
import { errorText, useLoader } from '../hooks'
import type { ChatResponse, Citation, Message, Note, Notebook, Source } from '../types'
import { useConfirm } from './Dialogs'
import {
  ArrowRightIcon,
  CopyIcon,
  NoteIcon,
  RefreshIcon,
  SparkIcon,
  Spinner,
  TrashIcon,
} from './Icons'
import { RichText } from './RichText'

export interface ChatHandle {
  ask: (question: string) => void
}

interface Props {
  ref?: Ref<ChatHandle>
  notebookId: string
  notebook: Notebook | undefined
  sources: Source[] | undefined
  selectedSourceIds: string[]
  onCitation: (citation: Citation) => void
  onNoteCreated: (note: Note) => void
  className?: string
}

export function ChatPanel({
  ref,
  notebookId,
  notebook,
  sources,
  selectedSourceIds,
  onCitation,
  onNoteCreated,
  className = '',
}: Props) {
  const messages = useLoader(() => api.listMessages(notebookId), `messages-${notebookId}`)
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState<Pending | null>(null)
  const [sendError, setSendError] = useState<{ question: string; message: string } | null>(null)
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set())
  const [noteError, setNoteError] = useState<string | null>(null)
  const [confirm, confirmDialog] = useConfirm()
  const scrollRef = useRef<HTMLDivElement>(null)

  const readySources = sources?.filter((s) => s.status === 'ready') ?? []
  const canAsk = readySources.length > 0 && selectedSourceIds.length > 0
  // Questions that span the notebook come first; per-source questions fill the rest.
  const suggestions = [
    ...(notebook?.key_questions ?? []),
    ...pickAcrossSources(
      readySources.filter((s) => selectedSourceIds.includes(s.id)).map((s) => s.suggested_questions),
    ),
  ].slice(0, 4)

  // Follow the answer while it is written, but stop fighting a reader who scrolled up.
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120
    if (atBottom || !pending?.text) {
      el.scrollTo({ top: el.scrollHeight, behavior: pending?.text ? 'auto' : 'smooth' })
    }
  }, [messages.data?.length, pending?.text, pending?.passages])

  async function ask(question: string) {
    const text = question.trim()
    if (!text || pending || !canAsk) return
    setPending({ question: text, text: '', passages: null })
    setSendError(null)
    setDraft('')
    try {
      let opened = false
      let response: ChatResponse
      try {
        response = await api.chatStream(notebookId, text, selectedSourceIds, {
          onOpen: () => {
            opened = true
          },
          onPassages: (passages) => setPending((p) => (p ? { ...p, passages } : p)),
          onDelta: (piece) => setPending((p) => (p ? { ...p, text: p.text + piece } : p)),
        })
      } catch (err) {
        // The stream never started: a proxy in between may drop event streams. Once it did
        // start, the failure is real and retrying would ask the model a second time.
        if (opened || (err instanceof ApiError && err.status === 401)) throw err
        response = await api.chat(notebookId, text, selectedSourceIds)
      }
      messages.setData((list = []) => [...list, response.question, response.answer])
    } catch (err) {
      setSendError({ question: text, message: errorText(err) })
      setDraft(text)
    } finally {
      setPending(null)
    }
  }

  // Lets the source guide send its suggested questions into this chat.
  useImperativeHandle(ref, () => ({ ask: (question: string) => void ask(question) }))

  async function saveAsNote(message: Message) {
    setNoteError(null)
    try {
      onNoteCreated(await api.noteFromMessage(notebookId, message.id))
      setSavedIds((ids) => new Set(ids).add(message.id))
    } catch (err) {
      setNoteError(errorText(err))
    }
  }

  async function clearChat() {
    const ok = await confirm({
      title: 'Chatverlauf löschen?',
      body: 'Gespeicherte Notizen bleiben erhalten.',
      confirmLabel: 'Löschen',
      danger: true,
    })
    if (!ok) return
    try {
      await api.clearMessages(notebookId)
      messages.setData(() => [])
    } catch (err) {
      setNoteError(errorText(err))
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    void ask(draft)
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      void ask(draft)
    }
  }

  const list = messages.data ?? []
  const ready = canAsk && draft.trim().length > 0 && !pending

  return (
    <section className={`panel ${className}`} aria-label="Chat">
      <div className="panel-header">
        <h2 className="font-medium">Chat</h2>
        {list.length > 0 && (
          <button className="btn-ghost" onClick={() => void clearChat()}>
            <TrashIcon size={14} /> Verlauf löschen
          </button>
        )}
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-6 overflow-y-auto px-4 py-6" aria-live="polite">
        {messages.loading && (
          <div className="flex justify-center text-muted">
            <Spinner />
          </div>
        )}
        {messages.error && (
          <div className="flex flex-col items-center gap-2 text-sm">
            <p className="text-danger">{messages.error}</p>
            <button className="btn-ghost" onClick={() => void messages.reload()}>
              Erneut laden
            </button>
          </div>
        )}

        {!messages.loading && list.length === 0 && !pending && (
          <EmptyChat
            hasSources={readySources.length > 0}
            processing={sources?.some((s) => s.status === 'processing') ?? false}
            overview={notebook?.overview_status === 'ready' ? notebook.summary : null}
            suggestions={suggestions}
            onAsk={(q) => void ask(q)}
          />
        )}

        {list.map((message) =>
          message.role === 'user' ? (
            <Question key={message.id} text={message.content} />
          ) : (
            <article key={message.id} className="max-w-[95%] space-y-2">
              <RichText text={message.content} citations={message.citations} onCitation={onCitation} />
              <div className="flex flex-wrap items-center gap-2">
                <button
                  className="btn-ghost -ml-3 text-xs"
                  onClick={() => void saveAsNote(message)}
                  disabled={savedIds.has(message.id)}
                >
                  <NoteIcon size={14} /> {savedIds.has(message.id) ? 'Als Notiz gespeichert' : 'Als Notiz speichern'}
                </button>
                <CopyButton text={message.content} />
                {message.citations.length > 0 && (
                  <span className="text-xs text-muted">
                    {message.citations.length === 1 ? '1 Beleg' : `${message.citations.length} Belege`}
                  </span>
                )}
              </div>
            </article>
          ),
        )}

        {pending && (
          <>
            <Question text={pending.question} dimmed />
            {pending.text ? (
              <article className="max-w-[95%] space-y-2">
                {/* Raw model output: the markers become clickable chips once validated. */}
                <RichText text={pending.text} />
                <p className="flex items-center gap-2 text-xs text-muted">
                  <Spinner size={12} /> schreibt …
                </p>
              </article>
            ) : (
              <p className="flex items-center gap-2 text-sm text-muted">
                <Spinner size={14} />
                {pending.passages
                  ? `${passageText(pending.passages)} – formuliere Antwort …`
                  : 'Durchsuche Quellen …'}
              </p>
            )}
          </>
        )}
      </div>

      <div className="border-t border-line p-3">
        {sendError && (
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
            <span>{sendError.message}</span>
            <button className="btn-ghost text-danger" onClick={() => void ask(sendError.question)}>
              <RefreshIcon size={14} /> Erneut senden
            </button>
          </div>
        )}
        {noteError && <p className="mb-2 text-sm text-danger">{noteError}</p>}
        {/* One rounded field holding the text and the send button, like NotebookLM. */}
        <form
          onSubmit={onSubmit}
          className="flex items-end gap-2 rounded-3xl border border-line bg-surface px-3 py-2 transition-colors focus-within:border-accent"
        >
          <textarea
            className="max-h-40 min-h-9 flex-1 resize-none bg-transparent py-1.5 text-sm text-fg outline-none placeholder:text-muted"
            rows={1}
            placeholder={
              readySources.length === 0
                ? 'Füge zuerst eine Quelle hinzu …'
                : selectedSourceIds.length === 0
                  ? 'Wähle mindestens eine Quelle aus …'
                  : 'Frage zu deinen Quellen stellen …'
            }
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={!canAsk}
            aria-label="Frage"
          />
          {/* Grey until there is something to send, then it turns into the accent colour. */}
          <button
            className={`btn size-9 shrink-0 p-0 ${
              ready ? 'bg-accent text-accent-fg hover:opacity-90' : 'bg-surface-muted text-muted'
            }`}
            disabled={!ready}
            aria-label="Senden"
          >
            {pending ? <Spinner size={15} /> : <ArrowRightIcon size={18} />}
          </button>
        </form>
        <p className="mt-2 text-center text-[11px] text-muted">
          {canAsk
            ? `Antworten basieren nur auf ${selectedSourceIds.length === 1 ? '1 ausgewählten Quelle' : `${selectedSourceIds.length} ausgewählten Quellen`} und können Fehler enthalten.`
            : 'Antworten basieren ausschließlich auf deinen Quellen.'}
        </p>
      </div>
      {confirmDialog}
    </section>
  )
}

interface Pending {
  question: string
  text: string
  passages: { count: number; sources: number } | null
}

function passageText({ count, sources }: { count: number; sources: number }): string {
  const passages = count === 1 ? '1 Passage' : `${count} Passagen`
  return sources === 1 ? `${passages} aus 1 Quelle` : `${passages} aus ${sources} Quellen`
}

/** Round-robin, so every selected source contributes before any source repeats. */
function pickAcrossSources(perSource: string[][], limit = 4): string[] {
  const picked: string[] = []
  const depth = Math.max(0, ...perSource.map((q) => q.length))
  for (let i = 0; i < depth && picked.length < limit; i++) {
    for (const questions of perSource) {
      const question = questions[i]
      if (question !== undefined && picked.length < limit) picked.push(question)
    }
  }
  return picked
}

function Question({ text, dimmed = false }: { text: string; dimmed?: boolean }) {
  return (
    <div className="flex justify-end">
      <p
        className={`max-w-[85%] rounded-2xl rounded-br-md bg-accent px-4 py-2 text-sm whitespace-pre-wrap text-accent-fg ${dimmed ? 'opacity-80' : ''}`}
      >
        {text}
      </p>
    </div>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      className="btn-ghost text-xs"
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => {
          setCopied(true)
          window.setTimeout(() => setCopied(false), 1500)
        })
      }}
    >
      <CopyIcon size={14} /> {copied ? 'Kopiert' : 'Kopieren'}
    </button>
  )
}

function EmptyChat({
  hasSources,
  processing,
  overview,
  suggestions,
  onAsk,
}: {
  hasSources: boolean
  processing: boolean
  overview: string | null
  suggestions: string[]
  onAsk: (question: string) => void
}) {
  return (
    // The overview runs several lines: centred text is hard to read, so it gets a wider,
    // left-aligned block while the rest of the empty state stays centred.
    <div
      className={`mx-auto flex flex-col items-center gap-3 py-8 text-center ${overview ? 'max-w-xl' : 'max-w-md'}`}
    >
      <SparkIcon size={28} className="text-accent" />
      {hasSources ? (
        <>
          <p className="font-medium">Was möchtest du wissen?</p>
          {overview ? (
            <p className="text-left text-sm leading-relaxed text-muted">{overview}</p>
          ) : (
            <p className="text-sm text-muted">
              Jede Aussage wird mit einem klickbaren Beleg aus deinen Quellen versehen.
            </p>
          )}
          {suggestions.length > 0 && (
            <ul className="mt-2 w-full space-y-2">
              {suggestions.map((question) => (
                <li key={question}>
                  <button
                    className="w-full rounded-2xl border border-line px-4 py-2.5 text-left text-sm hover:border-accent hover:bg-accent-soft"
                    onClick={() => onAsk(question)}
                  >
                    {question}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      ) : (
        <>
          <p className="font-medium">{processing ? 'Quellen werden verarbeitet …' : 'Noch keine Quellen'}</p>
          <p className="text-sm text-muted">
            {processing
              ? 'Sobald die erste Quelle bereit ist, kannst du Fragen stellen.'
              : 'Füge eine Quelle hinzu, um mit dem Chat zu beginnen.'}
          </p>
        </>
      )}
    </div>
  )
}
