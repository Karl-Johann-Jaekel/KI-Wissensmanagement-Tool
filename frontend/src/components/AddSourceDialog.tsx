import { useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react'
import { api } from '../api'
import { errorText } from '../hooks'
import type { Source } from '../types'
import { CloseIcon, FileIcon, LinkIcon, Spinner } from './Icons'

const ACCEPT = '.pdf,.txt,.md,.markdown'

interface Props {
  notebookId: string
  onAdded: (source: Source) => void
  onClose: () => void
}

export function AddSourceDialog({ notebookId, onAdded, onClose }: Props) {
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState<string[]>([])
  const [dragging, setDragging] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function uploadFiles(files: FileList | File[]) {
    const list = Array.from(files)
    if (list.length === 0) return
    setBusy(true)
    setErrors([])
    const failures: string[] = []
    for (const file of list) {
      try {
        onAdded(await api.uploadSource(notebookId, file))
      } catch (err) {
        failures.push(`${file.name}: ${errorText(err)}`)
      }
    }
    setBusy(false)
    if (failures.length) setErrors(failures)
    else onClose()
  }

  async function importUrl(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setErrors([])
    try {
      onAdded(await api.importUrl(notebookId, url.trim()))
      onClose()
    } catch (err) {
      setErrors([errorText(err)])
      setBusy(false)
    }
  }

  function onDrop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    void uploadFiles(event.dataTransfer.files)
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div role="dialog" aria-modal="true" aria-labelledby="add-source-title" className="panel w-full max-w-lg rounded-b-none sm:rounded-2xl">
        <div className="panel-header">
          <h2 id="add-source-title" className="font-medium">Quellen hinzufügen</h2>
          <button className="btn-ghost p-1.5" onClick={onClose} aria-label="Schließen">
            <CloseIcon />
          </button>
        </div>

        <div className="space-y-5 p-4">
          <div
            onDragOver={(e) => {
              e.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={`flex flex-col items-center gap-2 rounded-xl border-2 border-dashed p-6 text-center transition-colors ${
              dragging ? 'border-accent bg-accent-soft' : 'border-line'
            }`}
          >
            <FileIcon size={28} className="text-muted" />
            <p className="text-sm">Dateien hierher ziehen oder</p>
            <button className="btn-primary" onClick={() => fileInput.current?.click()} disabled={busy}>
              {busy ? <Spinner /> : null} Dateien auswählen
            </button>
            <p className="text-xs text-muted">PDF (mit Text), TXT, Markdown · max. 20 MB</p>
            <input
              ref={fileInput}
              type="file"
              accept={ACCEPT}
              multiple
              hidden
              onChange={(e) => {
                if (e.target.files) void uploadFiles(e.target.files)
                e.target.value = ''
              }}
            />
          </div>

          <form onSubmit={importUrl} className="space-y-2">
            <label htmlFor="source-url" className="flex items-center gap-1.5 text-sm font-medium">
              <LinkIcon /> Webseite importieren
            </label>
            <div className="flex gap-2">
              <input
                id="source-url"
                className="input"
                type="url"
                inputMode="url"
                placeholder="https://…"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
              <button className="btn-primary shrink-0" disabled={busy || !/^https?:\/\/\S+\.\S+/.test(url.trim())}>
                Import
              </button>
            </div>
          </form>

          {errors.length > 0 && (
            <ul className="space-y-1 rounded-lg bg-danger-soft p-3 text-sm text-danger">
              {errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
