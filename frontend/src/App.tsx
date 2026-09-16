import { useCallback, useEffect, useState } from 'react'
import { getAccessKey, onUnauthorized, setAccessKey } from './api'
import { KeyScreen } from './components/KeyScreen'
import { NotebookList } from './components/NotebookList'
import { NotebookView } from './components/NotebookView'

function notebookIdFromHash(): string | null {
  const match = /^#\/notebook\/([0-9a-f-]{36})$/.exec(window.location.hash)
  return match?.[1] ?? null
}

export default function App() {
  const [unlocked, setUnlocked] = useState(() => getAccessKey() !== null)
  const [notebookId, setNotebookId] = useState(notebookIdFromHash)

  useEffect(() => {
    onUnauthorized(() => {
      setAccessKey(null)
      setUnlocked(false)
    })
    const onHash = () => setNotebookId(notebookIdFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const open = useCallback((id: string) => {
    window.location.hash = `#/notebook/${id}`
  }, [])
  const back = useCallback(() => {
    window.location.hash = '#/'
  }, [])

  if (!unlocked) return <KeyScreen onUnlocked={() => setUnlocked(true)} />
  if (notebookId) return <NotebookView key={notebookId} notebookId={notebookId} onBack={back} />
  return <NotebookList onOpen={open} />
}
