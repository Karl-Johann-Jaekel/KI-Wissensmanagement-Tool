import { useCallback, useState, type ReactNode } from 'react'
import {
  ConfirmDialog,
  PromptDialog,
  type ConfirmOptions,
  type PromptOptions,
} from './Dialog'

/**
 * Replacements for `window.confirm` and `window.prompt`. Both hooks return a promise, so call
 * sites read like the native calls they replace, plus the node to render.
 */

export function useConfirm(): [(options: ConfirmOptions) => Promise<boolean>, ReactNode] {
  const [request, setRequest] = useState<{
    options: ConfirmOptions
    resolve: (value: boolean) => void
  } | null>(null)

  const confirm = useCallback(
    (options: ConfirmOptions) => new Promise<boolean>((resolve) => setRequest({ options, resolve })),
    [],
  )

  const answer = (value: boolean) => {
    request?.resolve(value)
    setRequest(null)
  }

  const node = request ? <ConfirmDialog options={request.options} onAnswer={answer} /> : null
  return [confirm, node]
}

export function usePrompt(): [(options: PromptOptions) => Promise<string | null>, ReactNode] {
  const [request, setRequest] = useState<{
    options: PromptOptions
    resolve: (value: string | null) => void
  } | null>(null)

  const prompt = useCallback(
    (options: PromptOptions) =>
      new Promise<string | null>((resolve) => setRequest({ options, resolve })),
    [],
  )

  const answer = (value: string | null) => {
    request?.resolve(value)
    setRequest(null)
  }

  const node = request ? <PromptDialog options={request.options} onAnswer={answer} /> : null
  return [prompt, node]
}
