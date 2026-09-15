import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

export interface Loader<T> {
  data: T | undefined
  error: string | null
  loading: boolean
  reload: () => Promise<void>
  setData: (update: (current: T | undefined) => T) => void
}

interface LoaderState<T> {
  key: string | null
  data: T | undefined
  error: string | null
}

/** Fetch on mount / when `key` changes; exposes error and loading state for every call. */
export function useLoader<T>(fetcher: () => Promise<T>, key: string): Loader<T> {
  const [state, setState] = useState<LoaderState<T>>({ key: null, data: undefined, error: null })
  const fetcherRef = useRef(fetcher)
  const keyRef = useRef(key)

  useLayoutEffect(() => {
    fetcherRef.current = fetcher
    keyRef.current = key
  })

  const reload = useCallback(async () => {
    const requestedKey = keyRef.current
    try {
      const data = await fetcherRef.current()
      if (keyRef.current === requestedKey) setState({ key: requestedKey, data, error: null })
    } catch (err) {
      if (keyRef.current === requestedKey) {
        setState((current) => ({
          key: requestedKey,
          data: current.key === requestedKey ? current.data : undefined,
          error: errorText(err),
        }))
      }
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [key, reload])

  const setData = useCallback((update: (current: T | undefined) => T) => {
    setState((current) => ({ ...current, data: update(current.data) }))
  }, [])

  const current = state.key === key
  return {
    data: current ? state.data : undefined,
    error: current ? state.error : null,
    loading: !current,
    reload,
    setData,
  }
}

export function errorText(err: unknown): string {
  return err instanceof Error ? err.message : 'Unbekannter Fehler'
}
