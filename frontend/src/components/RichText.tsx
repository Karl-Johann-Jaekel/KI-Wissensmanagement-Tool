import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import type { Citation } from '../types'

/**
 * Minimal Markdown subset for model answers and notes: paragraphs, "- " / "1. " lists,
 * **bold**, and [n] citation chips. Avoids a Markdown dependency and never renders raw HTML.
 */

type Block =
  | { kind: 'p'; lines: string[] }
  | { kind: 'ul'; items: string[] }
  | { kind: 'ol'; items: string[] }

const RULE = /^\s*([-*_])\1{2,}\s*$/
const BULLET = /^\s*[-*•]\s+(.*)$/
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/
const INLINE = /(\*\*[^*]+\*\*|\[\d+\])/g

function parseBlocks(text: string): Block[] {
  const blocks: Block[] = []
  for (const line of text.split(/\r?\n/)) {
    const bullet = BULLET.exec(line)
    const numbered = bullet ? null : NUMBERED.exec(line)
    const last = blocks.at(-1)
    if (RULE.test(line)) {
      blocks.push({ kind: 'p', lines: [] }) // horizontal rules only separate paragraphs
    } else if (bullet?.[1] !== undefined) {
      if (last?.kind === 'ul') last.items.push(bullet[1])
      else blocks.push({ kind: 'ul', items: [bullet[1]] })
    } else if (numbered?.[1] !== undefined) {
      if (last?.kind === 'ol') last.items.push(numbered[1])
      else blocks.push({ kind: 'ol', items: [numbered[1]] })
    } else if (line.trim() === '') {
      if (last && !(last.kind === 'p' && last.lines.length === 0)) blocks.push({ kind: 'p', lines: [] })
    } else {
      const heading = line.replace(/^#{1,6}\s+/, '')
      const content = heading !== line ? `**${heading}**` : line
      if (last?.kind === 'p') last.lines.push(content)
      else blocks.push({ kind: 'p', lines: [content] })
    }
  }
  return blocks.filter((b) => (b.kind === 'p' ? b.lines.length > 0 : b.items.length > 0))
}

interface RichTextProps {
  text: string
  citations?: Citation[]
  onCitation?: (citation: Citation) => void
}

export function RichText({ text, citations = [], onCitation }: RichTextProps) {
  const byNumber = new Map(citations.map((c) => [c.n, c]))

  const inline = (value: string, keyPrefix: string): ReactNode[] =>
    value.split(INLINE).map((part, i) => {
      const key = `${keyPrefix}-${i}`
      if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
        return <strong key={key}>{part.slice(2, -2)}</strong>
      }
      const marker = /^\[(\d+)\]$/.exec(part)
      const citation = marker?.[1] ? byNumber.get(Number(marker[1])) : undefined
      if (citation) {
        return (
          <CitationChip key={key} citation={citation} onClick={onCitation} />
        )
      }
      return part
    })

  return (
    <div className="space-y-2 text-sm leading-relaxed break-words">
      {parseBlocks(text).map((block, i) => {
        if (block.kind === 'ul' || block.kind === 'ol') {
          const Tag = block.kind
          return (
            <Tag key={i} className={`space-y-1 pl-5 ${block.kind === 'ul' ? 'list-disc' : 'list-decimal'}`}>
              {block.items.map((item, j) => (
                <li key={j}>{inline(item, `${i}-${j}`)}</li>
              ))}
            </Tag>
          )
        }
        return (
          <p key={i} className="whitespace-pre-line">
            {inline(block.lines.join('\n'), String(i))}
          </p>
        )
      })}
    </div>
  )
}

function CitationChip({
  citation,
  onClick,
}: {
  citation: Citation
  onClick?: (citation: Citation) => void
}) {
  const [anchor, setAnchor] = useState<DOMRect | null>(null)
  const ref = useRef<HTMLButtonElement>(null)
  const label = `${citation.source_title}${citation.page ? `, S. ${citation.page}` : ''}`

  const show = () => setAnchor(ref.current?.getBoundingClientRect() ?? null)
  const hide = () => setAnchor(null)

  // The preview is positioned against the viewport, so scrolling would leave it behind.
  useEffect(() => {
    if (!anchor) return
    window.addEventListener('scroll', hide, true)
    return () => window.removeEventListener('scroll', hide, true)
  }, [anchor])

  return (
    // No transform on this wrapper: it would become the containing block of the fixed preview.
    <span className="inline">
      <button
        ref={ref}
        type="button"
        onClick={() => onClick?.(citation)}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        aria-label={`Quelle ${citation.n}: ${label}`}
        className="ml-1 inline-flex h-5 min-w-5 -translate-y-px items-center justify-center rounded-full bg-accent-soft px-1.5 align-middle text-[11px] font-semibold text-accent transition-colors hover:bg-accent hover:text-accent-fg"
      >
        {citation.n}
      </button>
      {anchor && <CitationPreview citation={citation} label={label} anchor={anchor} />}
    </span>
  )
}

const PREVIEW_WIDTH = 320
const PREVIEW_GAP = 8

/**
 * Hover card for a citation chip. Fixed to the viewport because the chat column scrolls and
 * would clip an absolutely positioned card near its edges.
 */
function CitationPreview({
  citation,
  label,
  anchor,
}: {
  citation: Citation
  label: string
  anchor: DOMRect
}) {
  const width = Math.min(PREVIEW_WIDTH, window.innerWidth - 2 * PREVIEW_GAP)
  const left = Math.min(
    Math.max(PREVIEW_GAP, anchor.left + anchor.width / 2 - width / 2),
    window.innerWidth - width - PREVIEW_GAP,
  )
  const above = anchor.top > window.innerHeight / 2
  const style: CSSProperties = above
    ? { left, width, bottom: window.innerHeight - anchor.top + PREVIEW_GAP }
    : { left, width, top: anchor.bottom + PREVIEW_GAP }

  return (
    <span
      role="tooltip"
      style={style}
      className="pointer-events-none fixed z-40 block rounded-xl border border-line bg-surface p-3 shadow-lg"
    >
      <span className="block text-xs font-medium text-fg">{label}</span>
      <span className="mt-1 block text-xs leading-relaxed text-muted">{citation.snippet}</span>
      <span className="mt-2 block text-[11px] text-accent">Klicken öffnet die Passage</span>
    </span>
  )
}
