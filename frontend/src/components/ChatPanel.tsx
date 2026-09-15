import {
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type Ref,
} from 'react'
import { api } from '../api'
import { errorText, useLoader } from '../hooks'
import type { Citation, Message, Note, Source } from '../types'
import { NoteIcon, RefreshIcon, SendIcon, SparkIcon, Spinner, TrashIcon } from './Icons'
import { RichText } from './RichText'

export interface ChatHandle {
  ask: (question: string) => void
}

interface Props {
  ref?: Ref<ChatHandle>
  notebookId: string
  sources: Source[] | undefined
  selectedSourceIds: string[]
  onCitation: (citation: Citation) => void
  onNoteCreated: (note: Note) => void
  className?: string
}

export function ChatPanel({
  ref,
  notebookId,
  sources,
  selectedSourceIds,
  onCitation,
  onNoteCreated,
  className = '',
}: Props) {
  const messages = useLoader(() => api.listMessages(notebookId), `messages-${notebookId}`)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState<string | null>(null)
  const [sendError, setSendError] = useState<{ question: string; message: string } | null>(null)
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set())
  const [noteError, setNoteError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  const readySources = sources?.filter((s) => s.status === 'ready') ?? []
  const canAsk = readySources.length > 0 && selectedSourceIds.length > 0
  const suggestions = readySources
    .filter((s) => selectedSourceIds.includes(s.id))
    .flatMap((s) => s.suggested_questions)
    .slice(0, 4)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages.data?.length, sending])

  async function ask(question: string) {
    const text = question.trim()
    if (!text || sending || !canAsk) return
    setSending(text)
    setSendError(null)
    setDraft('')
    try {
      const response = await api.chat(notebookId, text, selectedSourceIds)
      messages.setData((list = []) => [...list, response.question, response.answer])
    } catch (err) {
      setSendError({ question: text, message: errorText(err) })
      setDraft(text)
    } finally {
      setSending(null)
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
    if (!window.confirm('Chatverlauf löschen? Gespeicherte Notizen bleiben erhalten.')) return
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

        {!messages.loading && list.length === 0 && !sending && (
          <EmptyChat
            hasSources={readySources.length > 0}
            processing={sources?.some((s) => s.status === 'processing') ?? false}
            suggestions={suggestions}
            onAsk={(q) => void ask(q)}
          />
        )}

        {list.map((message) =>
          message.role === 'user' ? (
            <div key={message.id} className="flex justify-end">
              <p className="max-w-[85%] rounded-2xl rounded-br-md bg-accent px-4 py-2 text-sm whitespace-pre-wrap text-accent-fg">
                {message.content}
              </p>
            </div>
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
                {message.citations.length > 0 && (
                  <span className="text-xs text-muted">
                    {message.citations.length === 1 ? '1 Beleg' : `${message.citations.length} Belege`}
                  </span>
                )}
              </div>
            </article>
          ),
        )}

        {sending && (
          <>
            <div className="flex justify-end">
              <p className="max-w-[85%] rounded-2xl rounded-br-md bg-accent px-4 py-2 text-sm whitespace-pre-wrap text-accent-fg opacity-80">
                {sending}
              </p>
            </div>
            <p className="flex items-center gap-2 text-sm text-muted">
              <Spinner size={14} /> Durchsuche Quellen und formuliere Antwort …
            </p>
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
        <form onSubmit={onSubmit} className="flex items-end gap-2">
          <textarea
            className="input max-h-40 min-h-11 resize-none"
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
          <button className="btn-primary size-11 shrink-0 p-0" disabled={!canAsk || !draft.trim() || !!sending} aria-label="Senden">
            {sending ? <Spinner /> : <SendIcon />}
          </button>
        </form>
        <p className="mt-2 text-center text-[11px] text-muted">
          {canAsk
            ? `Antworten basieren nur auf ${selectedSourceIds.length === 1 ? '1 ausgewählten Quelle' : `${selectedSourceIds.length} ausgewählten Quellen`} und können Fehler enthalten.`
            : 'Antworten basieren ausschließlich auf deinen Quellen.'}
        </p>
      </div>
    </section>
  )
}

function EmptyChat({
  hasSources,
  processing,
  suggestions,
  onAsk,
}: {
  hasSources: boolean
  processing: boolean
  suggestions: string[]
  onAsk: (question: string) => void
}) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-3 py-8 text-center">
      <SparkIcon size={28} className="text-accent" />
      {hasSources ? (
        <>
          <p className="font-medium">Was möchtest du wissen?</p>
          <p className="text-sm text-muted">Jede Aussage wird mit einem klickbaren Beleg aus deinen Quellen versehen.</p>
          {suggestions.length > 0 && (
            <ul className="mt-2 w-full space-y-2">
              {suggestions.map((question) => (
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
          )}
        </>
      ) : (
        <>
          <p className="font-medium">{processing ? 'Quellen werden verarbeitet …' : 'Noch keine Quellen'}</p>
          <p className="text-sm text-muted">
            {processing
              ? 'Sobald die erste Quelle bereit ist, kannst du Fragen stellen.'
              : 'Füge links eine Quelle hinzu, um mit dem Chat zu beginnen.'}
          </p>
        </>
      )}
    </div>
  )
}
