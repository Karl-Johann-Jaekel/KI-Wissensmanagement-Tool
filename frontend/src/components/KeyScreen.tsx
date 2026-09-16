import { useState, type FormEvent } from 'react'
import { api, setAccessKey } from '../api'
import { errorText } from '../hooks'
import { Spinner } from './Icons'

export function KeyScreen({ onUnlocked }: { onUnlocked: () => void }) {
  const [key, setKey] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setChecking(true)
    setError(null)
    try {
      await api.checkKey(key.trim())
      setAccessKey(key.trim())
      onUnlocked()
    } catch (err) {
      setError(errorText(err))
    } finally {
      setChecking(false)
    }
  }

  return (
    <main className="flex min-h-full items-center justify-center p-4">
      <form onSubmit={submit} className="panel w-full max-w-sm gap-4 p-6">
        <div>
          <h1 className="text-xl font-semibold">Notebook</h1>
          <p className="mt-1 text-sm text-muted">
            Demo-Instanz. Bitte den Zugangsschlüssel aus der E-Mail eingeben.
          </p>
        </div>
        <input
          className="input"
          type="password"
          autoComplete="current-password"
          placeholder="Zugangsschlüssel"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          autoFocus
        />
        {error && <p className="text-sm text-danger">{error}</p>}
        <button className="btn-primary py-2" disabled={!key.trim() || checking}>
          {checking ? <Spinner /> : 'Öffnen'}
        </button>
      </form>
    </main>
  )
}
