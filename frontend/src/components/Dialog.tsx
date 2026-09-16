import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { CloseIcon } from './Icons'

export interface ConfirmOptions {
  title: string
  body?: string
  confirmLabel?: string
  danger?: boolean
}

export interface PromptOptions {
  title: string
  label: string
  initial?: string
  confirmLabel?: string
}

/** Shell for the small in-app dialogs: backdrop, Escape and a close button. */
export function Dialog({
  title,
  children,
  onClose,
}: {
  title: string
  children: ReactNode
  onClose: () => void
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        className="panel w-full max-w-sm rounded-b-none sm:rounded-2xl"
      >
        <div className="panel-header">
          <h2 id="dialog-title" className="font-medium">
            {title}
          </h2>
          <button className="btn-ghost p-1.5" onClick={onClose} aria-label="Schließen">
            <CloseIcon />
          </button>
        </div>
        <div className="space-y-4 p-4">{children}</div>
      </div>
    </div>
  )
}

export function ConfirmDialog({
  options,
  onAnswer,
}: {
  options: ConfirmOptions
  onAnswer: (value: boolean) => void
}) {
  return (
    <Dialog title={options.title} onClose={() => onAnswer(false)}>
      {options.body && <p className="text-sm text-muted">{options.body}</p>}
      <div className="flex justify-end gap-2">
        <button className="btn-ghost" onClick={() => onAnswer(false)}>
          Abbrechen
        </button>
        <button
          className={options.danger ? 'btn-destructive' : 'btn-primary'}
          onClick={() => onAnswer(true)}
          autoFocus
        >
          {options.confirmLabel ?? 'Bestätigen'}
        </button>
      </div>
    </Dialog>
  )
}

export function PromptDialog({
  options,
  onAnswer,
}: {
  options: PromptOptions
  onAnswer: (value: string | null) => void
}) {
  const [value, setValue] = useState(options.initial ?? '')

  function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = value.trim()
    onAnswer(trimmed ? trimmed : null)
  }

  return (
    <Dialog title={options.title} onClose={() => onAnswer(null)}>
      <form onSubmit={submit} className="space-y-4">
        <label className="block space-y-1.5">
          <span className="text-sm text-muted">{options.label}</span>
          <input
            className="input"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            autoFocus
            onFocus={(e) => e.target.select()}
          />
        </label>
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={() => onAnswer(null)}>
            Abbrechen
          </button>
          <button className="btn-primary" disabled={!value.trim()}>
            {options.confirmLabel ?? 'Speichern'}
          </button>
        </div>
      </form>
    </Dialog>
  )
}
